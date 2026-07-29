"""Tests for Anthropic streaming adapter."""

import pytest

from app.providers.anthropic.streaming.adapter import (
    _map_event,
    adapt_stream,
)
from app.providers.models.enums import FinishReason
from app.providers.streaming.chunk import StreamEventType


class ContentBlockDeltaEvent:
    def __init__(self, delta, index=0):
        self.delta = delta
        self.index = index


class ContentBlockStartEvent:
    def __init__(self, content_block, index=0):
        self.content_block = content_block
        self.index = index


class MessageDeltaEvent:
    def __init__(self, delta, usage=None):
        self.delta = delta
        self.usage = usage


class TextDelta:
    def __init__(self, text):
        self.type = "text_delta"
        self.text = text


class InputJsonDelta:
    def __init__(self, partial_json):
        self.type = "input_json_delta"
        self.partial_json = partial_json


class ToolUseBlock:
    def __init__(self, id, name):
        self.type = "tool_use"
        self.id = id
        self.name = name


class _MessageDelta:
    def __init__(self, stop_reason):
        self.stop_reason = stop_reason


class _Usage:
    def __init__(self, output_tokens=0):
        self.output_tokens = output_tokens


async def _run_stream(events):
    class FakeStream:
        def __init__(self, events):
            self._events = events

        async def __aenter__(self):
            async def aiter():
                for e in self._events:
                    yield e

            return aiter()

        async def __aexit__(self, *args):
            pass

    result = []
    async for chunk in adapt_stream(FakeStream(events)):
        result.append(chunk)
    return result


class TestAdaptStream:
    """Tests for adapt_stream."""

    @pytest.mark.asyncio
    async def test_text_stream(self) -> None:
        events = [
            ContentBlockDeltaEvent(TextDelta("Hello"), index=0),
            ContentBlockDeltaEvent(TextDelta(" world"), index=0),
        ]
        result = await _run_stream(events)
        assert len(result) == 3
        assert result[0].event_type == StreamEventType.CONTENT_DELTA
        assert result[0].content_delta == "Hello"
        assert result[1].event_type == StreamEventType.CONTENT_DELTA
        assert result[1].content_delta == " world"
        assert result[2].event_type == StreamEventType.FINISH
        assert result[2].finish_reason == FinishReason.STOP

    @pytest.mark.asyncio
    async def test_empty_stream(self) -> None:
        result = await _run_stream([])
        assert len(result) == 1
        assert result[0].event_type == StreamEventType.FINISH

    @pytest.mark.asyncio
    async def test_stream_error(self) -> None:
        class FailingStream:
            async def __aenter__(self):
                raise RuntimeError("connection lost")

            async def __aexit__(self, *args):
                pass

        result = []
        with pytest.raises(Exception):
            async for chunk in adapt_stream(FailingStream()):
                result.append(chunk)

        assert len(result) == 1
        assert result[0].event_type == StreamEventType.ERROR
        assert "connection lost" in result[0].error_message

    @pytest.mark.asyncio
    async def test_unknown_event_type_ignored(self) -> None:
        class UnknownEvent:
            pass

        events = [UnknownEvent()]
        result = await _run_stream(events)
        assert len(result) == 1
        assert result[0].event_type == StreamEventType.FINISH


