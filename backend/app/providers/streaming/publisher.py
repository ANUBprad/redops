"""Stream publisher abstraction.

Defines the interface for publishing streaming events
to consumers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator  # noqa: TC003

from app.providers.streaming.chunk import StreamChunk  # noqa: TC001


class StreamPublisher(ABC):
    """Abstract stream publisher.

    Publishers produce StreamChunk instances that consumers
    can subscribe to. Decouples stream producers from consumers.
    """

    @abstractmethod
    async def publish(self, chunk: StreamChunk) -> None:
        """Publish a single chunk to all subscribers.

        Args:
            chunk: The chunk to publish.

        """

    @abstractmethod
    def subscribe(self) -> AsyncIterator[StreamChunk]:
        """Subscribe to the stream.

        Returns:
            An async iterator of chunks.

        """

    @abstractmethod
    async def complete(self) -> None:
        """Signal that the stream is complete."""

    @abstractmethod
    async def error(self, message: str) -> None:
        """Signal an error on the stream.

        Args:
            message: The error message.

        """
