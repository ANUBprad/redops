"""Anthropic streaming adapter — maps SDK events to framework StreamChunks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.providers.anthropic.errors.mapping import wrap_streaming_error
from app.providers.models.enums import FinishReason
from app.providers.streaming.chunk import StreamChunk

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "max_tokens": FinishReason.LENGTH,
    "tool_use": FinishReason.TOOL_CALLS,
}

_ACTIVE_TOOL_CALLS: dict[str, str] = {}


async def adapt_stream(
    sdk_stream: Any,
    *,
    provider: str = "anthropic",
) -> AsyncIterator[StreamChunk]:
    """Adapt an Anthropic SDK stream to framework StreamChunks.

    Args:
        sdk_stream: The raw async stream from Anthropic.
        provider: Provider name for metadata.

    Yields:
        StreamChunk instances for each event in the stream.

    """
    chunk_index = 0
    _ACTIVE_TOOL_CALLS.clear()

    try:
        async with sdk_stream as stream:
            async for event in stream:
                mapped = _map_event(event, index=chunk_index)
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


_EVENT_HANDLERS: dict[str, str] = {
    "ContentBlockDeltaEvent": "_map_content_delta",
    "ContentBlockStartEvent": "_map_content_block_start",
    "MessageDeltaEvent": "_map_message_delta",
}


def _map_event(event: Any, *, index: int) -> StreamChunk | None:
    """Map a single Anthropic stream event to a StreamChunk."""
    event_type = type(event).__name__
    handler_name = _EVENT_HANDLERS.get(event_type)

    if handler_name is None:
        return None

    handler = globals()[handler_name]
    return handler(event, index=index)


def _map_content_delta(event: Any, *, index: int) -> StreamChunk | None:
    """Map a ContentBlockDeltaEvent to a StreamChunk."""
    delta = getattr(event, "delta", None)
    if delta is None:
        return None

    delta_type = getattr(delta, "type", None)

    if delta_type == "text_delta":
        text = getattr(delta, "text", "")
        if text:
            return StreamChunk.content(text=text, index=index)

    if delta_type == "input_json_delta":
        partial_json = getattr(delta, "partial_json", "")
        if partial_json:
            block_index = getattr(event, "index", 0)
            tool_call_id = _find_tool_call_id(block_index)
            if tool_call_id:
                return StreamChunk.tool_call_delta(
                    tool_call_id=tool_call_id,
                    arguments_delta=partial_json,
                    index=index,
                )

    return None


def _map_content_block_start(event: Any, *, index: int) -> StreamChunk | None:
    """Map a ContentBlockStartEvent to a StreamChunk."""
    content_block = getattr(event, "content_block", None)
    if content_block is None:
        return None

    block_type = getattr(content_block, "type", None)
    if block_type == "tool_use":
        tool_id = getattr(content_block, "id", "")
        tool_name = getattr(content_block, "name", "")
        block_index = getattr(event, "index", 0)
        _ACTIVE_TOOL_CALLS[str(block_index)] = tool_id
        if tool_id and tool_name:
            return StreamChunk.tool_call_start(
                tool_call_id=tool_id,
                name=tool_name,
                index=index,
            )

    return None


def _map_message_delta(event: Any, *, index: int) -> StreamChunk | None:
    """Map a MessageDeltaEvent to a StreamChunk."""
    delta = getattr(event, "delta", None)
    if delta is None:
        return None

    stop_reason = getattr(delta, "stop_reason", None)
    if stop_reason:
        reason = _FINISH_REASON_MAP.get(stop_reason, FinishReason.UNKNOWN)
        usage = _extract_message_delta_usage(event)
        return StreamChunk.finish(reason=reason, usage=usage, index=index)

    return None


def _find_tool_call_id(block_index: int) -> str | None:
    """Find tool call ID by content block index."""
    return _ACTIVE_TOOL_CALLS.get(str(block_index))


def _extract_message_delta_usage(event: Any) -> dict[str, Any]:
    """Extract usage metadata from a MessageDeltaEvent."""
    usage = getattr(event, "usage", None)
    if usage is None:
        return {}

    output_tokens = getattr(usage, "output_tokens", 0) or 0
    return {
        "output_tokens": output_tokens,
    }
