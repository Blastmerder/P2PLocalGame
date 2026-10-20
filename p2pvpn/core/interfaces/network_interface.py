from abc import ABC, abstractmethod
from typing import Callable, Any, Coroutine

class INetworkInterface(ABC):
    """Abstract base class for network interfaces."""

    @abstractmethod
    async def write(self, data: bytes) -> None:
        """
        Writes data to the network interface.

        Args:
            data: The bytes to write.
        """
        pass

    @abstractmethod
    def frame_received(self, callback: Callable[[bytes], Coroutine[Any, Any, None]]) -> None:
        """
        Registers a callback to be called when a frame is received.

        Args:
            callback: An async callback that accepts the raw bytes of the frame.
        """
        pass
