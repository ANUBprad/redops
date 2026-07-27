"""Anthropic response mapping — converts SDK responses to framework models."""

from __future__ import annotations

import json
from typing import Any

from app.providers.models.enums import FinishReason
from app.providers.models.messages import ToolCallContent
from app.providers.models.responses import ChatResponse, Usage

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "max_tokens": FinishReason.LENGTH,
    "tool_use": FinishReason.TOOL_CALLS,
}


def map_chat_response(
    response: Any,  # noqa: ANN401
    *,
    provider: str = "anthropic",
) -> ChatResponse:
    """Map an Anthropic Message to a framework ChatResponse.

    Args:
        response: The raw Anthropic Message object.
        provider: Provider name for the response.

    Returns:
        A provider-agnostic ChatResponse.

    """
    usage = _map_usage(response.usage) if response.usage else Usage()
    content, tool_calls = _extract_content_and_tools(response.content)
    finish_reason = _map_finish_reason(getattr(response, "stop_reason", None))

    return ChatResponse(
        model=response.model,
        provider=provider,
        usage=usage,
        finish_reason=finish_reason,
        request_id=getattr(response, "id", None),
        content=content,
        tool_calls=tuple(tool_calls),
        metadata=_extract_metadata(response),
    )


def _map_usage(usage: Any) -> Usage:  # noqa: ANN401
    """Map Anthropic usage to framework Usage."""
    if usage is None:
        return Usage()

    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cached_tokens = cache_creation + cache_read

    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def _extract_content_and_tools(
    content: list[Any] | None,
) -> tuple[str, list[ToolCallContent]]:
    """Extract text content and tool calls from Anthropic content blocks."""
    text_parts: list[str] = []
    tool_calls: list[ToolCallContent] = []

    if not content:
        return "", tool_calls

    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", "")
            if text:
                text_parts.append(text)
        elif block_type == "tool_use":
            tool_calls.append(_map_tool_use_block(block))

    return "".join(text_parts), tool_calls


def _map_tool_use_block(block: Any) -> ToolCallContent:  # noqa: ANN401
    """Map an Anthropic tool_use block to ToolCallContent."""
    tool_input = getattr(block, "input", {})
    arguments = json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input)
    return ToolCallContent(
        tool_call_id=getattr(block, "id", ""),
        name=getattr(block, "name", ""),
        arguments=arguments,
    )


def _map_finish_reason(reason: str | None) -> FinishReason:
    """Map Anthropic stop_reason to framework FinishReason."""
    if reason is None:
        return FinishReason.UNKNOWN
    return _FINISH_REASON_MAP.get(reason, FinishReason.UNKNOWN)


def _extract_metadata(response: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract additional metadata from Anthropic response."""
    metadata: dict[str, Any] = {}
    stop_sequence = getattr(response, "stop_sequence", None)
    if stop_sequence is not None:
        metadata["stop_sequence"] = stop_sequence
    return metadata
