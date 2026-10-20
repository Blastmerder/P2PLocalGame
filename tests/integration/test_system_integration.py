import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import os

from p2pvpn.core.engine import Engine
from p2pvpn.transport.udp.udp_transport import UDPTransport, UDPProtocol
from p2pvpn.interface.tap.tap_interface import TAPInterface
from p2pvpn.core.peer_manager import PeerManager
from p2pvpn.core.models.vpn_config import VPNConfig
from p2pvpn.core.models.packet_type import PacketType
from p2pvpn.core.models.peer import Peer, PeerState

class TestSystemIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = VPNConfig(
            local_ip="10.0.0.1",
            listen_port=5555,
            tap_name="tap0",
            prefix=24,
            keepalive_interval=0.05
        )
        
        self.peer_manager = PeerManager()
        self.transport = UDPTransport()
        self.tap = TAPInterface(device_name="tap0", ip_address="10.0.0.1", netmask="255.255.255.0", mtu=1500)
        self.tap.fd = 999
        
        self.engine = Engine(
            transport=self.transport,
            network_interface=self.tap,
            peer_manager=self.peer_manager,
            config=self.config
        )

        # Mocks
        self.mock_dt = MagicMock()
        self.mock_protocol = MagicMock(spec=UDPProtocol)
        
        # Patching loop.create_datagram_endpoint
        self.loop = asyncio.get_running_loop()
        self.endpoint_patcher = patch.object(self.loop, 'create_datagram_endpoint', new_callable=AsyncMock)
        self.mock_create_endpoint = self.endpoint_patcher.start()
        self.mock_create_endpoint.return_value = (self.mock_dt, self.mock_protocol)

        # Patching os for TAP
        self.os_read_patcher = patch('os.read')
        self.mock_os_read = self.os_read_patcher.start()
        self.os_write_patcher = patch('os.write')
        self.mock_os_write = self.os_write_patcher.start()
        self.os_close_patcher = patch('os.close')
        self.mock_os_close = self.os_close_patcher.start()

    async def asyncTearDown(self):
        # Try to stop engine safely
        try:
            await self.engine.stop()
        except:
            pass
        self.endpoint_patcher.stop()
        self.os_read_patcher.stop()
        self.os_write_patcher.stop()
        self.os_close_patcher.stop()

    async def test_full_integration_flow(self):
        """
        Verifies the full data flow:
        1. TAP -> Engine -> UDP (Data packet received from TAP is sent to peers)
        2. UDP -> Engine -> TAP (Data packet received from UDP is written to TAP)
        """
        # 1. Setup - We'll manually start to avoid background read loops in TAP
        await self.transport.open("127.0.0.1", 0)
        # Manually register callbacks instead of calling start() to avoid TAP's read loop
        self.transport.packet_received(self.engine._on_packet_received)
        self.tap.frame_received(self.engine._on_frame_received)
        self.engine._running = True
        
        # Setup an active peer
        peer = Peer(peer_id="peer1", address="1.2.3.4", port=5678, state=PeerState.ALIVE)
        self.peer_manager.add_peer(peer)
        
        # 2. Test TAP -> Engine -> UDP
        test_frame = b"from tap to udp"
        # Simulate frame received from TAP by calling the callback directly
        await self.engine._on_frame_received(test_frame)
        
        # Check if UDP transport sent the packet
        expected_udp_packet = b'\xde\xad\xbe\xef\x00' + b'\x02' + test_frame
        self.mock_dt.sendto.assert_called_with(expected_udp_packet, ("1.2.3.4", 5678))
        
        # 3. Test UDP -> Engine -> TAP
        test_payload = b"from udp to tap"
        udp_packet_data = b'\xde\xad\xbe\xef\x00' + b'\x02' + test_payload
        
        # Manually trigger the handler on the transport
        self.transport._handle_packet(udp_packet_data, ("1.2.3.4", 5678))
        await asyncio.sleep(0.05)
        
        # Check if os.write was called with the payload
        self.mock_os_write.assert_called_with(999, test_payload)

    async def test_hole_punching_and_hello_flow(self):
        """
        Verifies hole punching and HELLO packet discovery.
        """
        await self.transport.open("127.0.0.1", 0)
        # Manually register callbacks
        self.transport.packet_received(self.engine._on_packet_received)
        self.tap.frame_received(self.engine._on_frame_received)
        self.engine._running = True
        
        # 1. Test Hole Punching
        peer = Peer(peer_id="remote_peer", address="5.6.7.8", port=1234, state=PeerState.ALIVE)
        self.peer_manager.add_peer(peer)
        
        await self.engine.perform_hole_punching()
        
        # Check if hole_punch was called
        # Expected: MAGIC + HELLO + b''
        expected_hole_punch_packet = b'\xde\xad\xbe\xef\x00' + b'\x01' + b''
        self.mock_dt.sendto.assert_called_with(expected_hole_punch_packet, ("5.6.7.8", 1234))
        
        # 2. Test HELLO packet discovery
        new_peer_id = "new_peer"
        hello_packet = b'\xde\xad\xbe\xef\x00' + b'\x01' + new_peer_id.encode('utf-8')
        self.transport._handle_packet(hello_packet, ("9.9.9.9", 9999))
        await asyncio.sleep(0.05)
        
        # Verify new peer discovered
        discovered_peer = self.peer_manager.get_peer_by_address("9.9.9.9", 9999)
        self.assertIsNotNone(discovered_peer)
        self.assertEqual(discovered_peer.peer_id, new_peer_id)

if __name__ == '__main__':
    unittest.main()
