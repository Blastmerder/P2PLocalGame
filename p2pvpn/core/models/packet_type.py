from enum import Enum, auto

class PacketType(Enum):
    HELLO = auto()
    DATA = auto()
