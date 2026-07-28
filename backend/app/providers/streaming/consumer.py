"""Stream consumer abstraction.

Defines the interface for consuming streaming responses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable

from app.providers.streaming.chunk import StreamChunk


class StreamConsumer(ABC):
    """Abstract stream consumer.

    Consumers process StreamChunk instances from a stream.
    Implementations may accumulate content, forward events,
    or perform real-time analysis.
    """

    @abstractmethod
    async def consume(self, stream: AsyncIterator[StreamChunk]) -> None:
        """Consume all chunks from a stream.

        Args:
            stream: The stream of chunks to consume.

        """

    @abstractmethod
    async def consume_until(
        self,
        stream: AsyncIterator[StreamChunk],
        predicate: Callable[[StreamChunk], bool],
    ) -> list[StreamChunk]:
        """Consume chunks until a predicate is satisfied.

        Args:
            stream: The stream of chunks.
            predicate: Function that returns True to stop consumption.

        Returns:
            List of chunks consumed before stopping.

        """
