"""Request options for provider interactions.

Provider-agnostic option types that control model behavior
during inference. Options are immutable and passed to providers
as part of every request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderRequestOptions:
    """Base options applicable to all provider requests.

    Provides common configuration that every provider must
    respect, regardless of the specific model or capability.
    """

    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None
    seed: int | None = None
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChatOptions(ProviderRequestOptions):
    """Options specific to chat completions.

    Extends base options with chat-specific parameters
    like system prompts and tool definitions.
    """

    system_prompt: str | None = None
    tools: tuple[dict[str, Any], ...] = ()
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    parallel_tool_calls: bool | None = None


@dataclass(frozen=True, slots=True)
class EmbeddingOptions(ProviderRequestOptions):
    """Options specific to embedding requests.

    Controls embedding dimensions and input format.
    """

    dimensions: int | None = None
    encoding_format: str = "float"
