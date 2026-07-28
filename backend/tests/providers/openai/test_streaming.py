"""Tests for OpenAI streaming adapter."""

import pytest
from unittest.mock import MagicMock

from app.providers.models.enums import FinishReason
from app.providers.openai.streaming.adapter import adapt_stream, _map_chunk
from app.providers.streaming.chunk import StreamChunk, StreamEventType


def _make_stream_chunk(
    *,
    content: str | None = None,
    finish_reason: str | None = None,
    tool_calls: list | None = None,
    usage: dict | None = None,
) -> MagicMock:
    """Create a mock OpenAI stream chunk."""
    chunk = MagicMock()
    choice = MagicMock()
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls
    choice.delta = delta
    choice.finish_reason = finish_reason
    chunk.choices = [choice]
    chunk.usage = usage
    return chunk


class TestAdaptStream:
    """Tests for adapt_stream."""

    @pytest.mark.asyncio
    async def test_content_stream(self) -> None:
        chunks = [
            _make_stream_chunk(content="Hello"),
            _make_stream_chunk(content=" world"),
        ]

        async def mock_aiter():
            for c in chunks:
                yield c

        result = []
        async for chunk in adapt_stream(mock_aiter()):
            result.append(chunk)

        assert len(result) == 3
        assert result[0].event_type == StreamEventType.CONTENT_DELTA
        assert result[0].content_delta == "Hello"
        assert result[1].content_delta == " world"
        assert result[2].event_type == StreamEventType.FINISH
        assert result[2].finish_reason == FinishReason.STOP

    @pytest.mark.asyncio
    async def test_tool_call_stream(self) -> None:
        tc_start = MagicMock()
        tc_start.id = "call_1"
        func_start = MagicMock()
        func_start.name = "get_weather"
        func_start.arguments = ""
        tc_start.function = func_start

        tc_delta = MagicMock()
        tc_delta.id = "call_1"
        func_delta = MagicMock()
        func_delta.name = None
        func_delta.arguments = '{"city":'
        tc_delta.function = func_delta

        chunks = [
            _make_stream_chunk(tool_calls=[tc_start]),
            _make_stream_chunk(tool_calls=[tc_delta]),
        ]

        async def mock_aiter():
            for c in chunks:
                yield c

        result = []
        async for chunk in adapt_stream(mock_aiter()):
            result.append(chunk)

        assert result[0].event_type == StreamEventType.TOOL_CALL_START
        assert result[0].tool_call_name == "get_weather"
        assert result[1].event_type == StreamEventType.TOOL_CALL_DELTA
        assert result[2].finish_reason == FinishReason.STOP

    @pytest.mark.asyncio
    async def test_empty_stream(self) -> None:
        async def mock_aiter():
            return
            yield  # type: ignore[misc]

        result = []
        async for chunk in adapt_stream(mock_aiter()):
            result.append(chunk)

        assert len(result) == 1
        assert result[0].event_type == StreamEventType.FINISH


class TestMapChunk:
    """Tests for _map_chunk."""

    def test_content_chunk(self) -> None:
        raw = _make_stream_chunk(content="test")
        result = _map_chunk(raw, index=0)
        assert result is not None
        assert result.event_type == StreamEventType.CONTENT_DELTA
        assert result.content_delta == "test"

    def test_finish_chunk(self) -> None:
        raw = _make_stream_chunk(finish_reason="stop")
        result = _map_chunk(raw, index=0)
        assert result is not None
        assert result.event_type == StreamEventType.FINISH
        assert result.finish_reason == FinishReason.STOP

    def test_empty_choices(self) -> None:
        raw = MagicMock()
        raw.choices = []
        result = _map_chunk(raw, index=0)
        assert result is None

    def test_no_content_no_finish(self) -> None:
        raw = _make_stream_chunk()
        result = _map_chunk(raw, index=0)
        assert result is None
