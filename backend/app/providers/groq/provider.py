"""Groq provider — OpenAI-compatible provider.

Groq serves its models through an OpenAI-compatible chat completions API
(``https://api.groq.com/openai/v1``). This provider therefore composes the
same wire-format client, request/response mappers, streaming, and tool-calling
machinery used by the OpenAI provider, pointed at Groq's endpoint and keyed by
the ``GROQ_API_KEY`` credential.

Differences from OpenAI:
- No embedding API, so ``GroqProvider`` does not implement ``EmbeddingProvider``
  and omits embedding capabilities.
- Reasoning models run through the standard chat-completions path (Groq accepts
  system messages on its reasoning models), so the o1/o3-specific system->user
  conversion used by ``OpenAIReasoningAdapter`` is not applied.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.contracts.base import BaseProvider
from app.providers.contracts.chat import ChatProvider
from app.providers.contracts.reasoning import ReasoningProvider
from app.providers.contracts.streaming import StreamingProvider
from app.providers.contracts.tool_calling import ToolCallingProvider
from app.providers.groq.constants import DEFAULT_BASE_URL, PROVIDER_NAME
from app.providers.health.provider_health import ProviderHealth
from app.providers.health.status import ProviderStatus
from app.providers.metadata.provider import ProviderMetadata
from app.providers.openai.adapters.contracts import (
    OpenAIChatAdapter,
    OpenAIStreamingAdapter,
    OpenAIToolCallingAdapter,
)
from app.providers.openai.client.openai_client import OpenAIClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse
    from app.providers.streaming.chunk import StreamChunk

_CAPABILITIES = CapabilitySet.of(
    Capability.CHAT,
    Capability.SYSTEM_PROMPT,
    Capability.MULTI_TURN,
    Capability.STREAMING,
    Capability.TOOL_CALLING,
    Capability.FUNCTION_CALLING,
    Capability.PARALLEL_TOOL_CALLS,
    Capability.JSON_MODE,
    Capability.REASONING,
    Capability.SEED,
    Capability.PRESENCE_PENALTY,
    Capability.FREQUENCY_PENALTY,
    Capability.STOP_SEQUENCES,
    Capability.TEMPERATURE,
    Capability.TOP_P,
    Capability.LONG_CONTEXT,
)


class GroqProvider(
    BaseProvider,
    ChatProvider,
    StreamingProvider,
    ToolCallingProvider,
    ReasoningProvider,
):
    """Groq provider using the OpenAI-compatible wire format.

    Usage:
        provider = GroqProvider(api_key="gsk-...")
        await provider.initialize()
        response = await provider.chat(messages, model="llama-3.3-70b-versatile")
        await provider.dispose()

    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        """Initialize the Groq provider.

        Args:
            api_key: Groq API key. Falls back to GROQ_API_KEY env var.
            base_url: Custom API base URL (defaults to Groq's OpenAI-compatible
                endpoint).
            timeout: Default request timeout in seconds.

        """
        self._client = OpenAIClient(
            api_key=api_key,
            base_url=base_url or DEFAULT_BASE_URL,
            timeout=timeout,
        )
        self._chat_adapter = OpenAIChatAdapter(self._client)
        self._streaming_adapter = OpenAIStreamingAdapter(self._client)
        self._tool_adapter = OpenAIToolCallingAdapter(self._client)
        self._started = False

    @property
    def provider_name(self) -> str:
        """Return the unique provider identifier."""
        return PROVIDER_NAME

    @property
    def metadata(self) -> ProviderMetadata:
        """Return static provider metadata."""
        return ProviderMetadata(
            name=PROVIDER_NAME,
            display_name="Groq",
            description=(
                "Groq LPU inference for Llama, Mixtral, GEMMA, and OpenAI Codex "
                "models served through an OpenAI-compatible API"
            ),
            version="0.1.0",
            author="RedOps Eval",
            homepage="https://groq.com",
            documentation_url="https://console.groq.com/docs",
            supported_regions=("global",),
            tags=("groq", "lpu", "llama", "mixtral", "gemma", "chat", "reasoning"),
        )

    def capabilities(self) -> CapabilitySet:
        """Return supported capabilities."""
        return _CAPABILITIES

    def supports(self, capability: CapabilitySet) -> bool:
        """Check if all capabilities are supported."""
        return _CAPABILITIES.supports_all(capability)

    # ── Lifecycle ────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize the provider (validate config, set up pools)."""

    async def start(self) -> None:
        """Start accepting requests."""
        self._started = True

    async def stop(self) -> None:
        """Stop accepting new requests."""
        self._started = False

    async def dispose(self) -> None:
        """Release all resources."""
        await self._client.close()
        self._started = False

    # ── Health ───────────────────────────────────────────────────────

    async def health(self) -> bool:
        """Check if the Groq API is reachable."""
        return await self._client.check_health()

    async def detailed_health(self) -> ProviderHealth:
        """Return detailed health with latency info."""
        start = time.monotonic()
        is_healthy = await self._client.check_health()
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProviderHealth(
            provider_name=PROVIDER_NAME,
            status=ProviderStatus.HEALTHY if is_healthy else ProviderStatus.UNHEALTHY,
            message="Groq API reachable" if is_healthy else "Groq API unreachable",
            latency_ms=elapsed_ms,
            last_check=datetime.now(UTC).isoformat(),
        )

    # ── Chat ─────────────────────────────────────────────────────────

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
            model: The model identifier (e.g., 'llama-3.3-70b-versatile').
            options: Optional generation parameters.

        Returns:
            The model's response.

        """
        return await self._chat_adapter.chat(messages, model=model, options=options)

    # ── Streaming ────────────────────────────────────────────────────

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion.

        Yields StreamChunk instances as the model generates tokens.

        """
        async for chunk in self._streaming_adapter.chat_stream(
            messages,
            model=model,
            options=options,
        ):
            yield chunk

    # ── Tool Calling ─────────────────────────────────────────────────

    async def chat_with_tools(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None = None,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Generate a chat completion with tool calling.

        The model may respond with tool calls that should be executed by the
        caller, then fed back as ToolResultContent messages.

        """
        return await self._tool_adapter.chat_with_tools(
            messages,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
            options=options,
        )

    # ── Reasoning ────────────────────────────────────────────────────

    async def reason(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Generate a response with reasoning traces.

        Groq serves reasoning-capable models (e.g., DeepSeek-R1 distillations)
        through the standard chat-completions path and accepts system messages,
        so the plain chat adapter is used rather than OpenAI's o1/o3 conversion.

        """
        return await self._chat_adapter.chat(messages, model=model, options=options)
