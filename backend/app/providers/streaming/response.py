"""Streaming response.

Aggregates stream chunks into a complete response,
assembling content, tool calls, and usage from the stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.providers.models.enums import FinishReason
from app.providers.models.messages import ToolCallContent
from app.providers.streaming.chunk import StreamChunk, StreamEventType


@dataclass
class StreamingResponse:
    """Accumulates stream chunks into a complete response.

    Collects content deltas, tool call deltas, and usage
    data from the stream into a final ChatResponse-like
    structure.
    """

    _content_parts: list[str] = field(default_factory=list, init=False)
    _tool_calls: dict[str, _ToolCallAccumulator] = field(
        default_factory=dict, init=False,
    )
    _finish_reason: FinishReason = field(
        default=FinishReason.UNKNOWN, init=False,
    )
    _usage: dict[str, Any] = field(default_factory=dict, init=False)
    _chunk_count: int = field(default=0, init=False)
    _error: str | None = field(default=None, init=False)

    def apply(self, chunk: StreamChunk) -> None:
        """Apply a stream chunk to the accumulator.

        Args:
            chunk: The chunk to apply.

        """
        self._chunk_count += 1

        if chunk.event_type == StreamEventType.CONTENT_DELTA:
            self._content_parts.append(chunk.content_delta)

        elif chunk.event_type == StreamEventType.TOOL_CALL_START:
            tc_id = chunk.tool_call_id or ""
            self._tool_calls[tc_id] = _ToolCallAccumulator(
                tool_call_id=tc_id,
                name=chunk.tool_call_name or "",
            )

        elif chunk.event_type == StreamEventType.TOOL_CALL_DELTA:
            tc_id = chunk.tool_call_id or ""
            if tc_id in self._tool_calls:
                self._tool_calls[tc_id].arguments_parts.append(
                    chunk.tool_call_arguments_delta,
                )

        elif chunk.event_type == StreamEventType.FINISH:
            if chunk.finish_reason is not None:
                self._finish_reason = chunk.finish_reason
            self._usage.update(chunk.usage_metadata)

        elif chunk.event_type == StreamEventType.ERROR:
            self._error = chunk.error_message

    @property
    def content(self) -> str:
        """Return the assembled content string."""
        return "".join(self._content_parts)

    @property
    def tool_calls(self) -> tuple[ToolCallContent, ...]:
        """Return assembled tool calls."""
        return tuple(
            ToolCallContent(
                tool_call_id=acc.tool_call_id,
                name=acc.name,
                arguments="".join(acc.arguments_parts),
            )
            for acc in self._tool_calls.values()
        )

    @property
    def finish_reason(self) -> FinishReason:
        """Return the finish reason."""
        return self._finish_reason

    @property
    def usage(self) -> dict[str, Any]:
        """Return usage metadata."""
        return dict(self._usage)

    @property
    def chunk_count(self) -> int:
        """Return the number of chunks processed."""
        return self._chunk_count

    @property
    def error(self) -> str | None:
        """Return the error message if any."""
        return self._error

    @property
    def is_error(self) -> bool:
        """Check if the stream encountered an error."""
        return self._error is not None


@dataclass
class _ToolCallAccumulator:
    """Accumulates tool call data across chunks."""

    tool_call_id: str
    name: str
    arguments_parts: list[str] = field(default_factory=list)
