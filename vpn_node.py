#!/usr/bin/env python3
"""
P2P L2 VPN Node — creates a virtual Ethernet (TAP) interface
and tunnels raw Ethernet frames over UDP to all known peers.

Designed for Linux gaming LANs. Easily extensible to N peers.
"""

import asyncio
import fcntl
import logging
import os
import struct
import time
from dataclasses import dataclass
from typing import Dict, Optional

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────
TUNSETIFF   = 0x400454CA
IFF_TAP     = 0x0002
IFF_NO_PI   = 0x1000
ETH_PROTO_ARP = 0x0806

MAX_FRAME   = 65535     # max read size — bounded by TAP_MTU at write time
MAGIC       = b"P2PL2"  # 5-byte header prefix to identify our packets
MAGIC_LEN   = len(MAGIC)
HEARTBEAT_INTERVAL  = 5   # seconds between regular keepalive pings
PEER_TIMEOUT        = 30  # seconds before a peer is considered dead
PUNCH_COUNT         = 10  # rapid HELLOs at startup for hole punching
PUNCH_INTERVAL      = 0.3 # seconds between punch packets

# ── MTU budget ────────────────────────────────────────────────
# Physical MTU 1500
#  - IP header   20
#  - UDP header   8
#  - MAGIC+TYPE   6
#  - PPPoE/ISP   46  (safety margin)
# ─────────────────
# TAP MTU       1420  → Ethernet frames never exceed physical MTU,
#                       NAT routers won't fragment/drop UDP datagrams
TAP_MTU = 1420

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("vpn")


# ──────────────────────────────────────────────────────────────
# Peer state
# ──────────────────────────────────────────────────────────────
@dataclass
class Peer:
    host: str
    port: int
    # 0.0 = "никогда не отвечал" (пир из конфига, непроверенный)
    last_seen: float = 0.0
    mac: Optional[bytes] = None

    @property
    def addr(self):
        return (self.host, self.port)

    @property
    def confirmed(self) -> bool:
        """True если пир хотя бы раз прислал пакет."""
        return self.last_seen > 0.0

    def touch(self):
        self.last_seen = time.time()

    def is_alive(self) -> bool:
        """
        Живым считается только подтверждённый пир, от которого
        пришёл пакет не позже PEER_TIMEOUT секунд назад.
        Непроверенные пиры из конфига — статус 'pending', не alive.
        """
        if not self.confirmed:
            return False
        return (time.time() - self.last_seen) < PEER_TIMEOUT

    @property
    def status(self) -> str:
        if not self.confirmed:
            return "pending"
        return "alive" if self.is_alive() else "dead"

    def __str__(self):
        mac_str = ":".join(f"{b:02x}" for b in self.mac) if self.mac else "unknown"
        return f"{self.host}:{self.port} [{self.status}] mac={mac_str}"


# ──────────────────────────────────────────────────────────────
# TAP interface helpers
# ──────────────────────────────────────────────────────────────
def open_tap(name: str = "tap0") -> tuple[int, str]:
    """Open (or create) a TAP interface, return (fd, actual_name)."""
    TUNDEV = "/dev/net/tun"
    fd = os.open(TUNDEV, os.O_RDWR | os.O_NONBLOCK)
    ifr = struct.pack("16sH22x", name.encode(), IFF_TAP | IFF_NO_PI)
    ioctl_result = fcntl.ioctl(fd, TUNSETIFF, ifr)
    actual_name = ioctl_result[:16].rstrip(b"\x00").decode()
    log.info("Opened TAP interface: %s (fd=%d)", actual_name, fd)
    return fd, actual_name


