import asyncio
import os
import subprocess
import platform
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from p2pvpn.interface.tap.tap_interface import TAPInterface

class TestTAPInterface(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.device_name = "tap0"
        self.ip_address = "192.168.1.1"
        self.netmask = "255.255.255.0"
        self.mtu = 1500
        self.tap = TAPInterface(self.device_name, self.ip_address, self.netmask, self.mtu)

    @patch("platform.system")
    @patch("subprocess.run")
    async def test_setup_linux_success(self, mock_run, mock_system):
        print("Running test_setup_linux_success")
        mock_system.return_value = "Linux"
        mock_run.return_value = MagicMock(returncode=0)
        
        await self.tap.setup()
        
        # Verify Linux commands
        expected_calls = [
            unittest.mock.call(["ip", "tuntap", "add", "dev", self.device_name, "mode", "tap"], check=True),
            unittest.mock.call(["ip", "addr", "add", f"{self.ip_address}/24", "dev", self.device_name], check=True),
            unittest.mock.call(["ip", "link", "set", "dev", self.device_name, "mtu", str(self.mtu)], check=True),
            unittest.mock.call(["ip", "link", "set", "dev", self.device_name, "up"], check=True),
        ]
        mock_run.assert_has_calls(expected_calls, any_order=False)

    @patch("platform.system")
    @patch("subprocess.run")
    async def test_setup_windows_success(self, mock_run, mock_system):
        print("Running test_setup_windows_success")
        mock_system.return_value = "Windows"
        mock_run.return_value = MagicMock(returncode=0)
        
        await self.tap.setup()
        
        # Verify Windows commands
        expected_calls = [
            unittest.mock.call(["netsh", "interface", "ip", "set", "address", f"name={self.device_name}", "static", self.ip_address, self.netmask], check=True),
            unittest.mock.call(["netsh", "interface", "ipv4", "set", "subinterface", self.device_name, f"mtu={self.mtu}", "store=persistent"], check=True),
        ]
        mock_run.assert_has_calls(expected_calls, any_order=False)

    @patch("platform.system")
    async def test_setup_unsupported_platform(self, mock_system):
        print("Running test_setup_unsupported_platform")
        mock_system.return_value = "Darwin" # macOS
        with self.assertRaises(NotImplementedError):
            await self.tap.setup()

    @patch("subprocess.run")
    @patch("platform.system")
    async def test_teardown_linux_success(self, mock_system, mock_run):
        print("Running test_teardown_linux_success")
        mock_system.return_value = "Linux"
        mock_run.return_value = MagicMock(returncode=0)
        
        await self.tap.teardown()
        
        mock_run.assert_called_with(["ip", "tuntap", "del", "dev", self.device_name, "mode", "tap"], check=True)

    @patch("os.write")
    @patch("asyncio.to_thread")
    async def test_write_success(self, mock_to_thread, mock_os_write):
        print("Running test_write_success")
        self.tap.fd = 99
        data = b"hello tap"
        
        await self.tap.write(data)
        
        mock_to_thread.assert_called_with(os.write, 99, data)

    async def test_write_without_setup(self):
        print("Running test_write_without_setup")
        with self.assertRaises(RuntimeError):
            await self.tap.write(b"data")

    @patch("os.read")
    @patch("asyncio.to_thread")
    async def test_frame_received_callback(self, mock_to_thread, mock_os_read):
        print("Running test_frame_received_callback")
        # Setup
        self.tap.fd = 99
        callback = AsyncMock()
        data = b"incoming frame"
        
        # Mock os.read via to_thread
        # The first call returns data, the second call raises CancelledError
        mock_to_thread.side_effect = [data, asyncio.CancelledError()]
        
        self.tap.frame_received(callback)
        
        # We need to give it a moment to run the task
        await asyncio.sleep(0.1)
        
        callback.assert_called_with(data)
        
        # Cleanup
        if self.tap._read_task:
            self.tap._read_task.cancel()
            try:
                await self.tap._read_task
            except asyncio.CancelledError:
                pass

    @patch("os.close")
    @patch("subprocess.run")
    async def test_teardown_closes_fd(self, mock_run, mock_os_close):
        print("Running test_teardown_closes_fd")
        self.tap.fd = 99
        await self.tap.teardown()
        mock_os_close.assert_called_once_with(99)
        self.assertIsNone(self.tap.fd)

if __name__ == "__main__":
    unittest.main()
