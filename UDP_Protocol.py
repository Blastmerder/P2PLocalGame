import asyncio
import logging


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("UDPProtocol")



# ─────────────────────────────────────────────────────
# UDP protocol
# ─────────────────────────────────────────────────────
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


