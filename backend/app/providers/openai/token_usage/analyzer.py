"""OpenAI token usage extraction."""

from __future__ import annotations

from typing import Any

from app.providers.models.responses import Usage


def extract_usage(response: Any) -> Usage:
    """Extract token usage from an OpenAI response.

    Args:
        response: Raw OpenAI ChatCompletion or embedding response.

    Returns:
        Framework Usage object with token counts.

    """
    usage = getattr(response, "usage", None)
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


def extract_stream_usage(chunk: Any) -> Usage | None:
    """Extract token usage from a streaming chunk.

    Only the final chunk contains usage data.

    Args:
        chunk: Raw OpenAI ChatCompletionChunk.

    Returns:
        Usage object if usage data present, None otherwise.

    """
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return None

    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or 0

    return Usage(
        input_tokens=prompt_tokens,
        output_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _extract_cached_tokens(usage: Any) -> int:
    """Extract cached tokens from OpenAI usage."""
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", None)
        if cached is not None:
            return int(cached)
    return 0


def _extract_audio_tokens(usage: Any) -> int:
    """Extract audio tokens from OpenAI usage."""
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details is not None:
        audio = getattr(prompt_details, "audio_tokens", None)
        if audio is not None:
            return int(audio)

    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details is not None:
        audio = getattr(completion_details, "audio_tokens", None)
        if audio is not None:
            return int(audio)

    return 0
