"""Anthropic contracts adapter — implements framework provider interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.providers.anthropic.mappers.request import (
    map_chat_options,
    map_messages,
    map_tool_choice,
    map_tools,
)
from app.providers.anthropic.mappers.response import map_chat_response
from app.providers.anthropic.streaming.adapter import adapt_stream

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.providers.anthropic.client.anthropic_client import AnthropicClient
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse
    from app.providers.streaming.chunk import StreamChunk

_DEFAULT_MAX_TOKENS = 4096


class AnthropicChatAdapter:
    """Adapter for chat completions through Anthropic."""

    def __init__(self, client: AnthropicClient) -> None:
        """Initialize with Anthropic client."""
        self._client = client

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Execute a chat completion."""
        anthropic_messages, system = map_messages(
            messages,
            system_prompt=options.system_prompt if options else None,
        )
        params = map_chat_options(options)

        max_tokens = params.pop("max_tokens", _DEFAULT_MAX_TOKENS)

        response = await self._client.create_message(
            model=model,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            system=system,
            **params,
        )

        return map_chat_response(response)


class AnthropicStreamingAdapter:
    """Adapter for streaming chat completions through Anthropic."""

    def __init__(self, client: AnthropicClient) -> None:
        """Initialize with Anthropic client."""
        self._client = client

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion."""
        anthropic_messages, system = map_messages(
            messages,
            system_prompt=options.system_prompt if options else None,
        )
        params = map_chat_options(options)

        max_tokens = params.pop("max_tokens", _DEFAULT_MAX_TOKENS)

        sdk_stream = await self._client.create_message_stream(
            model=model,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            system=system,
            **params,
        )

        async for chunk in adapt_stream(sdk_stream):
            yield chunk


class AnthropicToolCallingAdapter:
    """Adapter for tool-calling chat completions through Anthropic."""

    def __init__(self, client: AnthropicClient) -> None:
        """Initialize with Anthropic client."""
        self._client = client

    async def chat_with_tools(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None = None,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Execute a chat completion with tool calling."""
        anthropic_messages, system = map_messages(
            messages,
            system_prompt=options.system_prompt if options else None,
        )
        params = map_chat_options(options)

        max_tokens = params.pop("max_tokens", _DEFAULT_MAX_TOKENS)

        anthropic_tools = map_tools(tools)
        if anthropic_tools:
            params["tools"] = anthropic_tools

        mapped_tool_choice = map_tool_choice(tool_choice)
        if mapped_tool_choice is not None:
            params["tool_choice"] = mapped_tool_choice

        response = await self._client.create_message(
            model=model,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            system=system,
            **params,
        )

        return map_chat_response(response)


class AnthropicReasoningAdapter:
    """Adapter for reasoning completions through Anthropic."""

    def __init__(self, client: AnthropicClient) -> None:
        """Initialize with Anthropic client."""
        self._client = client

    async def reason(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Execute a reasoning completion.

        Anthropic does not have a separate reasoning mode like o1/o3.
        Extended thinking is used when available via the thinking parameter.
        """
        anthropic_messages, system = map_messages(
            messages,
            system_prompt=options.system_prompt if options else None,
        )
        params = map_chat_options(options)

        max_tokens = params.pop("max_tokens", _DEFAULT_MAX_TOKENS)

        response = await self._client.create_message(
            model=model,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            system=system,
            **params,
        )

        return map_chat_response(response)