def configure_tap(iface: str, ip: str, prefix: int = 24, mtu: int = TAP_MTU):
    """
    Bring up the TAP, assign IP, set MTU and clamp TCP MSS.

    MTU = 1420: физический MTU(1500) - IP(20) - UDP(8) - MAGIC(6) - PPPoE(46)
    Без этого: ping OK (маленькие пакеты), TCP/игры — нет (большие дропаются).

    MSS clamping — КРИТИЧНО для TCP:
      FORWARD chain = транзитный трафик (роутинг через машину).
      OUTPUT chain  = трафик, исходящий С этой машины через tap0.
      INPUT chain   = трафик, входящий В эту машину через tap0.
    Для прямых соединений host↔host через TAP нужны OUTPUT + INPUT,
    FORWARD здесь вообще не задействован.
    --clamp-mss-to-pmtu автоматически берёт MTU интерфейса — надёжнее
    чем жёсткое число, работает даже если MTU изменится.
    """
    mask = f"{ip}/{prefix}"

    # Базовые команды — обязательны
    base_cmds = [
        f"ip link set {iface} mtu {mtu}",
        f"ip link set {iface} up",
        f"ip addr add {mask} dev {iface}",
    ]
    for cmd in base_cmds:
        ret = os.system(cmd)
        if ret != 0:
            raise RuntimeError(f"Command failed ({ret}): {cmd}")

    # MSS clamping — желательны, но не фатальны при отсутствии iptables
    mss_cmds = [
        # Трафик, уходящий с этой машины через tap0 (наш ncat-клиент, игра)
        f"iptables -t mangle -C OUTPUT -o {iface} -p tcp "
        f"--tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null || "
        f"iptables -t mangle -A OUTPUT -o {iface} -p tcp "
        f"--tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu",

        # Трафик, приходящий на эту машину через tap0 (от пира)
        f"iptables -t mangle -C INPUT -i {iface} -p tcp "
        f"--tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null || "
        f"iptables -t mangle -A INPUT -i {iface} -p tcp "
        f"--tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu",
    ]
    for cmd in mss_cmds:
        ret = os.system(cmd)
        if ret != 0:
            log.warning("iptables MSS clamp failed (no iptables?): continuing anyway")

    log.info("Configured %s  ip=%s  mtu=%d  mss=%d", iface, mask, mtu, mtu - 40)


# ──────────────────────────────────────────────────────────────
# Packet wire format
#
#   [ MAGIC (5) | TYPE (1) | PAYLOAD ]
#
#   TYPE 0x01 — DATA  : raw Ethernet frame
#   TYPE 0x02 — HELLO : keepalive / peer announcement (no payload)
# ──────────────────────────────────────────────────────────────
TYPE_DATA  = 0x01
TYPE_HELLO = 0x02


def encode_data(frame: bytes) -> bytes:
    return MAGIC + bytes([TYPE_DATA]) + frame


def encode_hello() -> bytes:
    return MAGIC + bytes([TYPE_HELLO])


def decode(packet: bytes):
    """Returns (type, payload) or (None, None) if invalid."""
    if len(packet) < MAGIC_LEN + 1 or packet[:MAGIC_LEN] != MAGIC:
        return None, None
    ptype = packet[MAGIC_LEN]
    payload = packet[MAGIC_LEN + 1:]
    return ptype, payload


