import asyncio
import unittest
from abc import ABC
from typing import Callable, Any, Coroutine
from unittest.mock import AsyncMock, MagicMock

from p2pvpn.core.interfaces import ITransport, INetworkInterface

class TestITransport(unittest.IsolatedAsyncioTestCase):
    async def test_itransport_is_abc(self):
        with self.assertRaises(TypeError):
            ITransport()  # type: ignore

    async def test_itransport_implementation(self):
        class MockTransport(ITransport):
            def __init__(self):
                self.callback = None
                self.sent_data = []

            async def send(self, destination: tuple[str, int], data: bytes) -> None:
                self.sent_data.append((destination, data))

            def packet_received(self, callback: Callable[[tuple[str, int], bytes], Coroutine[Any, Any, None]]) -> None:
                self.callback = callback

            async def trigger_packet(self, destination: tuple[str, int], data: bytes):
                if self.callback:
                    await self.callback(destination, data)

        transport = MockTransport()
        dest = ("127.0.0.1", 12345)
        data = b"hello"
        await transport.send(dest, data)
        self.assertEqual(transport.sent_data, [(dest, data)])

        received_data = []
        async def my_callback(d, data_bytes):
            received_data.append((d, data_bytes))

        transport.packet_received(my_callback)
        await transport.trigger_packet(dest, data)
        self.assertEqual(received_data, [(dest, data)])

    async def test_mocking_capabilities(self):
        mock_transport = MagicMock(spec=ITransport)
        mock_transport.send = AsyncMock()
        
        dest = ("1.2.3.4", 5678)
        data = b"mock data"
        await mock_transport.send(dest, data)
        mock_transport.send.assert_called_once_with(dest, data)

class TestINetworkInterface(unittest.IsolatedAsyncioTestCase):
    async def test_inetwork_interface_is_abc(self):
        with self.assertRaises(TypeError):
            INetworkInterface()  # type: ignore

    async def test_inetwork_interface_implementation(self):
        class MockNetworkInterface(INetworkInterface):
            def __init__(self):
                self.callback = None
                self.written_data = []

            async def write(self, data: bytes) -> None:
                self.written_data.append(data)

            def frame_received(self, callback: Callable[[bytes], Coroutine[Any, Any, None]]) -> None:
                self.callback = callback

            async def trigger_frame(self, data: bytes):
                if self.callback:
                    await self.callback(data)

        ni = MockNetworkInterface()
        data = b"frame data"
        await ni.write(data)
        self.assertEqual(ni.written_data, [data])

        received_frames = []
        async def my_callback(data_bytes):
            received_frames.append(data_bytes)

        ni.frame_received(my_callback)
        await ni.trigger_frame(data)
        self.assertEqual(received_frames, [data])

    async def test_mocking_capabilities_ni(self):
        mock_ni = MagicMock(spec=INetworkInterface)
        mock_ni.write = AsyncMock()
        
        data = b"mock data"
        await mock_ni.write(data)
        mock_ni.write.assert_called_once_with(data)

if __name__ == "__main__":
    unittest.main()
