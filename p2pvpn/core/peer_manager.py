from typing import Dict, List, Optional
from datetime import datetime, timedelta
from p2pvpn.core.models.peer import Peer, PeerState

class PeerManager:
    """
    Manages the lifecycle and state of remote peers.
    """
    def __init__(self, timeout_duration: timedelta = timedelta(minutes=5)):
        self._peers: Dict[str, Peer] = {}  # peer_id -> Peer
        self._peers_by_address: Dict[str, str] = {}  # address:port -> peer_id
        self._timeout_duration = timeout_duration

    def add_peer(self, peer: Peer) -> None:
        """
        Adds a peer to the manager. If a peer with the same ID already exists, it is updated.
        """
        peer_id = peer.peer_id
        address_key = f"{peer.address}:{peer.port}"

        # If replacing an existing peer, clean up the old address mapping if it's different
        if peer_id in self._peers:
            old_peer = self._peers[peer_id]
            old_address_key = f"{old_peer.address}:{old_peer.port}"
            if old_address_key != address_key:
                if self._peers_by_address.get(old_address_key) == peer_id:
                    del self._peers_by_address[old_address_key]

        self._peers[peer_id] = peer
        self._peers_by_address[address_key] = peer_id

    def remove_peer(self, peer_id: str) -> None:
        """
        Removes a peer from the manager.
        """
        if peer_id in self._peers:
            peer = self._peers.pop(peer_id)
            address_key = f"{peer.address}:{peer.port}"
            if self._peers_by_address.get(address_key) == peer_id:
                del self._peers_by_address[address_key]

    def update_peer_activity(self, peer_id: str) -> None:
        """
        Updates the last seen time and state of a peer.
        """
        if peer_id in self._peers:
            peer = self._peers[peer_id]
            peer.mark_alive()

    def get_peer(self, peer_id: str) -> Optional[Peer]:
        """
        Retrieves a peer by its ID.
        """
        return self._peers.get(peer_id)

    def get_peer_by_address(self, address: str, port: int) -> Optional[Peer]:
        """
        Retrieves a peer by its address and port.
        """
        address_key = f"{address}:{port}"
        peer_id = self._peers_by_address.get(address_key)
        if peer_id:
            return self._peers.get(peer_id)
        return None

    def get_active_peers(self) -> List[Peer]:
        """
        Returns a list of all peers that are currently in the ALIVE state.
        """
        return [peer for peer in self._peers.values() if peer.state == PeerState.ALIVE]

    def get_all_peers(self) -> List[Peer]:
        """
        Returns a list of all peers managed.
        """
        return list(self._peers.values())

    def cleanup_expired_peers(self) -> List[str]:
        """
        Identifies peers that have not been seen within the timeout duration and marks them as DEAD.
        Returns a list of peer IDs that were marked as DEAD.
        """
        expired_peer_ids = []
        now = datetime.now()
        for peer_id, peer in self._peers.items():
            if peer.state == PeerState.ALIVE and peer.last_seen:
                if now - peer.last_seen > self._timeout_duration:
                    peer.mark_dead()
                    expired_peer_ids.append(peer_id)
        return expired_peer_ids
