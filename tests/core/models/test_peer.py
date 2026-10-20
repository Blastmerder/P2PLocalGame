import unittest
from datetime import datetime
from p2pvpn.core.models.peer import Peer, PeerState

class TestPeer(unittest.TestCase):
    def test_peer_initial_state(self):
        peer = Peer(peer_id="peer1", address="127.0.0.1", port=12345)
        self.assertEqual(peer.state, PeerState.PENDING)

    def test_peer_lifecycle(self):
        peer = Peer(peer_id="peer1", address="127.0.0.1", port=12345)
        
        # Test mark_alive
        peer.mark_alive()
        self.assertEqual(peer.state, PeerState.ALIVE)
        self.assertIsInstance(peer.last_seen, datetime)

        # Test mark_dead
        peer.mark_dead()
        self.assertEqual(peer.state, PeerState.DEAD)

        # Test mark_pending
        peer.mark_pending()
        self.assertEqual(peer.state, PeerState.PENDING)

if __name__ == '__main__':
    unittest.main()
