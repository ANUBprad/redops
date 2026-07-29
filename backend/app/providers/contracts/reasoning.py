"""Reasoning provider contract.

Defines the interface for providers that support chain-of-thought,
extended thinking, or other reasoning trace capabilities.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse


class ReasoningProvider:
    """Interface for reasoning-capable providers.

    Providers that expose reasoning traces or step-by-step
    thinking must implement this interface.

    The reasoning_content field in ChatResponse carries the
    model's internal reasoning, while content carries the
    final answer.
    """

    @abstractmethod
    async def reason(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Generate a response with reasoning traces.

        The response may include a reasoning_content field
        containing the model's chain-of-thought, separate
        from the final content.

        Args:
            messages: The conversation messages.
            model: The model identifier to use.
            options: Optional generation parameters.

        Returns:
            Response with reasoning and final content.

        Raises:
            InvalidModel: If the model does not support reasoning.
            ProviderUnavailable: If the provider is down.

        """
