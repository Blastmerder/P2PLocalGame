from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from typing import Optional

class PeerState(Enum):
    PENDING = auto()
    ALIVE = auto()
    DEAD = auto()

@dataclass
class Peer:
    peer_id: str
    address: str
    port: int
    state: PeerState = PeerState.PENDING
    last_seen: Optional[datetime] = None

    def mark_alive(self):
        self.state = PeerState.ALIVE
        self.last_seen = datetime.now()

    def mark_dead(self):
        self.state = PeerState.DEAD

    def mark_pending(self):
        self.state = PeerState.PENDING