class TestMapEvent:
    """Tests for _map_event."""

    def test_content_block_delta_text(self) -> None:
        event = ContentBlockDeltaEvent(TextDelta("Hello"), index=0)
        result = _map_event(event, index=0)
        assert result is not None
        assert result.event_type == StreamEventType.CONTENT_DELTA
        assert result.content_delta == "Hello"

    def test_content_block_delta_input_json(self) -> None:
        from app.providers.anthropic.streaming.adapter import _ACTIVE_TOOL_CALLS

        _ACTIVE_TOOL_CALLS.clear()
        _ACTIVE_TOOL_CALLS["0"] = "toolu_abc"

        event = ContentBlockDeltaEvent(InputJsonDelta('{"city":'), index=0)
        result = _map_event(event, index=0)
        assert result is not None
        assert result.event_type == StreamEventType.TOOL_CALL_DELTA
        assert result.tool_call_id == "toolu_abc"
        assert result.tool_call_arguments_delta == '{"city":'

        _ACTIVE_TOOL_CALLS.clear()

    def test_content_block_delta_no_delta(self) -> None:
        event = ContentBlockDeltaEvent(None, index=0)
        result = _map_event(event, index=0)
        assert result is None

    def test_content_block_delta_unknown_type(self) -> None:
        class UnknownDelta:
            type = "unknown_type"

        event = ContentBlockDeltaEvent(UnknownDelta(), index=0)
        result = _map_event(event, index=0)
        assert result is None

    def test_content_block_start_tool_use(self) -> None:
        from app.providers.anthropic.streaming.adapter import _ACTIVE_TOOL_CALLS

        _ACTIVE_TOOL_CALLS.clear()

        event = ContentBlockStartEvent(ToolUseBlock("toolu_abc", "get_weather"), index=0)
        result = _map_event(event, index=0)
        assert result is not None
        assert result.event_type == StreamEventType.TOOL_CALL_START
        assert result.tool_call_id == "toolu_abc"
        assert result.tool_call_name == "get_weather"

        _ACTIVE_TOOL_CALLS.clear()

    def test_content_block_start_text(self) -> None:
        class TextBlock:
            type = "text"

        event = ContentBlockStartEvent(TextBlock(), index=0)
        result = _map_event(event, index=0)
        assert result is None

    def test_content_block_start_no_content_block(self) -> None:
        event = ContentBlockStartEvent(None, index=0)
        result = _map_event(event, index=0)
        assert result is None

    def test_message_delta_end_turn(self) -> None:
        event = MessageDeltaEvent(_MessageDelta("end_turn"))
        result = _map_event(event, index=0)
        assert result is not None
        assert result.event_type == StreamEventType.FINISH
        assert result.finish_reason == FinishReason.STOP

    def test_message_delta_tool_use(self) -> None:
        event = MessageDeltaEvent(_MessageDelta("tool_use"))
        result = _map_event(event, index=0)
        assert result is not None
        assert result.finish_reason == FinishReason.TOOL_CALLS

    def test_message_delta_max_tokens(self) -> None:
        event = MessageDeltaEvent(_MessageDelta("max_tokens"))
        result = _map_event(event, index=0)
        assert result is not None
        assert result.finish_reason == FinishReason.LENGTH

    def test_message_delta_stop_sequence(self) -> None:
        event = MessageDeltaEvent(_MessageDelta("stop_sequence"))
        result = _map_event(event, index=0)
        assert result is not None
        assert result.finish_reason == FinishReason.STOP

    def test_message_delta_with_usage(self) -> None:
        event = MessageDeltaEvent(_MessageDelta("end_turn"), usage=_Usage(50))
        result = _map_event(event, index=0)
        assert result is not None
        assert result.usage_metadata["output_tokens"] == 50

    def test_message_delta_no_delta(self) -> None:
        event = MessageDeltaEvent(None)
        result = _map_event(event, index=0)
        assert result is None

    def test_message_delta_no_stop_reason(self) -> None:
        event = MessageDeltaEvent(_MessageDelta(None))
        result = _map_event(event, index=0)
        assert result is None

    def test_message_delta_unknown_stop_reason(self) -> None:
        event = MessageDeltaEvent(_MessageDelta("something_else"))
        result = _map_event(event, index=0)
        assert result is not None
        assert result.finish_reason == FinishReason.UNKNOWN

    def test_input_json_no_tool_call_id(self) -> None:
        from app.providers.anthropic.streaming.adapter import _ACTIVE_TOOL_CALLS

        _ACTIVE_TOOL_CALLS.clear()

        event = ContentBlockDeltaEvent(InputJsonDelta('{"x":1}'), index=0)
        result = _map_event(event, index=0)
        assert result is None

        _ACTIVE_TOOL_CALLS.clear()

    def test_input_json_empty_partial(self) -> None:
        from app.providers.anthropic.streaming.adapter import _ACTIVE_TOOL_CALLS

        _ACTIVE_TOOL_CALLS.clear()
        _ACTIVE_TOOL_CALLS["0"] = "toolu_1"

        event = ContentBlockDeltaEvent(InputJsonDelta(""), index=0)
        result = _map_event(event, index=0)
        assert result is None

        _ACTIVE_TOOL_CALLS.clear()

    def test_text_delta_empty_text(self) -> None:
        event = ContentBlockDeltaEvent(TextDelta(""), index=0)
        result = _map_event(event, index=0)
        assert result is None

    def test_message_delta_usage_none(self) -> None:
        event = MessageDeltaEvent(_MessageDelta("end_turn"), usage=None)
        result = _map_event(event, index=0)
        assert result is not None
        assert result.usage_metadata == {}

    def test_tool_use_empty_id(self) -> None:
        from app.providers.anthropic.streaming.adapter import _ACTIVE_TOOL_CALLS

        _ACTIVE_TOOL_CALLS.clear()

        event = ContentBlockStartEvent(ToolUseBlock("", "get_weather"), index=0)
        result = _map_event(event, index=0)
        assert result is None

        _ACTIVE_TOOL_CALLS.clear()

    def test_tool_use_empty_name(self) -> None:
        from app.providers.anthropic.streaming.adapter import _ACTIVE_TOOL_CALLS

        _ACTIVE_TOOL_CALLS.clear()

        event = ContentBlockStartEvent(ToolUseBlock("toolu_1", ""), index=0)
        result = _map_event(event, index=0)
        assert result is None

        _ACTIVE_TOOL_CALLS.clear()
