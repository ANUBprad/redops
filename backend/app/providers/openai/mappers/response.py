"""OpenAI response mapping — converts SDK responses to framework models."""

from __future__ import annotations

from typing import Any

from app.providers.models.enums import FinishReason
from app.providers.models.messages import ToolCallContent
from app.providers.models.responses import ChatResponse, EmbeddingResponse, Usage

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "tool_calls": FinishReason.TOOL_CALLS,
    "content_filter": FinishReason.CONTENT_FILTER,
    "max_tokens": FinishReason.MAX_TOKENS,
}


def map_chat_response(
    response: Any,
    *,
    provider: str = "openai",
) -> ChatResponse:
    """Map an OpenAI ChatCompletion to a framework ChatResponse.

    Args:
        response: The raw OpenAI ChatCompletion object.
        provider: Provider name for the response.

    Returns:
        A provider-agnostic ChatResponse.

    """
    choice = response.choices[0] if response.choices else None
    message = choice.message if choice else None
    usage = _map_usage(response.usage) if response.usage else Usage()

    content = message.content if message and message.content else ""
    tool_calls = _map_tool_calls(message.tool_calls if message else None)
    finish_reason = _map_finish_reason(choice.finish_reason if choice else None)

    return ChatResponse(
        model=response.model,
        provider=provider,
        usage=usage,
        finish_reason=finish_reason,
        request_id=getattr(response, "id", None),
        content=content or "",
        tool_calls=tuple(tool_calls),
        metadata=_extract_metadata(response),
    )


def map_embedding_response(
    response: Any,
    *,
    provider: str = "openai",
) -> EmbeddingResponse:
    """Map an OpenAI embedding response to framework EmbeddingResponse.

    Args:
        response: The raw OpenAI embedding response.
        provider: Provider name for the response.

    Returns:
        A provider-agnostic EmbeddingResponse.

    """
    data = response.data[0] if response.data else None
    embedding = tuple(data.embedding) if data and data.embedding else ()
    usage = _map_usage(response.usage) if response.usage else Usage()

    return EmbeddingResponse(
        model=response.model,
        provider=provider,
        usage=usage,
        finish_reason=FinishReason.STOP,
        request_id=getattr(response, "id", None),
        embedding=embedding,
        dimensions=len(embedding),
    )


def _map_usage(usage: Any) -> Usage:
    """Map OpenAI usage to framework Usage."""
    if usage is None:
        return Usage()

    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or 0
    cached_tokens = _extract_cached_tokens(usage)
    audio_tokens = _extract_audio_tokens(usage)

    return Usage(
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        total_tokens=total_tokens,
        audio_tokens=audio_tokens,
    )


def _extract_cached_tokens(usage: Any) -> int:
    """Extract cached tokens from OpenAI usage."""
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", None)
        if cached is not None:
            return cached
    return 0


def _extract_audio_tokens(usage: Any) -> int:
    """Extract audio tokens from OpenAI usage."""
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        audio = getattr(details, "audio_tokens", None)
        if audio is not None:
            return audio
    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details is not None:
        audio = getattr(completion_details, "audio_tokens", None)
        if audio is not None:
            return audio
    return 0


def _map_tool_calls(
    tool_calls: list[Any] | None,
) -> list[ToolCallContent]:
    """Map OpenAI tool calls to framework ToolCallContent."""
    if not tool_calls:
        return []

    result: list[ToolCallContent] = []
    for tc in tool_calls:
        function = getattr(tc, "function", None)
        if function is None:
            continue

        result.append(
            ToolCallContent(
                tool_call_id=getattr(tc, "id", ""),
                name=getattr(function, "name", ""),
                arguments=getattr(function, "arguments", ""),
            ),
        )

    return result


def _map_finish_reason(reason: str | None) -> FinishReason:
    """Map OpenAI finish reason to framework FinishReason."""
    if reason is None:
        return FinishReason.UNKNOWN

    return _FINISH_REASON_MAP.get(reason, FinishReason.UNKNOWN)


def _extract_metadata(response: Any) -> dict[str, Any]:
    """Extract additional metadata from OpenAI response."""
    metadata: dict[str, Any] = {}

    system_fingerprint = getattr(response, "system_fingerprint", None)
    if system_fingerprint is not None:
        metadata["system_fingerprint"] = system_fingerprint

    return metadata
