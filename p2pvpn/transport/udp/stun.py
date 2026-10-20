"""
stun.py — STUN (Session Traversal Utilities for NAT) implementation.

Provides functionality to discover a node's public IP address and port
by communicating with STUN servers.
"""

import asyncio
import ipaddress
import logging
import os
import random
import socket
import struct
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Public STUN servers (fallback list)
# ──────────────────────────────────────────────────────────────
DEFAULT_SERVERS: list[tuple[str, int]] = [
    ("stun.l.google.com",       19302),
    ("stun1.l.google.com",      19302),
    ("stun2.l.google.com",      19302),
    ("stun.cloudflare.com",     3478),
    ("stun.stunprotocol.org",   3478),
    ("stun.nextcloud.com",      3478),
    ("stun.voip.blackberry.com", 3478),
]

# ──────────────────────────────────────────────────────────────
# RFC 5389 constants
# ──────────────────────────────────────────────────────────────
STUN_MAGIC_COOKIE    = 0x2112A442          # fixed magic cookie
BINDING_REQUEST      = 0x0001
BINDING_RESPONSE     = 0x0101
BINDING_ERROR        = 0x0111

ATTR_MAPPED_ADDRESS     = 0x0001
ATTR_XOR_MAPPED_ADDRESS = 0x0020

HEADER_SIZE = 20   # bytes: type(2) + length(2) + cookie(4) + txn_id(12)


# ──────────────────────────────────────────────────────────────
# STUN request result
# ──────────────────────────────────────────────────────────────
@dataclass
class STUNResult:
    public_ip:   str
    public_port: int
    server_used: str

    def __str__(self):
        return f"{self.public_ip}:{self.public_port}  (via {self.server_used})"


# ──────────────────────────────────────────────────────────────
# STUN packet assembly/parsing
# ──────────────────────────────────────────────────────────────
def _build_binding_request() -> tuple[bytes, bytes]:
    """Return (packet, transaction_id)."""
    txn_id = os.urandom(12)
    # Header: msg_type(2) + msg_len(2) + magic(4) + txn_id(12)
    header = struct.pack(">HHI", BINDING_REQUEST, 0, STUN_MAGIC_COOKIE) + txn_id
    return header, txn_id


def _parse_response(data: bytes, txn_id: bytes) -> Optional[tuple[str, int]]:
    """
    Parse STUN Binding Response.
    Returns (ip, port) or None on failure.
    """
    if len(data) < HEADER_SIZE:
        logger.debug("STUN response too short: %d bytes", len(data))
        return None

    msg_type, msg_len, magic = struct.unpack(">HHI", data[:8])
    resp_txn = data[8:20]

    if msg_type == BINDING_ERROR:
        logger.debug("STUN server returned error response")
        return None
    if msg_type != BINDING_RESPONSE:
        logger.debug("Unexpected STUN message type: 0x%04x", msg_type)
        return None
    if magic != STUN_MAGIC_COOKIE:
        logger.debug("STUN magic cookie mismatch")
        return None
    if resp_txn != txn_id:
        logger.debug("STUN transaction ID mismatch")
        return None

    # Parse attributes
    offset = HEADER_SIZE
    xor_result    = None
    mapped_result = None

    while offset + 4 <= len(data):
        attr_type, attr_len = struct.unpack(">HH", data[offset:offset + 4])
        attr_val = data[offset + 4: offset + 4 + attr_len]
        offset += 4 + attr_len
        # alignment to 4 bytes
        if attr_len % 4:
            offset += 4 - (attr_len % 4)

        if attr_type == ATTR_XOR_MAPPED_ADDRESS and len(attr_val) >= 8:
            xor_result = _parse_xor_mapped(attr_val)

        elif attr_type == ATTR_MAPPED_ADDRESS and len(attr_val) >= 8:
            mapped_result = _parse_mapped(attr_val)

    # XOR-MAPPED-ADDRESS preferred (RFC 5389 recommends)
    return xor_result or mapped_result


def _parse_xor_mapped(val: bytes) -> Optional[tuple[str, int]]:
    """Parse XOR-MAPPED-ADDRESS attribute."""
    family = val[1]
    xport  = struct.unpack(">H", val[2:4])[0] ^ (STUN_MAGIC_COOKIE >> 16)

    if family == 0x01:  # IPv4
        xip = struct.unpack(">I", val[4:8])[0] ^ STUN_MAGIC_COOKIE
        ip  = str(ipaddress.IPv4Address(xip))
        return ip, xport

    if family == 0x02:  # IPv6 (future use)
        logger.debug("IPv6 XOR-MAPPED-ADDRESS — not yet handled")
        return None

    return None


