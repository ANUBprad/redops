"""Chat provider contract.

Defines the interface for providers that support chat/text
completion. This is the most common provider type.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse


class ChatProvider:
    """Interface for chat completion providers.

    Providers that support conversational AI must implement
    this interface. The Evaluation Engine uses this contract
    for all chat-based evaluations.

    """

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Generate a chat completion.

        Args:
            messages: The conversation messages.
            model: The model identifier to use.
            options: Optional generation parameters.

        Returns:
            The model's response.

        Raises:
            InvalidModel: If the model is not recognized.
            ContextWindowExceeded: If input exceeds context.
            ProviderUnavailable: If the provider is down.

        """
