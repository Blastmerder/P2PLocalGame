#!/usr/bin/env python3
"""
P2P L2 VPN Node — creates a virtual Ethernet (TAP) interface
and tunnels raw Ethernet frames over UDP to all known peers.

Cross-platform: Linux (/dev/net/tun) and Windows (TAP-Windows6).
See tap.py for platform-specific details.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

from tap import TAPDevice

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────
ETH_PROTO_ARP = 0x0806

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
        self._tap = None                     # tap.TAPDevice
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Setup ────────────────────────────────────────────────

    def setup_tap(self):
        self._tap = TAPDevice(
            name=self.cfg.get("tap_name", "tap0"),
            ip=self.cfg["local_ip"],
            prefix=self.cfg.get("prefix", 24),
            mtu=self.cfg.get("mtu", TAP_MTU),
        )
        self._tap.setup()

    def teardown_tap(self):
        if self._tap is not None:
            self._tap.teardown()

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
        """Записать Ethernet-фрейм в TAP (через платформенный backend)."""
        self._tap.write(frame)

    def _on_tap_frame(self, frame: bytes):
        """Callback из TAP: один готовый Ethernet-фрейм → всем пирам."""
        log.debug("TAP → %d bytes, forwarding to peers", len(frame))
        self._broadcast(frame)

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

        # Create UDP socket. SO_REUSEPORT есть только на Linux/BSD —
        # используем его чтобы занять порт сразу после STUN-сокета без
        # ожидания TIME_WAIT. На Windows flag не поддерживается asyncio,
        # но там достаточно того, что STUN-сокет уже закрыт.
        endpoint_kwargs = dict(
            local_addr=("0.0.0.0", self.cfg["listen_port"]),
        )
        import sys as _sys
        if _sys.platform != "win32":
            endpoint_kwargs["reuse_port"] = True
        transport, _ = await self._loop.create_datagram_endpoint(
            lambda: self._UDPProtocol(self),
            **endpoint_kwargs,
        )

        # Send initial HELLO to bootstrap peers
        await asyncio.sleep(0.2)
        hello = encode_hello()
        for peer in self.peers.values():
            transport.sendto(hello, peer.addr)

        log.info("VPN node started. Local IP: %s  Port: %d",
                 self.cfg["local_ip"], self.cfg["listen_port"])

        # Запускаем TAP-ридер: epoll на Linux / поток на Windows
        self._tap.start_reading(self._loop, self._on_tap_frame)

        try:
            await asyncio.gather(
                self._hole_punch_all(),
                self._heartbeat(),
            )
        finally:
            self.teardown_tap()
