import asyncio
import struct
import ipaddress
from typing import Callable, Any, Coroutine, Tuple, Optional
from p2pvpn.core.interfaces.transport import ITransport
from p2pvpn.core.models.packet_type import PacketType

# Wire format constants
MAGIC = b'\xde\xad\xbe\xef\x00'

# STUN constants
STUN_MAGIC_COOKIE = 0x2112A442
BINDING_REQUEST = 0x0001
BINDING_RESPONSE = 0x0101
BINDING_ERROR = 0x0111
ATTR_MAPPED_ADDRESS = 0x0001
ATTR_XOR_MAPPED_ADDRESS = 0x0020
STUN_HEADER_SIZE = 20

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, transport_wrapper: 'UDPTransport'):
        self.transport_wrapper = transport_wrapper

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        self.transport_wrapper._handle_packet(data, addr)

    def error_received(self, exc: Exception):
        pass

class UDPTransport(ITransport):
    def __init__(self):
        self._callback: Optional[Callable[[Tuple[str, int], PacketType, bytes], Coroutine[Any, Any, None]]] = None
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[asyncio.DatagramProtocol] = None

    def packet_received(self, callback: Callable[[Tuple[str, int], PacketType, bytes], Coroutine[Any, Any, None]]) -> None:
        self._callback = callback

    async def open(self, host: str, port: int):
        loop = asyncio.get_running_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            local_addr=(host, port)
        )

    async def close(self):
        if self._transport:
            self._transport.close()
            self._transport = None
            self._protocol = None

    async def send(self, destination: Tuple[str, int], data: bytes, packet_type: PacketType = PacketType.DATA) -> None:
        if not self._transport:
            raise RuntimeError("Transport is not open")
        packet = self._encode_packet(packet_type, data)
        self._transport.sendto(packet, destination)

    async def hole_punch(self, destination: Tuple[str, int]) -> None:
        if not self._transport:
            raise RuntimeError("Transport is not open")
        packet = self._encode_packet(PacketType.HELLO, b'')
        self._transport.sendto(packet, destination)

    def _encode_packet(self, packet_type: PacketType, payload: bytes) -> bytes:
        return MAGIC + packet_type.value.to_bytes(1, 'big') + payload

    def _decode_packet(self, data: bytes) -> Tuple[PacketType, bytes]:
        if len(data) < 6:
            raise ValueError("Packet too short")
        if data[:5] != MAGIC:
            raise ValueError("Invalid MAGIC")
        
        packet_type_val = data[5]
        try:
            packet_type = PacketType(packet_type_val)
        except ValueError:
            raise ValueError(f"Invalid packet type: {packet_type_val}")
            
        return packet_type, data[6:]

    def _handle_packet(self, data: bytes, addr: Tuple[str, int]):
        try:
            packet_type, payload = self._decode_packet(data)
            if self._callback:
                asyncio.create_task(self._callback((addr[0], addr[1]), packet_type, payload))
        except Exception:
            pass

    def _parse_response(self, data: bytes, txn_id: bytes) -> Optional[Tuple[str, int]]:
        """
        Parses a STUN Binding Response.
        """
        if len(data) < STUN_HEADER_SIZE:
            return None

        msg_type, msg_len, magic = struct.unpack(">HHI", data[:8])
        resp_txn = data[8:20]

        if msg_type == BINDING_ERROR:
            return None
        if msg_type != BINDING_RESPONSE:
            return None
        if magic != STUN_MAGIC_COOKIE:
            return None
        if resp_txn != txn_id:
            return None

        offset = STUN_HEADER_SIZE
        xor_result = None
        mapped_result = None

        while offset + 4 <= len(data):
            attr_type, attr_len = struct.unpack(">HH", data[offset:offset + 4])
            attr_val = data[offset + 4: offset + 4 + attr_len]
            
            if len(attr_val) < attr_len:
                # This might happen if the packet is truncated
                break

            if attr_type == ATTR_XOR_MAPPED_ADDRESS and len(attr_val) >= 8:
                xor_result = self._parse_xor_mapped(attr_val)
            elif attr_type == ATTR_MAPPED_ADDRESS and len(attr_val) >= 8:
                mapped_result = self._parse_mapped(attr_val)

            offset += 4 + attr_len
            if attr_len % 4:
                offset += 4 - (attr_len % 4)

        return xor_result or mapped_result

    def _parse_xor_mapped(self, val: bytes) -> Optional[Tuple[str, int]]:
        family = val[1]
        xport = struct.unpack(">H", val[2:4])[0] ^ (STUN_MAGIC_COOKIE >> 16)
        if family == 0x01:
            xip = struct.unpack(">I", val[4:8])[0] ^ STUN_MAGIC_COOKIE
            ip = str(ipaddress.IPv4Address(xip))
            return ip, xport
        return None

    def _parse_mapped(self, val: bytes) -> Optional[Tuple[str, int]]:
        family = val[1]
        port = struct.unpack(">H", val[2:4])[0]
        if family == 0x01:
            ip = str(ipaddress.IPv4Address(val[4:8]))
            return ip, port
        return None
