"""
tap.py — кросс-платформенный TAP-интерфейс для P2P L2 VPN.

Экспортирует одну штуку — класс TAPDevice с единым API:

    tap = TAPDevice(name="tap0", ip="10.0.0.1", prefix=24, mtu=1420)
    tap.setup()
    tap.start_reading(loop, on_frame=callback)   # callback(frame: bytes)
    tap.write(frame_bytes)
    tap.teardown()

Бэкенды:
  • Linux   → /dev/net/tun, TUNSETIFF, ip/iptables/ethtool
  • Windows → TAP-Windows6 (tap0901) через CreateFile + DeviceIoControl,
              конфиг через netsh, чтение в отдельном потоке.

Windows-часть требует:
  • драйвер TAP-Windows6 (ставится с OpenVPN или отдельно)
  • pywin32 (`pip install pywin32`)
  • запуск от имени администратора
"""
from __future__ import annotations

import asyncio
import logging
import os
import struct
import sys
import threading
from typing import Callable, Optional

log = logging.getLogger("vpn.tap")

MAX_FRAME = 2048  # Ethernet(1518) + VLAN + запас; offload отключён


# ══════════════════════════════════════════════════════════════════
#  Базовый интерфейс
# ══════════════════════════════════════════════════════════════════
class _TAPBase:
    name: str

    def __init__(self, name: str, ip: str, prefix: int, mtu: int):
        self.name = name
        self.ip = ip
        self.prefix = prefix
        self.mtu = mtu

    def setup(self) -> None:       ...
    def teardown(self) -> None:    ...
    def write(self, frame: bytes) -> None: ...
    def start_reading(self, loop: asyncio.AbstractEventLoop,
                      on_frame: Callable[[bytes], None]) -> None: ...


# ══════════════════════════════════════════════════════════════════
#  Linux backend: /dev/net/tun + epoll
# ══════════════════════════════════════════════════════════════════
class _TAPLinux(_TAPBase):
    TUNSETIFF  = 0x400454CA
    IFF_TAP    = 0x0002
    IFF_NO_PI  = 0x1000

    def __init__(self, name, ip, prefix, mtu):
        super().__init__(name, ip, prefix, mtu)
        self._fd: Optional[int]   = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_frame: Optional[Callable[[bytes], None]] = None

    # ── open / configure / close ────────────────────────────────
    def setup(self) -> None:
        import fcntl
        fd = os.open("/dev/net/tun", os.O_RDWR | os.O_NONBLOCK)
        ifr = struct.pack("16sH22x", self.name.encode(),
                          self.IFF_TAP | self.IFF_NO_PI)
        actual = fcntl.ioctl(fd, self.TUNSETIFF, ifr)
        self.name = actual[:16].rstrip(b"\x00").decode()
        self._fd = fd
        log.info("Linux TAP opened: %s (fd=%d)", self.name, fd)
        self._configure()

    def _configure(self) -> None:
        """Настройка Linux TAP — см. подробный коммент в configure_tap()
        старой версии: MTU, offload off, MSS clamp."""
        mask = f"{self.ip}/{self.prefix}"
        mss  = self.mtu - 40

        for cmd in (
            f"ip link set {self.name} mtu {self.mtu}",
            f"ip link set {self.name} up",
            f"ip addr replace {mask} dev {self.name}",
        ):
            if os.system(cmd) != 0:
                raise RuntimeError(f"Command failed: {cmd}")

        # Критично: без этого TCP и большие UDP «ложатся», ping работает
        if os.system(f"ethtool -K {self.name} tso off gso off gro off "
                     f"lro off tx off sg off 2>/dev/null") != 0:
            log.warning("ethtool not installed — TCP/large UDP may drop")

        for chain, match in (("OUTPUT", f"-o {self.name}"),
                             ("INPUT",  f"-i {self.name}")):
            rule = (f"{chain} {match} -p tcp --tcp-flags SYN,RST SYN "
                    f"-j TCPMSS --set-mss {mss}")
            os.system(
                f"iptables -t mangle -C {rule} 2>/dev/null || "
                f"iptables -t mangle -A {rule}"
            )

        log.info("Configured %s  ip=%s  mtu=%d  mss=%d  (offload off)",
                 self.name, mask, self.mtu, mss)

    def teardown(self) -> None:
        if self._fd is None:
            return
        for chain, match in (("OUTPUT", f"-o {self.name}"),
                             ("INPUT",  f"-i {self.name}")):
            os.system(
                f"iptables -t mangle -D {chain} {match} -p tcp "
                f"--tcp-flags SYN,RST SYN -j TCPMSS --set-mss "
                f"{self.mtu - 40} 2>/dev/null"
            )
        os.system(f"ip link set {self.name} down 2>/dev/null")
        os.system(f"ip addr flush dev {self.name} 2>/dev/null")
        try:
            if self._loop:
                self._loop.remove_reader(self._fd)
            os.close(self._fd)
        except Exception:
            pass
        self._fd = None
        log.info("Linux TAP %s torn down", self.name)

    # ── I/O ─────────────────────────────────────────────────────
    def write(self, frame: bytes) -> None:
        try:
            os.write(self._fd, frame)
        except BlockingIOError:
            log.warning("TAP write buffer full, dropped %d bytes", len(frame))
        except OSError as e:
            log.warning("TAP write error: %s", e)

    def start_reading(self, loop, on_frame):
        self._loop = loop
        self._on_frame = on_frame
        loop.add_reader(self._fd, self._drain)
        log.debug("Linux TAP reader registered via epoll")

    def _drain(self) -> None:
        try:
            while True:
                try:
                    frame = os.read(self._fd, MAX_FRAME)
                    if frame:
                        self._on_frame(frame)
                except BlockingIOError:
                    return
        except OSError as e:
            log.error("TAP read error: %s", e)


