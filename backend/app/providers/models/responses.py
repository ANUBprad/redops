"""Response types for provider interactions.

Provider-agnostic response representations returned by providers.
All responses are immutable and include usage tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.providers.models.enums import FinishReason
from app.providers.models.messages import ToolCallContent  # noqa: TC001


@dataclass(frozen=True, slots=True)
class Usage:
    """Token usage statistics for a request.

    Tracks input, output, and cached tokens along with
    any additional provider-specific usage data.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    audio_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Compute total if not explicitly provided."""
        if self.total_tokens == 0:
            object.__setattr__(
                self,
                "total_tokens",
                self.input_tokens + self.output_tokens,
            )


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Base response from any provider.

    All provider responses share common metadata including
    usage tracking, model identification, and finish reason.
    """

    model: str
    provider: str
    usage: Usage
    finish_reason: FinishReason = FinishReason.UNKNOWN
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChatResponse(ProviderResponse):
    """Response from a chat completion.

    Contains the generated text content and any tool calls
    initiated by the model.
    """

    content: str = ""
    tool_calls: tuple[ToolCallContent, ...] = ()
    audio_data: str | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingResponse(ProviderResponse):
    """Response from an embedding request.

    Contains the generated embedding vector and the
    dimensions of the embedding.
    """

    embedding: tuple[float, ...] = ()
    dimensions: int = 0
