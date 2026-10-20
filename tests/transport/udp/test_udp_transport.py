import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from p2pvpn.transport.udp.udp_transport import UDPTransport, MAGIC, STUN_MAGIC_COOKIE, BINDING_RESPONSE, ATTR_XOR_MAPPED_ADDRESS
from p2pvpn.core.models.packet_type import PacketType
import struct

class TestUDPTransport(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.transport = UDPTransport()

    def test_encode_decode_packet(self):
        packet_type = PacketType.DATA
        payload = b"hello world"
        encoded = self.transport._encode_packet(packet_type, payload)
        
        # Verify format: [ MAGIC (5) | TYPE (1) | PAYLOAD ]
        self.assertEqual(encoded[:5], MAGIC)
        self.assertEqual(encoded[5], packet_type.value)
        self.assertEqual(encoded[6:], payload)
        
        decoded_type, decoded_payload = self.transport._decode_packet(encoded)
        self.assertEqual(decoded_type, packet_type)
        self.assertEqual(decoded_payload, payload)

    def test_decode_invalid_magic(self):
        bad_data = b'\x00\x00\x00\x00\x00' + b'\x01' + b'payload'
        with self.assertRaisesRegex(ValueError, "Invalid MAGIC"):
            self.transport._decode_packet(bad_data)

    def test_decode_too_short(self):
        with self.assertRaisesRegex(ValueError, "Packet too short"):
            self.transport._decode_packet(b'\xde\xad\xbe\xef\x00')

    def test_decode_invalid_type(self):
        # PacketType has 1 and 2. Let's try 3.
        bad_data = MAGIC + b'\x03' + b'payload'
        with self.assertRaisesRegex(ValueError, "Invalid packet type"):
            self.transport._decode_packet(bad_data)

    def test_parse_stun_response_xor_mapped(self):
        # Construct a valid STUN Binding Response with XOR-MAPPED-ADDRESS
        # txn_id = 12 bytes
        txn_id = b'123456789012'
        # Header: type(2) + len(2) + magic(4) + txn_id(12)
        # BINDING_RESPONSE = 0x0101
        # msg_len = length of attributes
        
        family = 0x01 # IPv4
        port = 12345
        ip = "192.168.1.1"
        ip_bytes = bytes(map(int, ip.split('.')))
        
        # XOR port
        xport = port ^ (STUN_MAGIC_COOKIE >> 16)
        xip = struct.unpack(">I", ip_bytes)[0] ^ STUN_MAGIC_COOKIE
        xip_bytes = struct.pack(">I", xip)
        
        attr_header = struct.pack(">HH", ATTR_XOR_MAPPED_ADDRESS, 8)
        # val[0] is reserved, val[1] is family, val[2:4] is port, val[4:8] is IP
        attr_val = b'\x00' + struct.pack("B", family) + struct.pack(">H", xport) + xip_bytes
        
        msg_len = len(attr_header) + len(attr_val)
        header = struct.pack(">HHI", BINDING_RESPONSE, msg_len, STUN_MAGIC_COOKIE) + txn_id
        full_packet = header + attr_header + attr_val
        
        result = self.transport._parse_response(full_packet, txn_id)
        self.assertEqual(result, (ip, port))

    def test_parse_stun_response_invalid_txn_id(self):
        txn_id = b'123456789012'
        bad_txn_id = b'000000000000'
        header = struct.pack(">HHI", BINDING_RESPONSE, 0, STUN_MAGIC_COOKIE) + bad_txn_id
        result = self.transport._parse_response(header, txn_id)
        self.assertIsNone(result)

    def test_parse_stun_response_invalid_magic(self):
        txn_id = b'123456789012'
        header = struct.pack(">HHI", BINDING_RESPONSE, 0, 0x12345678) + txn_id
        result = self.transport._parse_response(header, txn_id)
        self.assertIsNone(result)

    async def test_send(self):
        mock_transport = MagicMock(spec=asyncio.DatagramTransport)
        self.transport._transport = mock_transport
        destination = ("127.0.0.1", 9999)
        data = b"test data"
        
        await self.transport.send(destination, data)
        
        expected_packet = self.transport._encode_packet(PacketType.DATA, data)
        mock_transport.sendto.assert_called_once_with(expected_packet, destination)

    async def test_hole_punch(self):
        mock_transport = MagicMock(spec=asyncio.DatagramTransport)
        self.transport._transport = mock_transport
        destination = ("127.0.0.1", 9999)
        
        await self.transport.hole_punch(destination)
        
        expected_packet = self.transport._encode_packet(PacketType.HELLO, b'')
        mock_transport.sendto.assert_called_once_with(expected_packet, destination)

    async def test_handle_packet_callback(self):
        callback = AsyncMock()
        self.transport.packet_received(callback)
        
        payload = b"received payload"
        packet = self.transport._encode_packet(PacketType.DATA, payload)
        addr = ("1.2.3.4", 5678)
        
        self.transport._handle_packet(packet, addr)
        
        # Since _handle_packet uses asyncio.create_task, we need to give it a moment
        await asyncio.sleep(0.01)
        
        callback.assert_called_once_with(("1.2.3.4", 5678), PacketType.DATA, payload)

if __name__ == '__main__':
    unittest.main()
