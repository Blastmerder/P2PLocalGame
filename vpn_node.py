#!/usr/bin/env python3
"""
P2P L2 VPN Node — creates a virtual Ethernet (TAP) interface
and tunnels raw Ethernet frames over UDP to all known peers.

Cross-platform: Linux (/dev/net/tun) and Windows (TAP-Windows6).
See tap.py for platform-specific details.
"""

import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Dict, Optional

from tap import TAPDevice
from peer import Peer
from constants import *


def _make_udp_socket(port: int) -> socket.socket:
    """
    Создать UDP-сокет, готовый к биндингу на 0.0.0.0:port.

    SO_REUSEADDR обязательно — на Windows без него bind() падает
    с WSAEADDRINUSE если STUN-сокет ещё не до конца закрыт.
    SO_REUSEPORT — где доступно (Linux/BSD), позволяет нескольким
    сокетам слушать тот же порт одновременно.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
    sock.setblocking(False)
    sock.bind(("0.0.0.0", port))
    return sock


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

HELLO = MAGIC + bytes([TYPE_HELLO])

def encode_data(frame: bytes) -> bytes:
    return MAGIC + bytes([TYPE_DATA]) + frame


def decode(packet: bytes):
    """Returns (type, payload) or (None, None) if invalid."""
    if len(packet) < MAGIC_LEN + 1 or packet[:MAGIC_LEN] != MAGIC:
        return None, None
    ptype = packet[MAGIC_LEN]
    payload = packet[MAGIC_LEN + 1:]
    return ptype, payload


# ─────────────────────────────────────────────────────
# UDP protocol
# ────────────────────────────────────────────────────────────
class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, node):
        self.node = node

    def connection_made(self, transport):
        self.node._transport = transport
        log.info("UDP socket ready on port %d", self.node.cfg["listen_port"])

    def datagram_received(self, data, addr):
        self.node._on_udp(data, addr)

    def error_received(self, exc):
        log.warning("UDP error: %s", exc)


# ──────────────────────────────────────────────────────────────
# Main VPN node
# ──────────────────────────────────────────────────────────────
class VPNNode:
    def __init__(self, config, tap):
        self.cfg = config
        self.peers: Dict[tuple, Peer] = {}   # (host, port) → Peer
        self._tap = None                     # tap.TAPDevice
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tap = tap

    # ── Setup ────────────────────────────────────────────────

#    def setup_tap(self):
#        self._tap = TAPDevice(
#            name=self.cfg.get("tap_name", "tap0"),
#            ip=self.cfg["local_ip"],
#            prefix=self.cfg.get("prefix", 24),
#            mtu=self.cfg.get("mtu", TAP_MTU),
#        )
#        self._tap.setup()
    
    def add_peer(self, peer: Peer):
        addr = peer.addr
        self.peers[addr] = peer
        log.info("Registered initial peer: %s:%d", addr[0], addr[1])

    def _add_initial_peers(self):
        for hp in self.cfg.get("peers", []):
            host, port = hp["host"], hp["port"]
            self.add_peer(Peer(host=host, port=port))

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

        self.peers[addr].touch()

        if ptype == TYPE_DATA:
            self._tap.write(payload)
            # Learn MAC from Ethernet src field (bytes 6-12)
            if len(payload) >= 12 and peer.mac is None:
                peer.mac = payload[6:12]
                log.info("Learned MAC for %s: %s", addr, peer)

        elif ptype == TYPE_HELLO:
            log.debug("HELLO from %s:%d", *addr)


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

        log.info("Starting hole punch for %d peer(s)…", len(self.peers))
        
        # Начинаем отправлять всем HELLO, потому что надо для создания открытого порта на роутере
        for i in range(PUNCH_COUNT):
            self.send_to_peers(HELLO)
            await asyncio.sleep(PUNCH_INTERVAL)
        
        confirmed = [p for p in self.peers.values() if p.confirmed]
        
        if confirmed:
            log.info("Hole punch OK: %d/%d peers responded",
                     len(confirmed), len(self.peers))
        else:
            log.warning(
                "Hole punch: no peers responded after %d attempts. "
                "Check address, firewall, and NAT type.", PUNCH_COUNT)

    # ── Send Data to All Peers ───────────────────────────────
    
    def send_to_peers(self, data):
        for peer in list(self.peers.values()):
            if self._transport:
                self._transport.sendto(data, peer.addr)    
                log.debug("Send to %s, data, %s", peer.addr, data)

    # ── HeartBeat ──────────────────────────────────────────── 

    async def _heartbeat(self):
        """Periodically send HELLO to all known peers to keep them alive."""
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            self.send_to_peers(HELLO)
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
        # todo: Обновить запуск, без каких либо зовисимостей, либо с выдачей зависимостей при запуске и их переиспользование, для упращения процесса  

        self._loop = asyncio.get_running_loop()
        self._add_initial_peers()

        # UDP-сокет создаём вручную, чтобы выставить SO_REUSEADDR
        # (+ SO_REUSEPORT на Linux). Это лечит WSAEADDRINUSE на Windows
        # после закрытия STUN-сокета: asyncio.transport.close() освобождает
        # порт асинхронно, и без REUSEADDR следующий bind() падает.
        self._transport, _ = await self._loop.create_datagram_endpoint(
            lambda: UDPProtocol(self),
            sock=_make_udp_socket(self.cfg["listen_port"]),
        )

        # Send initial HELLO to bootstrap peers
        await asyncio.sleep(0.2)
        
        self.send_to_peers(HELLO)

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
            pass
