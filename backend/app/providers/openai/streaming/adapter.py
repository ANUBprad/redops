"""OpenAI streaming adapter — maps SDK chunks to framework StreamChunks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.providers.models.enums import FinishReason
from app.providers.openai.errors.mapping import wrap_streaming_error
from app.providers.streaming.chunk import StreamChunk

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "tool_calls": FinishReason.TOOL_CALLS,
    "content_filter": FinishReason.CONTENT_FILTER,
    "max_tokens": FinishReason.MAX_TOKENS,
}


async def adapt_stream(
    sdk_stream: Any,  # noqa: ANN401
    *,
    provider: str = "openai",  # noqa: ARG001
) -> AsyncIterator[StreamChunk]:
    """Adapt an OpenAI SDK stream to framework StreamChunks.

    Args:
        sdk_stream: The raw async stream from OpenAI.
        provider: Provider name for metadata.

    Yields:
        StreamChunk instances for each event in the stream.

    """
    chunk_index = 0

    try:
        async for chunk in sdk_stream:
            mapped = _map_chunk(chunk, index=chunk_index)
            if mapped is not None:
                yield mapped
                chunk_index += 1

        yield StreamChunk.finish(FinishReason.STOP, index=chunk_index)

    except Exception as exc:
        yield StreamChunk.error(
            message=str(exc),
            index=chunk_index,
        )
        raise wrap_streaming_error(exc, chunk_index=chunk_index) from exc


def _map_chunk(chunk: Any, *, index: int) -> StreamChunk | None:  # noqa: ANN401
    """Map a single OpenAI chunk to a StreamChunk."""
    choice = chunk.choices[0] if chunk.choices else None

    if choice is None:
        return None

    delta = choice.delta
    finish_reason = choice.finish_reason

    if delta and delta.content:
        return StreamChunk.content(text=delta.content, index=index)

    if delta and delta.tool_calls:
        return _map_tool_call_deltas(delta.tool_calls, index=index)

    if finish_reason:
        reason = _FINISH_REASON_MAP.get(finish_reason, FinishReason.UNKNOWN)
        usage = _extract_chunk_usage(chunk)
        return StreamChunk.finish(reason=reason, usage=usage, index=index)

    return None


def _map_tool_call_deltas(
    tool_calls: list[Any],
    *,
    index: int,
) -> StreamChunk | None:
    """Map tool call deltas from a stream chunk."""
    if not tool_calls:
        return None

    tc = tool_calls[0]
    function = getattr(tc, "function", None)

    if function is None:
        return None

    tc_id = getattr(tc, "id", None)
    name = getattr(function, "name", None)
    arguments = getattr(function, "arguments", "")

    if name and tc_id:
        return StreamChunk.tool_call_start(
            tool_call_id=tc_id,
            name=name,
            index=index,
        )

    if tc_id and arguments:
        return StreamChunk.tool_call_delta(
            tool_call_id=tc_id,
            arguments_delta=arguments,
            index=index,
        )

    return None


def _extract_chunk_usage(chunk: Any) -> dict[str, Any]:  # noqa: ANN401
    """Extract usage metadata from a stream chunk."""
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return {}

    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
