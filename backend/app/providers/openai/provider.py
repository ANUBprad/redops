"""OpenAI provider — canonical implementation of the Provider Framework.

Implements ChatProvider, StreamingProvider, ToolCallingProvider, and
ReasoningProvider interfaces for the OpenAI API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.contracts.base import BaseProvider
from app.providers.contracts.chat import ChatProvider
from app.providers.contracts.reasoning import ReasoningProvider
from app.providers.contracts.streaming import StreamingProvider
from app.providers.contracts.tool_calling import ToolCallingProvider
from app.providers.metadata.provider import ProviderMetadata
from app.providers.openai.adapters.contracts import (
    OpenAIChatAdapter,
    OpenAIReasoningAdapter,
    OpenAIStreamingAdapter,
    OpenAIToolCallingAdapter,
)
from app.providers.openai.client.openai_client import OpenAIClient
from app.providers.openai.health.contributor import OpenAIHealthContributor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.providers.health.provider_health import ProviderHealth
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse
    from app.providers.streaming.chunk import StreamChunk

PROVIDER_NAME = "openai"

_CAPABILITIES = CapabilitySet.of(
    Capability.CHAT,
    Capability.SYSTEM_PROMPT,
    Capability.MULTI_TURN,
    Capability.STREAMING,
    Capability.VISION,
    Capability.IMAGE_URL,
    Capability.IMAGE_BASE64,
    Capability.MULTI_IMAGE,
    Capability.TOOL_CALLING,
    Capability.FUNCTION_CALLING,
    Capability.PARALLEL_TOOL_CALLS,
    Capability.JSON_MODE,
    Capability.STRUCTURED_OUTPUT,
    Capability.SEED,
    Capability.LOGPROBS,
    Capability.TOP_LOGPROBS,
    Capability.PRESENCE_PENALTY,
    Capability.FREQUENCY_PENALTY,
    Capability.STOP_SEQUENCES,
    Capability.TEMPERATURE,
    Capability.TOP_P,
    Capability.LONG_CONTEXT,
    Capability.VISION_CONTEXT,
    Capability.REASONING,
    Capability.PROMPT_CACHING,
)


class OpenAIProvider(
    BaseProvider,
    ChatProvider,
    StreamingProvider,
    ToolCallingProvider,
    ReasoningProvider,
):
    """OpenAI provider implementing all framework chat contracts.

    This is the canonical reference provider. Future providers
    should follow this structure.

    Usage:
        provider = OpenAIProvider(api_key="sk-...")
        await provider.initialize()
        response = await provider.chat(messages, model="gpt-4o")
        await provider.dispose()

    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            base_url: Custom API base URL.
            organization: OpenAI organization ID.
            timeout: Default request timeout in seconds.

        """
        self._client = OpenAIClient(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
            timeout=timeout,
        )
        self._chat_adapter = OpenAIChatAdapter(self._client)
        self._streaming_adapter = OpenAIStreamingAdapter(self._client)
        self._tool_adapter = OpenAIToolCallingAdapter(self._client)
        self._reasoning_adapter = OpenAIReasoningAdapter(self._client)
        self._health_contributor = OpenAIHealthContributor(self._client)
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
            display_name="OpenAI",
            description="OpenAI GPT models including GPT-4o, GPT-4, and o1/o3 reasoning models",
            version="0.1.0",
            author="RedOps Eval",
            homepage="https://openai.com",
            documentation_url="https://platform.openai.com/docs",
            supported_regions=("global",),
            tags=("openai", "gpt", "chat", "reasoning", "vision"),
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
        """Check if the OpenAI API is reachable."""
        return await self._client.check_health()

    async def detailed_health(self) -> ProviderHealth:
        """Return detailed health with latency info."""
        return await self._health_contributor.check()

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
            model: The model identifier (e.g., 'gpt-4o').
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
            messages, model=model, options=options,
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

        The model may respond with tool calls that should
        be executed by the caller, then fed back as
        ToolResultContent messages.

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

        For o1/o3 models, system messages are automatically
        converted to user messages (OpenAI restriction).

        """
        return await self._reasoning_adapter.reason(
            messages, model=model, options=options,
        )
