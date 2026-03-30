"""
stun_client.py — минимальный STUN-клиент (RFC 5389)

Определяет публичный IP и порт узла путём отправки Binding Request
на публичные STUN-серверы. Никаких внешних зависимостей.

Поддерживает:
  • Несколько fallback-серверов (опрашиваются по очереди)
  • Async и sync интерфейс
  • Разбор атрибутов MAPPED-ADDRESS и XOR-MAPPED-ADDRESS
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

log = logging.getLogger("vpn.stun")

# ──────────────────────────────────────────────────────────────
# Публичные STUN-серверы (fallback-список)
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
# RFC 5389 константы
# ──────────────────────────────────────────────────────────────
STUN_MAGIC_COOKIE    = 0x2112A442          # фиксированное магическое число
BINDING_REQUEST      = 0x0001
BINDING_RESPONSE     = 0x0101
BINDING_ERROR        = 0x0111

ATTR_MAPPED_ADDRESS     = 0x0001
ATTR_XOR_MAPPED_ADDRESS = 0x0020

HEADER_SIZE = 20   # байт: type(2) + length(2) + cookie(4) + txn_id(12)


# ──────────────────────────────────────────────────────────────
# Результат STUN-запроса
# ──────────────────────────────────────────────────────────────
@dataclass
class STUNResult:
    public_ip:   str
    public_port: int
    server_used: str

    def __str__(self):
        return f"{self.public_ip}:{self.public_port}  (via {self.server_used})"


# ──────────────────────────────────────────────────────────────
# Сборка / разбор STUN-пакетов
# ──────────────────────────────────────────────────────────────
def _build_binding_request() -> tuple[bytes, bytes]:
    """Вернуть (пакет, transaction_id)."""
    txn_id = os.urandom(12)
    # Header: msg_type(2) + msg_len(2) + magic(4) + txn_id(12)
    header = struct.pack(">HHI", BINDING_REQUEST, 0, STUN_MAGIC_COOKIE) + txn_id
    return header, txn_id


def _parse_response(data: bytes, txn_id: bytes) -> Optional[tuple[str, int]]:
    """
    Разобрать STUN Binding Response.
    Возвращает (ip, port) или None при ошибке.
    """
    if len(data) < HEADER_SIZE:
        log.debug("STUN response too short: %d bytes", len(data))
        return None

    msg_type, msg_len, magic = struct.unpack(">HHI", data[:8])
    resp_txn = data[8:20]

    if msg_type == BINDING_ERROR:
        log.debug("STUN server returned error response")
        return None
    if msg_type != BINDING_RESPONSE:
        log.debug("Unexpected STUN message type: 0x%04x", msg_type)
        return None
    if magic != STUN_MAGIC_COOKIE:
        log.debug("STUN magic cookie mismatch")
        return None
    if resp_txn != txn_id:
        log.debug("STUN transaction ID mismatch")
        return None

    # Разобрать атрибуты
    offset = HEADER_SIZE
    xor_result    = None
    mapped_result = None

    while offset + 4 <= len(data):
        attr_type, attr_len = struct.unpack(">HH", data[offset:offset + 4])
        attr_val = data[offset + 4: offset + 4 + attr_len]
        offset += 4 + attr_len
        # выравнивание по 4 байтам
        if attr_len % 4:
            offset += 4 - (attr_len % 4)

        if attr_type == ATTR_XOR_MAPPED_ADDRESS and len(attr_val) >= 8:
            xor_result = _parse_xor_mapped(attr_val)

        elif attr_type == ATTR_MAPPED_ADDRESS and len(attr_val) >= 8:
            mapped_result = _parse_mapped(attr_val)

    # XOR-MAPPED-ADDRESS предпочтительнее (RFC 5389 рекомендует)
    return xor_result or mapped_result


def _parse_xor_mapped(val: bytes) -> Optional[tuple[str, int]]:
    """Разобрать XOR-MAPPED-ADDRESS атрибут."""
    family = val[1]
    xport  = struct.unpack(">H", val[2:4])[0] ^ (STUN_MAGIC_COOKIE >> 16)

    if family == 0x01:  # IPv4
        xip = struct.unpack(">I", val[4:8])[0] ^ STUN_MAGIC_COOKIE
        ip  = str(ipaddress.IPv4Address(xip))
        return ip, xport

    if family == 0x02:  # IPv6 (на будущее)
        log.debug("IPv6 XOR-MAPPED-ADDRESS — not yet handled")
        return None

    return None


def _parse_mapped(val: bytes) -> Optional[tuple[str, int]]:
    """Разобрать MAPPED-ADDRESS атрибут (старый формат)."""
    family = val[1]
    port   = struct.unpack(">H", val[2:4])[0]

    if family == 0x01:  # IPv4
        ip = str(ipaddress.IPv4Address(val[4:8]))
        return ip, port

    return None


# ──────────────────────────────────────────────────────────────
# Async UDP протокол для asyncio
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
# Основная async функция
# ──────────────────────────────────────────────────────────────
async def discover_async(
    servers: Optional[list[tuple[str, int]]] = None,
    timeout: float = 3.0,
    local_port: int = 0,
) -> STUNResult:
    """
    Определить публичный IP:port через STUN.

    Параметры
    ---------
    servers     : список (host, port) STUN-серверов; по умолчанию DEFAULT_SERVERS
    timeout     : таймаут на один сервер (секунды)
    local_port  : локальный UDP-порт (0 = выбрать автоматически)

    Возвращает STUNResult или бросает RuntimeError если все серверы недоступны.
    """
    if servers is None:
        servers = DEFAULT_SERVERS

    loop = asyncio.get_running_loop()
    last_error: Exception = RuntimeError("No STUN servers configured")

    for host, port in servers:
        label = f"{host}:{port}"
        try:
            log.debug("Trying STUN server %s …", label)

            # Резолвим хост заранее (чтобы поймать DNS-ошибки красиво)
            infos = await loop.getaddrinfo(
                host, port,
                type=socket.SOCK_DGRAM,
                proto=socket.IPPROTO_UDP,
            )
            if not infos:
                raise OSError(f"DNS lookup failed for {host}")

            server_addr = (infos[0][4][0], port)   # первый IPv4 адрес

            request, txn_id = _build_binding_request()
            fut: asyncio.Future = loop.create_future()

            transport, _ = await loop.create_datagram_endpoint(
                lambda: _STUNProtocol(txn_id, fut),
                local_addr=("0.0.0.0", local_port),
                remote_addr=server_addr,
                reuse_port=True,    # SO_REUSEPORT: VPN-сокет может занять
            )                       # тот же порт не дожидаясь закрытия

            try:
                transport.sendto(request)
                ip, pub_port = await asyncio.wait_for(fut, timeout=timeout)
                log.info("STUN success via %s → %s:%d", label, ip, pub_port)
                return STUNResult(
                    public_ip=ip,
                    public_port=pub_port,
                    server_used=label,
                )
            finally:
                transport.close()

        except asyncio.TimeoutError:
            log.debug("STUN timeout on %s", label)
            last_error = TimeoutError(f"STUN server {label} timed out")
        except Exception as exc:
            log.debug("STUN error on %s: %s", label, exc)
            last_error = exc

    raise RuntimeError(
        f"All STUN servers failed. Last error: {last_error}"
    )


# ──────────────────────────────────────────────────────────────
# Sync-обёртка (удобна для одиночного вызова без asyncio)
# ──────────────────────────────────────────────────────────────
def discover(
    servers: Optional[list[tuple[str, int]]] = None,
    timeout: float = 3.0,
    local_port: int = 0,
) -> STUNResult:
    """Синхронная версия discover_async. Создаёт временный event loop."""
    return asyncio.run(discover_async(servers, timeout, local_port))


# ──────────────────────────────────────────────────────────────
# CLI: python3 stun_client.py
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="STUN public IP discovery")
    parser.add_argument("--server", metavar="HOST:PORT", action="append",
                        help="STUN server (repeat for multiple). Default: Google/Cloudflare")
    parser.add_argument("--timeout", type=float, default=3.0,
                        help="Per-server timeout in seconds (default: 3)")
    parser.add_argument("--port", type=int, default=0,
                        help="Local UDP port to bind (default: auto)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    servers = None
    if args.server:
        servers = []
        for s in args.server:
            h, p = s.rsplit(":", 1)
            servers.append((h, int(p)))

    try:
        result = discover(servers=servers, timeout=args.timeout, local_port=args.port)
        print(f"\n  ✓ Public address : {result.public_ip}:{result.public_port}")
        print(f"  ✓ STUN server    : {result.server_used}\n")
    except RuntimeError as e:
        print(f"\n  ✗ STUN failed: {e}\n", file=sys.stderr)
        sys.exit(1)