def _parse_mapped(val: bytes) -> Optional[tuple[str, int]]:
    """Parse MAPPED-ADDRESS attribute (legacy format)."""
    family = val[1]
    port   = struct.unpack(">H", val[2:4])[0]

    if family == 0x01:  # IPv4
        ip = str(ipaddress.IPv4Address(val[4:8]))
        return ip, port

    return None


# ──────────────────────────────────────────────────────────────
# Async UDP protocol for asyncio
# ──────────────────────────────────────────────────────────────
class _STUNProtocol(asyncio.DatagramProtocol):
    def __init__(self, txn_id: bytes, future: asyncio.Future):
        self._txn_id = txn_id
        self._fut    = future

    def datagram_received(self, data, addr):
        if self._fut.done():
            return
        result = _parse_response(data, self._txn_id)
        if result:
            self._fut.set_result(result)
        else:
            self._fut.set_exception(ValueError("Invalid STUN response"))

    def error_received(self, exc):
        if not self._fut.done():
            self._fut.set_exception(exc)

    def connection_lost(self, exc):
        if not self._fut.done():
            self._fut.set_exception(ConnectionError("STUN connection lost"))


# ──────────────────────────────────────────────────────────────
# Main async function
# ──────────────────────────────────────────────────────────────
async def discover_async(
    servers: Optional[list[tuple[str, int]]] = None,
    timeout: float = 3.0,
    local_port: int = 0,
) -> STUNResult:
    """
    Determine public IP:port via STUN.

    Args:
        servers: list of (host, port) STUN servers; defaults to DEFAULT_SERVERS
        timeout: timeout per server (seconds)
        local_port: local UDP port (0 = auto-allocate)

    Returns:
        STUNResult or raises RuntimeError if all servers are unreachable.
    """
    if servers is None:
        servers = DEFAULT_SERVERS

    loop = asyncio.get_running_loop()
    last_error: Exception = RuntimeError("No STUN servers configured")

    for host, port in servers:
        label = f"{host}:{port}"
        try:
            logger.debug("Trying STUN server %s …", label)

            # Resolve host beforehand (to catch DNS errors gracefully)
            infos = await loop.getaddrinfo(
                host, port,
                type=socket.SOCK_DGRAM,
                proto=socket.IPPROTO_UDP,
            )
            if not infos:
                raise OSError(f"DNS lookup failed for {host}")

            server_addr = (infos[0][4][0], port)   # first IPv4 address

            request, txn_id = _build_binding_request()
            fut: asyncio.Future = loop.create_future()

            # Bind socket manually with SO_REUSEADDR (+ REUSEPORT if available).
            # Without SO_REUSEADDR on Windows, the VPN socket might fail to 
            # bind to the same port after asyncio.transport.close() due to 
            # TIME_WAIT / asynchronous closing.
            # 
            # IMPORTANT: DO NOT use sock.connect(server_addr). On Windows
            # ProactorEventLoop in Python 3.14, if the socket is connected,
            # transport.sendto(data) uses WSASendTo with addr=None
            # and fails ("argument 4 must be tuple, not None"). 
            # Pass address explicitly to transport.sendto(request, server_addr).
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except (AttributeError, OSError):
                    pass
            sock.setblocking(False)
            sock.bind(("0.0.0.0", local_port))
            transport, _ = await loop.create_datagram_endpoint(
                lambda: _STUNProtocol(txn_id, fut),
                sock=sock,
            )

            try:
                transport.sendto(request, server_addr)
                ip, pub_port = await asyncio.wait_for(fut, timeout=timeout)
                logger.info("STUN success via %s → %s:%d", label, ip, pub_port)
                return STUNResult(
                    public_ip=ip,
                    public_port=pub_port,
                    server_used=label,
                )
            finally:
                transport.close()

        except asyncio.TimeoutError:
            logger.debug("STUN timeout on %s", label)
            last_error = TimeoutError(f"STUN server {label} timed out")
        except Exception as exc:
            logger.debug("STUN error on %s: %s", label, exc)
            last_error = exc

    raise RuntimeError(
        f"All STUN servers failed. Last error: {last_error}"
    )


# ──────────────────────────────────────────────────────────────
# Sync wrapper (useful for single calls without explicit loop management)
# ──────────────────────────────────────────────────────────────
def discover(
    servers: Optional[list[tuple[str, int]]] = None,
    timeout: float = 3.0,
    local_port: int = 0,
) -> STUNResult:
    """Synchronous version of discover_async. Manages its own event loop."""
    return asyncio.run(discover_async(servers, timeout, local_port))
