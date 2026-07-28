"""Audio provider contract.

Defines the interface for providers that support audio
input processing or audio/speech output generation.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse


class AudioProvider:
    """Interface for audio-capable providers.

    Providers that support audio input or output must
    implement this interface for audio-based evaluations.
    """

    @abstractmethod
    async def audio_input(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Process audio input.

        Messages should contain AudioContent blocks.

        Args:
            messages: Messages containing audio content.
            model: The model identifier to use.
            options: Optional generation parameters.

        Returns:
            The model's response to the audio input.

        Raises:
            InvalidModel: If the model does not support audio.
            ProviderUnavailable: If the provider is down.

        """

    @abstractmethod
    async def audio_output(
        self,
        text: str,
        *,
        model: str,
        voice: str = "default",
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Generate audio output from text.

        Args:
            text: The text to convert to speech.
            model: The model identifier to use.
            voice: The voice identifier to use.
            options: Optional generation parameters.

        Returns:
            Response containing audio data.

        Raises:
            InvalidModel: If the model does not support audio output.
            ProviderUnavailable: If the provider is down.

        """
