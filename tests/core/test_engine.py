import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta

from p2pvpn.core.engine import Engine
from p2pvpn.core.interfaces.transport import ITransport
from p2pvpn.core.interfaces.network_interface import INetworkInterface
from p2pvpn.core.peer_manager import PeerManager
from p2pvpn.core.models.vpn_config import VPNConfig
from p2pvpn.core.models.packet_type import PacketType
from p2pvpn.core.models.peer import Peer, PeerState

class TestEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_transport = MagicMock(spec=ITransport)
        self.mock_transport.send = AsyncMock()
        self.mock_transport.hole_punch = AsyncMock()
        # packet_received is used to register a callback.
        # We'll capture the callback.
        self.transport_callbacks = []
        self.mock_transport.packet_received.side_effect = lambda cb: self.transport_callbacks.append(cb)
    
        self.mock_network_interface = MagicMock(spec=INetworkInterface)
        self.mock_network_interface.write = AsyncMock()
        self.network_callbacks = []
        self.mock_network_interface.frame_received.side_effect = lambda cb: self.network_callbacks.append(cb)
    
        self.mock_peer_manager = MagicMock(spec=PeerManager)
        self.mock_config = VPNConfig(
            local_ip="10.0.0.1",
            listen_port=5555,
            tap_name="tap0",
            prefix=24
        )
    
        self.engine = Engine(
            transport=self.mock_transport,
            network_interface=self.mock_network_interface,
            peer_manager=self.mock_peer_manager,
            config=self.mock_config
        )

    async def test_start_registers_callbacks(self):
        await self.engine.start()
        self.mock_transport.packet_received.assert_called_once()
        self.mock_network_interface.frame_received.assert_called_once()
        self.assertTrue(self.engine._running)

    async def test_stop(self):
        await self.engine.start()
        await self.engine.stop()
        self.assertFalse(self.engine._running)

    async def test_packet_to_frame_routing(self):
        await self.engine.start()
        
        peer = Peer(peer_id="peer1", address="1.2.3.4", port=1234)
        self.mock_peer_manager.get_peer_by_address.return_value = peer
        
        # Simulate receiving a DATA packet
        payload = b"hello world"
        address = ("1.2.3.4", 1234)
        
        # Call the registered callback
        await self.transport_callbacks[0](address, PacketType.DATA, payload)
        
        self.mock_peer_manager.update_peer_activity.assert_called_with("peer1")
        self.mock_network_interface.write.assert_called_with(payload)

    async def test_frame_to_packet_routing(self):
        await self.engine.start()
        
        # Setup active peers
        peer1 = Peer(peer_id="peer1", address="1.1.1.1", port=1111)
        peer2 = Peer(peer_id="peer2", address="2.2.2.2", port=2222)
        self.mock_peer_manager.get_active_peers.return_value = [peer1, peer2]
        
        # Simulate receiving a frame from the network interface
        frame = b"new frame data"
        
        # Call the registered callback
        await self.network_callbacks[0](frame)
        
        # Check if DATA packet was sent to all active peers
        self.mock_transport.send.assert_any_call(("1.1.1.1", 1111), frame)
        self.mock_transport.send.assert_any_call(("2.2.2.2", 2222), frame)
        self.assertEqual(self.mock_transport.send.call_count, 2)

    async def test_hole_punching_workflow(self):
        await self.engine.start()
        
        peer1 = Peer(peer_id="peer1", address="1.1.1.1", port=1111)
        self.mock_peer_manager.get_all_peers.return_value = [peer1]
        
        await self.engine.perform_hole_punching()
        
        # Expected: MAGIC + HELLO + b''
        # Wait, engine.perform_hole_punching calls transport.hole_punch
        expected_hole_punch_packet = b'' # This depends on the implementation of hole_punch
        # Given the previous test expected: bytes([PacketType.HELLO.value]) + b"peer1"
        # but that's actually for the heartbeat?
        # Let's check perform_hole_punching in Engine
        # It calls self.transport.hole_punch((peer.address, peer.port))
        self.mock_transport.hole_punch.assert_called_with(("1.1.1.1", 1111))

    async def test_hello_packet_discovers_new_peer(self):
        await self.engine.start()
        
        self.mock_peer_manager.get_peer_by_address.return_value = None
        
        # Simulate receiving a HELLO packet from an unknown address
        peer_id = "new_peer"
        data = peer_id.encode('utf-8')
        address = ("5.6.7.8", 5678)
        
        await self.transport_callbacks[0](address, PacketType.HELLO, data)
        
        # Verify a new peer was added
        called_peer = self.mock_peer_manager.add_peer.call_args[0][0]
        self.assertEqual(called_peer.peer_id, peer_id)
        self.assertEqual(called_peer.address, "5.6.7.8")
        self.assertEqual(called_peer.port, 5678)
        self.assertEqual(called_peer.state, PeerState.ALIVE)

    async def test_hello_packet_updates_existing_peer(self):
        await self.engine.start()
        
        peer = Peer(peer_id="existing_peer", address="1.1.1.1", port=1111)
        self.mock_peer_manager.get_peer_by_address.return_value = peer
        
        # Simulate receiving a HELLO packet from an existing address
        data = b"existing_peer"
        address = ("1.1.1.1", 1111)
        
        await self.transport_callbacks[0](address, PacketType.HELLO, data)
        
        self.mock_peer_manager.update_peer_activity.assert_called_with("existing_peer")

    async def test_unknown_peer_data_packet(self):
        await self.engine.start()
        
        self.mock_peer_manager.get_peer_by_address.return_value = None
        
        # Simulate receiving a DATA packet from an unknown address
        data = b"some data"
        address = ("9.9.9.9", 9999)
        
        await self.transport_callbacks[0](address, PacketType.DATA, data)
        
        self.mock_network_interface.write.assert_not_called()

    async def test_packet_received_error_handling(self):
        await self.engine.start()
        
        # Simulate an error during packet processing
        self.mock_peer_manager.get_peer_by_address.side_effect = Exception("Unexpected error")
        
        data = b"data"
        address = ("1.1.1.1", 1111)
        
        # This should not raise an exception out of the callback
        try:
            await self.transport_callbacks[0](address, PacketType.DATA, data)
        except Exception as e:
            self.fail(f"_on_packet_received raised {e} instead of handling it.")

    async def test_frame_received_error_handling(self):
        await self.engine.start()
        
        # Simulate an error during frame processing
        self.mock_peer_manager.get_active_peers.side_effect = Exception("Unexpected error")
        
        # This should not raise an exception out of the callback
        try:
            await self.network_callbacks[0](b"frame")
        except Exception as e:
            self.fail(f"_on_frame_received raised {e} instead of handling it.")

if __name__ == '__main__':
    unittest.main()
