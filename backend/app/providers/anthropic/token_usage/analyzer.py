"""Anthropic token usage extraction."""

from __future__ import annotations

from typing import Any

from app.providers.models.responses import Usage


def extract_usage(response: Any) -> Usage:  # noqa: ANN401
    """Extract token usage from an Anthropic response.

    Args:
        response: Raw Anthropic Message object.

    Returns:
        Framework Usage object with token counts.

    """
    usage = getattr(response, "usage", None)
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


def extract_stream_usage(chunk: Any) -> Usage | None:  # noqa: ANN401
    """Extract token usage from a streaming event.

    Only the message_start and message_delta events contain usage data.

    Args:
        chunk: Raw Anthropic stream event.

    Returns:
        Usage object if usage data present, None otherwise.

    """
    event_type = type(chunk).__name__

    if event_type == "MessageStartEvent":
        usage = getattr(chunk, "message", None)
        if usage is not None:
            usage_obj = getattr(usage, "usage", None)
            if usage_obj is not None:
                input_tokens = getattr(usage_obj, "input_tokens", 0) or 0
                return Usage(input_tokens=input_tokens)

    if event_type == "MessageDeltaEvent":
        usage = getattr(chunk, "usage", None)
        if usage is not None:
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            return Usage(output_tokens=output_tokens)

    return None
