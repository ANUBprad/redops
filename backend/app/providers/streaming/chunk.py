"""Stream chunk types.

Defines the data structures for individual streaming events.
Each chunk carries a portion of the response or a control event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, unique
from typing import Any

from app.providers.models.enums import FinishReason  # noqa: TC001


@unique
class StreamEventType(StrEnum):
    """Type of stream event."""

    CONTENT_DELTA = "content_delta"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_START = "tool_call_start"
    FINISH = "finish"
    ERROR = "error"
    USAGE = "usage"
    HEARTBEAT = "heartbeat"


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """A single chunk in a streaming response.

    Carries either content deltas, tool call deltas,
    or control events (finish, error, usage).
    """

    event_type: StreamEventType
    index: int = 0
    content_delta: str = ""
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_arguments_delta: str = ""
    finish_reason: FinishReason | None = None
    usage_metadata: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def content(cls, text: str, index: int = 0) -> StreamChunk:
        """Create a content delta chunk."""
        return cls(
            event_type=StreamEventType.CONTENT_DELTA,
            index=index,
            content_delta=text,
        )

    @classmethod
    def tool_call_start(
        cls,
        tool_call_id: str,
        name: str,
        index: int = 0,
    ) -> StreamChunk:
        """Create a tool call start chunk."""
        return cls(
            event_type=StreamEventType.TOOL_CALL_START,
            index=index,
            tool_call_id=tool_call_id,
            tool_call_name=name,
        )

    @classmethod
    def tool_call_delta(
        cls,
        tool_call_id: str,
        arguments_delta: str,
        index: int = 0,
    ) -> StreamChunk:
        """Create a tool call arguments delta chunk."""
        return cls(
            event_type=StreamEventType.TOOL_CALL_DELTA,
            index=index,
            tool_call_id=tool_call_id,
            tool_call_arguments_delta=arguments_delta,
        )

    @classmethod
    def finish(
        cls,
        reason: FinishReason,
        usage: dict[str, Any] | None = None,
        index: int = 0,
    ) -> StreamChunk:
        """Create a finish chunk."""
        return cls(
            event_type=StreamEventType.FINISH,
            index=index,
            finish_reason=reason,
            usage_metadata=usage or {},
        )

    @classmethod
    def error(cls, message: str, index: int = 0) -> StreamChunk:
        """Create an error chunk."""
        return cls(
            event_type=StreamEventType.ERROR,
            index=index,
            error_message=message,
        )

    @classmethod
    def heartbeat(cls, index: int = 0) -> StreamChunk:
        """Create a heartbeat chunk."""
        return cls(
            event_type=StreamEventType.HEARTBEAT,
            index=index,
        )