# ──────────────────────────────────────────────────────────────
# Main VPN node
# ──────────────────────────────────────────────────────────────
class VPNNode:
    def __init__(self, config):
        self.cfg = config
        self.peers: Dict[tuple, Peer] = {}   # (host, port) → Peer
        self._tap_fd: Optional[int] = None
        self._iface: Optional[str] = None
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Setup ────────────────────────────────────────────────

    def setup_tap(self):
        self._tap_fd, self._iface = open_tap(self.cfg["tap_name"])
        configure_tap(self._iface, self.cfg["local_ip"], self.cfg.get("prefix", 24))

    def teardown_tap(self):
        """Убрать iptables правила и опустить интерфейс при завершении."""
        if not self._iface:
            return
        iface = self._iface
        cleanup_cmds = [
            f"iptables -t mangle -D OUTPUT -o {iface} -p tcp "
            f"--tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null",
            f"iptables -t mangle -D INPUT -i {iface} -p tcp "
            f"--tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null",
            f"ip link set {iface} down 2>/dev/null",
            f"ip addr flush dev {iface} 2>/dev/null",
        ]
        for cmd in cleanup_cmds:
            os.system(cmd)
        if self._tap_fd is not None:
            try:
                self._loop.remove_reader(self._tap_fd)
                os.close(self._tap_fd)
            except Exception:
                pass
        log.info("TAP %s torn down", iface)

    def _add_initial_peers(self):
        for hp in self.cfg.get("peers", []):
            host, port = hp["host"], hp["port"]
            key = (host, port)
            self.peers[key] = Peer(host=host, port=port)
            log.info("Registered initial peer: %s:%d", host, port)

    # ── UDP protocol ─────────────────────────────────────────

    class _UDPProtocol(asyncio.DatagramProtocol):
        def __init__(self, node):
            self.node = node

        def connection_made(self, transport):
            self.node._transport = transport
            log.info("UDP socket ready on port %d", self.node.cfg["listen_port"])

        def datagram_received(self, data, addr):
            self.node._on_udp(data, addr)

        def error_received(self, exc):
            log.warning("UDP error: %s", exc)

    # ── Core event handlers ──────────────────────────────────

    def _on_udp(self, data: bytes, addr: tuple):
        """Called when a UDP datagram arrives from a peer."""
        ptype, payload = decode(data)
        if ptype is None:
            return

        # Auto-register unknown peers (N-peer extensibility)
        if addr not in self.peers:
            log.info("New peer discovered: %s:%d", *addr)
            self.peers[addr] = Peer(host=addr[0], port=addr[1])

        peer = self.peers[addr]
        peer.touch()

        if ptype == TYPE_DATA:
            self._write_tap(payload)
            # Learn MAC from Ethernet src field (bytes 6-12)
            if len(payload) >= 12 and peer.mac is None:
                peer.mac = payload[6:12]
                log.info("Learned MAC for %s: %s", addr, peer)

        elif ptype == TYPE_HELLO:
            log.debug("HELLO from %s:%d", *addr)

    def _write_tap(self, frame: bytes):
        """
        Записать Ethernet-фрейм в TAP-интерфейс.
        TAP fd неблокирующий: при переполнении буфера получаем EAGAIN —
        логируем и пропускаем (лучше потерять один фрейм, чем подвиснуть).
        """
        try:
            os.write(self._tap_fd, frame)
        except BlockingIOError:
            log.warning("TAP write buffer full, frame dropped (%d bytes)", len(frame))
        except OSError as e:
            log.warning("TAP write error: %s", e)

    def _start_tap_reader(self):
        """
        Регистрируем TAP-fd в event loop через add_reader (epoll).
        Callback вызывается мгновенно при появлении данных — без потоков,
        без sleep, без busy-wait. Именно так должен работать async I/O.
        """
        self._loop.add_reader(self._tap_fd, self._on_tap_readable)
        log.debug("TAP reader registered via add_reader (epoll)")

    def _on_tap_readable(self):
        """
        Вызывается event loop'ом когда TAP fd готов к чтению.
        Читаем ВСЕ доступные фреймы за один вызов (burst read),
        чтобы не копить очередь при пиковой нагрузке.
        """
        try:
            while True:
                try:
                    frame = os.read(self._tap_fd, MAX_FRAME)
                    if frame:
                        log.debug("TAP → %d bytes, forwarding to peers", len(frame))
                        self._broadcast(frame)
                except BlockingIOError:
                    # Буфер исчерпан — выходим, epoll позовёт снова когда придут данные
                    break
        except OSError as e:
            log.error("TAP read error: %s", e)

    def _broadcast(self, frame: bytes):
        """Send an Ethernet frame to all reachable peers.

        pending-пиры (из конфига, ещё не ответили) тоже получают фреймы —
        вдруг они только что поднялись. Pruning только для confirmed-пиров,
        которые перестали отвечать.
        """
        if self._transport is None:
            return
        packet = encode_data(frame)
        to_remove = []
        for key, peer in self.peers.items():
            if peer.is_alive() or not peer.confirmed:
                self._transport.sendto(packet, peer.addr)
            else:
                to_remove.append(key)
        for key in to_remove:
            log.info("Peer timed out, removing: %s", self.peers.pop(key))

    # ── Unicast helper (for future use / routing) ────────────
    def send_to(self, frame: bytes, addr: tuple):
        if self._transport and addr in self.peers:
            self._transport.sendto(encode_data(frame), addr)

    # ── Hole punching ────────────────────────────────────────────

    async def _hole_punch_all(self):
        """
        UDP Hole Punching без relay-сервера.

        Оба клиента одновременно шлют HELLO на публичный адрес друг друга.
        Первый исходящий пакет открывает «дырку» в NAT: маршрутизатор
        запоминает маппинг (src, dst) и начинает пропускать ответы.

        Работает для: Full Cone, Address-Restricted, Port-Restricted NAT.
        Для Symmetric NAT — не гарантировано (редко у домашних провайдеров).
        """
        if not self.peers:
            return
        hello = encode_hello()
        log.info("Starting hole punch for %d peer(s)…", len(self.peers))
        for i in range(PUNCH_COUNT):
            for peer in list(self.peers.values()):
                if self._transport:
                    self._transport.sendto(hello, peer.addr)
                    log.debug("Punch #%d → %s", i + 1, peer.addr)
            await asyncio.sleep(PUNCH_INTERVAL)
        confirmed = [p for p in self.peers.values() if p.confirmed]
        if confirmed:
            log.info("Hole punch OK: %d/%d peers responded",
                     len(confirmed), len(self.peers))
        else:
            log.warning(
                "Hole punch: no peers responded after %d attempts. "
                "Check address, firewall, and NAT type.", PUNCH_COUNT)

    # ── Heartbeat ────────────────────────────────────────────

    async def _heartbeat(self):
        """Periodically send HELLO to all known peers to keep them alive."""
        hello = encode_hello()
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            for peer in list(self.peers.values()):
                if self._transport:
                    self._transport.sendto(hello, peer.addr)
            self._log_peers()

    def _log_peers(self):
        peers = list(self.peers.values())
        alive   = sum(1 for p in peers if p.is_alive())
        pending = sum(1 for p in peers if not p.confirmed)
        dead    = len(peers) - alive - pending
        log.info(
            "Peers — alive: %d  pending: %d  dead: %d  total: %d",
            alive, pending, dead, len(peers),
        )
        for p in peers:
            log.info("  %s", p)

    # ── Entry point ──────────────────────────────────────────

    async def run(self):
        self._loop = asyncio.get_running_loop()
        self.setup_tap()
        self._add_initial_peers()

        # Create UDP socket (SO_REUSEPORT позволяет занять порт сразу после
        # STUN-сокета без ожидания TIME_WAIT — оба используют один порт)
        transport, _ = await self._loop.create_datagram_endpoint(
            lambda: self._UDPProtocol(self),
            local_addr=("0.0.0.0", self.cfg["listen_port"]),
            reuse_port=True,
        )

        # Send initial HELLO to bootstrap peers
        await asyncio.sleep(0.2)
        hello = encode_hello()
        for peer in self.peers.values():
            transport.sendto(hello, peer.addr)

        log.info("VPN node started. Local IP: %s  Port: %d",
                 self.cfg["local_ip"], self.cfg["listen_port"])

        # Регистрируем TAP через epoll (не coroutine, просто add_reader)
        self._start_tap_reader()

        try:
            await asyncio.gather(
                self._hole_punch_all(),
                self._heartbeat(),
            )
        finally:
            self.teardown_tap()
