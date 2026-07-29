"""Streaming provider contract.

Defines the interface for providers that support streaming
responses via async iteration.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.streaming.chunk import StreamChunk


class StreamingProvider:
    """Interface for streaming-capable providers.

    Providers that support server-sent events or other streaming
    protocols must implement this interface. The Evaluation Engine
    uses streaming for real-time response observation.
    """

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion.

        Yields StreamChunk instances as the model generates
        tokens. The final chunk contains usage statistics.

        Args:
            messages: The conversation messages.
            model: The model identifier to use.
            options: Optional generation parameters.

        Yields:
            StreamChunk instances with partial or final data.

        Raises:
            InvalidModel: If the model is not recognized.
            StreamingFailure: If the stream is interrupted.
            ProviderUnavailable: If the provider is down.

        """
        # This is an abstract method; the yield is unreachable.
        # Included to satisfy type checkers for AsyncIterator.
        if False:
            yield
