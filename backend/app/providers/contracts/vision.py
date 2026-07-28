"""Vision provider contract.

Defines the interface for providers that support image
understanding and multimodal vision tasks.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse


class VisionProvider:
    """Interface for vision-capable providers.

    Providers that support image understanding must implement
    this interface. Vision inputs are passed as part of
    multimodal message content.
    """

    @abstractmethod
    async def vision(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Process a vision request.

        Messages should contain ImageContent blocks. The model
        will analyze the images and generate a response.

        Args:
            messages: Messages containing image content.
            model: The model identifier to use.
            options: Optional generation parameters.

        Returns:
            The model's vision response.

        Raises:
            InvalidModel: If the model does not support vision.
            ProviderUnavailable: If the provider is down.

        """
