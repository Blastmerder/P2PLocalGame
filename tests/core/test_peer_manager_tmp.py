from datetime import datetime, timedelta
from unittest.mock import patch
from p2pvpn.core.models.peer import Peer, PeerState
from p2pvpn.core.peer_manager import PeerManager

def test_add_and_remove_peer():
    manager = PeerManager()
    peer = Peer(peer_id="peer1", address="127.0.0.1", port=1234)
    
    manager.add_peer(peer)
    assert manager.get_peer("peer1") == peer
    assert manager.get_peer_by_address("127.0.0.1", 1234) == peer
    
    manager.remove_peer("peer1")
    assert manager.get_peer("peer1") is None
    assert manager.get_peer_by_address("127.0.0.1", 1234) is None

def test_update_peer_activity():
    manager = PeerManager()
    peer = Peer(peer_id="peer1", address="127.0.0.1", port=1234, state=PeerState.PENDING)
    manager.add_peer(peer)
    
    assert peer.state == PeerState.PENDING
    assert peer.last_seen is None
    
    manager.update_peer_activity("peer1")
    
    assert peer.state == PeerState.ALIVE
    assert peer.last_seen is not None
    assert isinstance(peer.last_seen, datetime)

def test_get_active_peers():
    manager = PeerManager()
    peer1 = Peer(peer_id="peer1", address="127.0.0.1", port=1234, state=PeerState.ALIVE)
    peer2 = Peer(peer_id="peer2", address="127.0.0.2", port=1234, state=PeerState.PENDING)
    peer3 = Peer(peer_id="peer3", address="127.0.0.3", port=1234, state=PeerState.DEAD)
    
    manager.add_peer(peer1)
    manager.add_peer(peer2)
    manager.add_peer(peer3)
    
    active_peers = manager.get_active_peers()
    assert len(active_peers) == 1
    assert active_peers[0].peer_id == "peer1"

def test_cleanup_expired_peers():
    timeout = timedelta(seconds=1)
    manager = PeerManager(timeout_duration=timeout)
    
    peer_active = Peer(peer_id="active", address="127.0.0.1", port=1234)
    peer_pending = Peer(peer_id="pending", address="127.0.0.2", port=1234, state=PeerState.PENDING)
    
    manager.add_peer(peer_active)
    manager.add_peer(peer_pending)
    
    # Mark active peer as alive
    manager.update_peer_activity("active")
    
    # Fast forward time
    with patch('p2pvpn.core.peer_manager.datetime') as mock_datetime:
        # Set current time to now
        now = datetime.now()
        mock_datetime.now.return_value = now
        
        # Wait for timeout
        mock_datetime.now.return_value = now + timedelta(seconds=2)
        
        expired_ids = manager.cleanup_expired_peers()
        
        assert "active" in expired_ids
        assert "pending" not in expired_ids  # Pending peer shouldn't be expired because it's not ALIVE (based on my implementation)
        
        assert manager.get_peer("active").state == PeerState.DEAD
        assert manager.get_peer("pending").state == PeerState.PENDING

def test_peer_id_update():
    # Test that updating a peer with the same ID works
    manager = PeerManager()
    peer1 = Peer(peer_id="peer1", address="127.0.0.1", port=1234)
    manager.add_peer(peer1)
    
    peer2 = Peer(peer_id="peer1", address="127.0.0.1", port=5678)  # Same ID, different port
    manager.add_peer(peer2)
    
    assert manager.get_peer("peer1").port == 5678
    assert manager.get_peer_by_address("127.0.0.1", 1234) is None
    assert manager.get_peer_by_address("127.0.0.1", 5678) == peer2

def test_peer_address_update():
    # Test that updating a peer with same ID but different address works
    manager = PeerManager()
    peer1 = Peer(peer_id="peer1", address="127.0.0.1", port=1234)
    manager.add_peer(peer1)
    
    peer2 = Peer(peer_id="peer1", address="192.168.1.1", port=1234)
    manager.add_peer(peer2)
    
    assert manager.get_peer("peer1").address == "192.168.1.1"
    assert manager.get_peer_by_address("127.0.0.1", 1234) is None
    assert manager.get_peer_by_address("192.168.1.1", 1234) == peer2
