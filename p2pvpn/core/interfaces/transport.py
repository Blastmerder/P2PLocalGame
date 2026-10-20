from abc import ABC, abstractmethod
from typing import Callable, Any, Coroutine
from p2pvpn.core.models.packet_type import PacketType

class ITransport(ABC):
    """Abstract base class for transport interfaces."""

    @abstractmethod
    async def send(self, destination: tuple[str, int], data: bytes, packet_type: PacketType = PacketType.DATA) -> None:
        """
        Sends data to the specified destination.

        Args:
            destination: A tuple of (host, port).
            data: The bytes to send.
            packet_type: The type of packet to send.
        """
        pass

    @abstractmethod
    def packet_received(self, callback: Callable[[tuple[str, int], PacketType, bytes], Coroutine[Any, Any, None]]) -> None:
        """
        Registers a callback to be called when a packet is received.

        Args:
            callback: An async callback that accepts (destination, packet_type, data).
        """
        pass