# ══════════════════════════════════════════════════════════════════
#  Windows backend: TAP-Windows6 (tap0901) + поток для чтения
# ══════════════════════════════════════════════════════════════════
class _TAPWindows(_TAPBase):
    COMPONENT_ID         = "tap0901"
    ADAPTER_KEY          = (r"SYSTEM\CurrentControlSet\Control\Class"
                            r"\{4D36E972-E325-11CE-BFC1-08002BE10318}")
    CONNECTIONS_KEY      = (r"SYSTEM\CurrentControlSet\Control\Network"
                            r"\{4D36E972-E325-11CE-BFC1-08002BE10318}")

    # DeviceIoControl codes — из tap-windows.h
    @staticmethod
    def _ctl(dev_type, fn):
        return (dev_type << 16) | (fn << 2)

    def __init__(self, name, ip, prefix, mtu):
        super().__init__(name, ip, prefix, mtu)
        self._handle = None
        self._guid: Optional[str] = None
        self._friendly: Optional[str] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_frame: Optional[Callable[[bytes], None]] = None

    # ── adapter discovery ───────────────────────────────────────
    @classmethod
    def _find_adapter(cls, preferred_name: Optional[str] = None):
        """Пробегает реестр, возвращает (guid, friendly_name) первого
        TAP-Windows6. Если задан preferred_name — ищет строго по нему."""
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, cls.ADAPTER_KEY) as root:
            i = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub_name) as sub:
                        try:
                            cid = winreg.QueryValueEx(sub, "ComponentId")[0]
                        except FileNotFoundError:
                            continue
                        if cid != cls.COMPONENT_ID:
                            continue
                        guid = winreg.QueryValueEx(sub, "NetCfgInstanceId")[0]
                        conn_path = f"{cls.CONNECTIONS_KEY}\\{guid}\\Connection"
                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE, conn_path
                        ) as conn:
                            name = winreg.QueryValueEx(conn, "Name")[0]
                        if preferred_name and name != preferred_name:
                            continue
                        return guid, name
                except OSError:
                    continue
        raise RuntimeError(
            "TAP-Windows6 adapter not found. Install the driver from "
            "OpenVPN (https://build.openvpn.net/downloads/releases/) "
            "or run `tapctl.exe create` from WireGuard/OpenVPN toolchain."
        )

    # ── open / configure / close ────────────────────────────────
    def setup(self) -> None:
        import win32file  # pywin32
        preferred = None if self.name in ("tap0", "") else self.name
        self._guid, self._friendly = self._find_adapter(preferred)
        log.info("Windows TAP adapter: %s  guid=%s",
                 self._friendly, self._guid)

        device_path = rf"\\.\Global\{self._guid}.tap"
        self._handle = win32file.CreateFile(
            device_path,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            win32file.FILE_ATTRIBUTE_SYSTEM | win32file.FILE_FLAG_OVERLAPPED,
            None,
        )

        # TAP_WIN_IOCTL_SET_MEDIA_STATUS = CTL_CODE(34, 6) — «дёрнуть кабель»
        win32file.DeviceIoControl(
            self._handle, self._ctl(34, 6),
            struct.pack("I", 1), 4, None,
        )
        log.info("Windows TAP media status → connected")

        self._configure_netsh()
        self.name = self._friendly  # далее используем имя как в netsh

    def _configure_netsh(self) -> None:
        """Настройка адаптера через netsh (требует админа)."""
        import subprocess
        import ipaddress
        mask = str(ipaddress.IPv4Network(
            f"0.0.0.0/{self.prefix}", strict=False
        ).netmask)
        name = self._friendly

        # IP + маска
        subprocess.run(
            ["netsh", "interface", "ipv4", "set", "address",
             f"name={name}", "source=static",
             f"address={self.ip}", f"mask={mask}"],
            check=True,
        )
        # MTU. store=active — до перезагрузки, persistent тоже можно.
        subprocess.run(
            ["netsh", "interface", "ipv4", "set", "subinterface",
             name, f"mtu={self.mtu}", "store=active"],
            check=True,
        )
        # Отключить offload на адаптере (PowerShell)
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Disable-NetAdapterLso -Name '{name}' -ErrorAction "
             f"SilentlyContinue; "
             f"Disable-NetAdapterChecksumOffload -Name '{name}' "
             f"-ErrorAction SilentlyContinue"],
            check=False,
        )
        log.info("Configured %s  ip=%s/%d  mtu=%d  (offload off)",
                 name, self.ip, self.prefix, self.mtu)

    def teardown(self) -> None:
        import win32file
        self._stop.set()
        if self._handle is not None:
            try:
                # Опустить линк (media status = disconnected)
                win32file.DeviceIoControl(
                    self._handle, self._ctl(34, 6),
                    struct.pack("I", 0), 4, None,
                )
            except Exception:
                pass
            try:
                win32file.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2.0)
        log.info("Windows TAP %s torn down", self._friendly or self.name)

    # ── I/O ─────────────────────────────────────────────────────
    def write(self, frame: bytes) -> None:
        import win32file
        import pywintypes
        overlapped = pywintypes.OVERLAPPED()
        try:
            win32file.WriteFile(self._handle, frame, overlapped)
            win32file.GetOverlappedResult(self._handle, overlapped, True)
        except pywintypes.error as e:
            log.warning("TAP write error: %s", e)

    def start_reading(self, loop, on_frame):
        self._loop = loop
        self._on_frame = on_frame
        self._reader_thread = threading.Thread(
            target=self._read_loop, name="tap-win-reader", daemon=True
        )
        self._reader_thread.start()
        log.debug("Windows TAP reader thread started")

    def _read_loop(self) -> None:
        """Блокирующее overlapped-чтение в отдельном потоке,
        фреймы доставляются в asyncio через call_soon_threadsafe."""
        import win32file
        import win32event
        import pywintypes

        overlapped = pywintypes.OVERLAPPED()
        overlapped.hEvent = win32event.CreateEvent(None, False, False, None)
        buf = win32file.AllocateReadBuffer(MAX_FRAME)

        while not self._stop.is_set():
            try:
                win32file.ReadFile(self._handle, buf, overlapped)
                n = win32file.GetOverlappedResult(
                    self._handle, overlapped, True
                )
                if n and not self._stop.is_set():
                    frame = bytes(buf[:n])
                    self._loop.call_soon_threadsafe(self._on_frame, frame)
            except pywintypes.error as e:
                # 995 = ERROR_OPERATION_ABORTED (handle closed),
                # 6   = invalid handle. И то и другое = «мы закрываемся».
                if e.winerror in (995, 6) or self._stop.is_set():
                    return
                log.error("TAP read error: %s", e)
                return


# ══════════════════════════════════════════════════════════════════
#  Публичная фабрика — выбирает backend по платформе
# ══════════════════════════════════════════════════════════════════
def TAPDevice(name: str, ip: str, prefix: int, mtu: int) -> _TAPBase:
    if sys.platform.startswith("linux"):
        return _TAPLinux(name, ip, prefix, mtu)
    if sys.platform == "win32":
        return _TAPWindows(name, ip, prefix, mtu)
    raise RuntimeError(
        f"Unsupported platform: {sys.platform}. "
        f"Only Linux and Windows are supported."
    )


def is_admin() -> bool:
    """Проверка привилегий: root на Linux, Administrator на Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0
