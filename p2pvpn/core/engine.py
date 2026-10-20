import asyncio
import logging
from typing import Optional, List

from p2pvpn.core.interfaces.transport import ITransport
from p2pvpn.core.interfaces.network_interface import INetworkInterface
from p2pvpn.core.peer_manager import PeerManager
from p2pvpn.core.models.vpn_config import VPNConfig
from p2pvpn.core.models.packet_type import PacketType
from p2pvpn.core.models.peer import Peer, PeerState

logger = logging.getLogger(__name__)

class Engine:
    """
    Central orchestrator that manages the VPN logic, coordinating between
    the transport layer and the network interface.
    """

    def __init__(
        self,
        transport: ITransport,
        network_interface: INetworkInterface,
        peer_manager: PeerManager,
        config: VPNConfig
    ):
        self.transport = transport
        self.network_interface = network_interface
        self.peer_manager = peer_manager
        self.config = config
        self._running = False

    async def start(self) -> None:
        """
        Starts the engine by registering callbacks for transport and network interface.
        """
        self._running = True
        
        # Register callbacks
        self.transport.packet_received(self._on_packet_received)
        self.network_interface.frame_received(self._on_frame_received)
        
        logger.info("Engine started.")

    async def stop(self) -> None:
        """
        Stops the engine.
        """
        self._running = False
        logger.info("Engine stopped.")

    async def _on_packet_received(self, address: tuple[str, int], packet_type: PacketType, payload: bytes) -> None:
        """
        Callback invoked when a packet is received from the transport layer.
        """
        try:
            if not payload and packet_type != PacketType.HELLO:
                return

            host, port = address

            if packet_type == PacketType.HELLO:
                # For HELLO, we expect the payload to be the peer_id (as UTF-8 string)
                try:
                    peer_id = payload.decode('utf-8')
                except UnicodeDecodeError:
                    logger.error("Failed to decode peer_id from HELLO packet")
                    return

                peer = self.peer_manager.get_peer_by_address(host, port)
                if peer:
                    if peer.peer_id != peer_id:
                        logger.warning(f"Peer ID mismatch: expected {peer.peer_id}, got {peer_id}")
                    self.peer_manager.update_peer_activity(peer.peer_id)
                else:
                    # New peer discovered via HELLO
                    new_peer = Peer(
                        peer_id=peer_id,
                        address=host,
                        port=port,
                        state=PeerState.ALIVE
                    )
                    self.peer_manager.add_peer(new_peer)
                    logger.info(f"Discovered new peer: {peer_id} at {host}:{port}")

            elif packet_type == PacketType.DATA:
                peer = self.peer_manager.get_peer_by_address(host, port)
                if peer:
                    self.peer_manager.update_peer_activity(peer.peer_id)
                    await self.network_interface.write(payload)
                else:
                    logger.warning(f"Received DATA packet from unknown peer at {host}:{port}")

        except Exception as e:
            logger.error(f"Error handling packet from {address}: {e}")

    async def _on_frame_received(self, frame: bytes) -> None:
        """
        Callback invoked when a frame is received from the network interface.
        """
        try:
            # Send the packet to all currently active peers
            active_peers = self.peer_manager.get_active_peers()
            for peer in active_peers:
                await self.transport.send((peer.address, peer.port), frame)
                
        except Exception as e:
            logger.error(f"Error handling frame from network interface: {e}")

    async def run(self) -> None:
        """
        Main loop for the engine.
        """
        await self.start()
        await asyncio.gather(
            self.perform_hole_punching(),
            self._heartbeat()
        )
        while self._running:
            await asyncio.sleep(1)

    async def _heartbeat(self) -> None:
        """
        Periodically send HELLO to all known peers to keep them alive.
        """
        while self._running:
            await asyncio.sleep(self.config.keepalive_interval)
            for peer in self.peer_manager.get_all_peers():
                try:
                    # HELLO packet payload is the peer_id
                    hello_payload = peer.peer_id.encode('utf-8')
                    await self.transport.send((peer.address, peer.port), hello_payload, packet_type=PacketType.HELLO)
                    logger.debug("Sent heartbeat HELLO to %s", peer.peer_id)
                except Exception as e:
                    logger.error("Failed to send heartbeat to %s: %s", peer.peer_id, e)

    async def perform_hole_punching(self) -> None:
        """
        Attempts to initiate hole punching with all known peers.
        """
        logger.info("Starting hole punching...")
        for peer in self.peer_manager.get_all_peers():
            try:
                await self.transport.hole_punch((peer.address, peer.port))
                logger.debug("Sent hole punch attempt to %s", peer.peer_id)
            except Exception as e:
                logger.error("Failed to hole punch %s: %s", peer.peer_id, e)
