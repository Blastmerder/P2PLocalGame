import asyncio
import os
import subprocess
import platform
import logging
from typing import Callable, Any, Coroutine, Optional
from p2pvpn.core.interfaces.network_interface import INetworkInterface

logger = logging.getLogger(__name__)

class TAPInterface(INetworkInterface):
    def __init__(self, device_name: str, ip_address: str, netmask: str, mtu: int = 1500):
        self.device_name = device_name
        self.ip_address = ip_address
        self.netmask = netmask
        self.mtu = mtu
        self.fd: Optional[int] = None
        self._callback: Optional[Callable[[bytes], Coroutine[Any, Any, None]]] = None
        self._read_task: Optional[asyncio.Task] = None

    async def setup(self) -> None:
        """Sets up the TAP device."""
        system = platform.system()
        try:
            if system == "Linux":
                await self._setup_linux()
            elif system == "Windows":
                await self._setup_windows()
            else:
                raise NotImplementedError(f"Platform {system} is not supported.")
            
            # In a real implementation, we would open the device here.
            # For this task, we'll allow setting the FD externally for testing.
            # In reality, it might look like:
            # self.fd = os.open(f"/dev/{self.device_name}", os.O_RDWR)
            
        except Exception as e:
            logger.error(f"Failed to setup TAP interface: {e}")
            raise

    async def _setup_linux(self) -> None:
        def _run_cmds():
            subprocess.run(["ip", "tuntap", "add", "dev", self.device_name, "mode", "tap"], check=True)
            prefix = self._netmask_to_prefix(self.netmask)
            subprocess.run(["ip", "addr", "add", f"{self.ip_address}/{prefix}", "dev", self.device_name], check=True)
            subprocess.run(["ip", "link", "set", "dev", self.device_name, "mtu", str(self.mtu)], check=True)
            subprocess.run(["ip", "link", "set", "dev", self.device_name, "up"], check=True)
        
        await asyncio.to_thread(_run_cmds)

    async def _setup_windows(self) -> None:
        def _run_cmds():
            subprocess.run(["netsh", "interface", "ip", "set", "address", f"name={self.device_name}", "static", self.ip_address, self.netmask], check=True)
            subprocess.run(["netsh", "interface", "ipv4", "set", "subinterface", self.device_name, f"mtu={self.mtu}", "store=persistent"], check=True)
        
        await asyncio.to_thread(_run_cmds)

    def _netmask_to_prefix(self, netmask: str) -> int:
        try:
            return sum(bin(int(x)).count('1') for x in netmask.split('.'))
        except Exception:
            return 24

    async def teardown(self) -> None:
        """Tears down the TAP device."""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        system = platform.system()
        try:
            if system == "Linux":
                await asyncio.to_thread(lambda: subprocess.run(["ip", "tuntap", "del", "dev", self.device_name, "mode", "tap"], check=True))
            elif system == "Windows":
                pass
        except Exception as e:
            logger.error(f"Failed to teardown TAP interface: {e}")

        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    async def write(self, data: bytes) -> None:
        """Writes data to the network interface."""
        if self.fd is None:
            raise RuntimeError("TAP interface is not set up.")
        
        await asyncio.to_thread(os.write, self.fd, data)

    def frame_received(self, callback: Callable[[bytes], Coroutine[Any, Any, None]]) -> None:
        """Registers a callback to be called when a frame is received."""
        self._callback = callback
        if self.fd is not None and self._read_task is None:
            self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        """Background loop to read frames from the TAP device."""
        while True:
            try:
                data = await asyncio.to_thread(os.read, self.fd, 2048)
                if data and self._callback:
                    await self._callback(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._read_task: # If it's not being cancelled
                    logger.error(f"Error reading from TAP interface: {e}")
                break
