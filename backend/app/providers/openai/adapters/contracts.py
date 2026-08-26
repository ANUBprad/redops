"""OpenAI contracts adapter — implements framework provider interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.providers.openai.mappers.request import map_chat_options, map_messages, map_tools
from app.providers.openai.mappers.response import map_chat_response, map_embedding_response
from app.providers.openai.streaming.adapter import adapt_stream

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions, EmbeddingOptions
    from app.providers.models.responses import ChatResponse, EmbeddingResponse
    from app.providers.openai.client.openai_client import OpenAIClient
    from app.providers.streaming.chunk import StreamChunk


class OpenAIChatAdapter:
    """Adapter for chat completions through OpenAI."""

    def __init__(self, client: OpenAIClient) -> None:
        """Initialize with OpenAI client."""
        self._client = client

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Execute a chat completion."""
        openai_messages = map_messages(
            messages,
            system_prompt=options.system_prompt if options else None,
        )
        params = map_chat_options(options)

        response = await self._client.create_chat_completion(
            model=model,
            messages=openai_messages,
            **params,
        )

        return map_chat_response(response)


class OpenAIStreamingAdapter:
    """Adapter for streaming chat completions through OpenAI."""

    def __init__(self, client: OpenAIClient) -> None:
        """Initialize with OpenAI client."""
        self._client = client

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute a streaming chat completion."""
        openai_messages = map_messages(
            messages,
            system_prompt=options.system_prompt if options else None,
        )
        params = map_chat_options(options)

        sdk_stream = await self._client.create_chat_stream(
            model=model,
            messages=openai_messages,
            **params,
        )

        async for chunk in adapt_stream(sdk_stream):
            yield chunk


class OpenAIToolCallingAdapter:
    """Adapter for tool-calling chat completions through OpenAI."""

    def __init__(self, client: OpenAIClient) -> None:
        """Initialize with OpenAI client."""
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
        openai_messages = map_messages(
            messages,
            system_prompt=options.system_prompt if options else None,
        )
        params = map_chat_options(options)

        openai_tools = map_tools(tools)
        if openai_tools:
            params["tools"] = openai_tools

        if tool_choice is not None:
            params["tool_choice"] = tool_choice

        response = await self._client.create_chat_completion(
            model=model,
            messages=openai_messages,
            **params,
        )

        return map_chat_response(response)


class OpenAIReasoningAdapter:
    """Adapter for reasoning (o1/o3) completions through OpenAI."""

    def __init__(self, client: OpenAIClient) -> None:
        """Initialize with OpenAI client."""
        self._client = client

    async def reason(
        self,
        messages: list[Message],
        *,
        model: str,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Execute a reasoning completion.

        For o1/o3 models, system messages are not supported.
        They are converted to user messages.
        """
        openai_messages = map_messages(messages)

        filtered: list[dict[str, Any]] = []
        for msg in openai_messages:
            if msg.get("role") == "system":
                filtered.append({**msg, "role": "user"})
            else:
                filtered.append(msg)

        params = map_chat_options(options)
        params.pop("temperature", None)
        params.pop("top_p", None)

        response = await self._client.create_chat_completion(
            model=model,
            messages=filtered,
            **params,
        )

        return map_chat_response(response)


class OpenAIEmbeddingAdapter:
    """Adapter for embedding generation through OpenAI."""

    def __init__(self, client: OpenAIClient) -> None:
        """Initialize with OpenAI client."""
        self._client = client

    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
        options: EmbeddingOptions | None = None,
    ) -> EmbeddingResponse:
        """Generate embeddings for the given texts."""
        params: dict[str, Any] = {}
        if options is not None:
            if options.dimensions is not None:
                params["dimensions"] = options.dimensions
            if options.encoding_format:
                params["encoding_format"] = options.encoding_format

        raw_response = await self._client.create_embedding(
            model=model,
            texts=texts,
            **params,
        )

        return map_embedding_response(raw_response)
