"""Tests for streaming framework."""

from __future__ import annotations

import pytest

from app.providers.models.enums import FinishReason
from app.providers.streaming.backpressure import BackpressureManager
from app.providers.streaming.chunk import StreamChunk, StreamEventType
from app.providers.streaming.response import StreamingResponse


class TestStreamChunk:
    """Tests for StreamChunk."""

    def test_content_chunk(self) -> None:
        chunk = StreamChunk.content("hello", index=0)
        assert chunk.event_type == StreamEventType.CONTENT_DELTA
        assert chunk.content_delta == "hello"
        assert chunk.index == 0

    def test_tool_call_start(self) -> None:
        chunk = StreamChunk.tool_call_start("tc_1", "get_weather")
        assert chunk.event_type == StreamEventType.TOOL_CALL_START
        assert chunk.tool_call_id == "tc_1"
        assert chunk.tool_call_name == "get_weather"

    def test_tool_call_delta(self) -> None:
        chunk = StreamChunk.tool_call_delta("tc_1", '{"city":')
        assert chunk.event_type == StreamEventType.TOOL_CALL_DELTA
        assert chunk.tool_call_arguments_delta == '{"city":'

    def test_finish_chunk(self) -> None:
        chunk = StreamChunk.finish(FinishReason.STOP, usage={"tokens": 100})
        assert chunk.event_type == StreamEventType.FINISH
        assert chunk.finish_reason == FinishReason.STOP
        assert chunk.usage_metadata["tokens"] == 100

    def test_error_chunk(self) -> None:
        chunk = StreamChunk.error("something went wrong")
        assert chunk.event_type == StreamEventType.ERROR
        assert chunk.error_message == "something went wrong"

    def test_heartbeat_chunk(self) -> None:
        chunk = StreamChunk.heartbeat()
        assert chunk.event_type == StreamEventType.HEARTBEAT


class TestStreamingResponse:
    """Tests for StreamingResponse accumulator."""

    def test_content_assembly(self) -> None:
        sr = StreamingResponse()
        sr.apply(StreamChunk.content("hello"))
        sr.apply(StreamChunk.content(" world"))
        assert sr.content == "hello world"

    def test_tool_call_assembly(self) -> None:
        sr = StreamingResponse()
        sr.apply(StreamChunk.tool_call_start("tc_1", "get_weather"))
        sr.apply(StreamChunk.tool_call_delta("tc_1", '{"city":'))
        sr.apply(StreamChunk.tool_call_delta("tc_1", '"NYC"}'))
        assert len(sr.tool_calls) == 1
        assert sr.tool_calls[0].name == "get_weather"
        assert sr.tool_calls[0].arguments == '{"city":"NYC"}'

    def test_finish(self) -> None:
        sr = StreamingResponse()
        sr.apply(StreamChunk.finish(FinishReason.STOP, usage={"tokens": 10}))
        assert sr.finish_reason == FinishReason.STOP
        assert sr.usage["tokens"] == 10

    def test_error(self) -> None:
        sr = StreamingResponse()
        sr.apply(StreamChunk.error("fail"))
        assert sr.is_error
        assert sr.error == "fail"

    def test_chunk_count(self) -> None:
        sr = StreamingResponse()
        sr.apply(StreamChunk.content("a"))
        sr.apply(StreamChunk.content("b"))
        assert sr.chunk_count == 2


class TestBackpressureManager:
    """Tests for BackpressureManager."""

    def test_initial_state(self) -> None:
        bp = BackpressureManager()
        assert not bp.is_paused
        assert bp.buffer_size == 0

    def test_should_pause(self) -> None:
        bp = BackpressureManager(high_watermark=3)
        bp.add_to_buffer("a")
        bp.add_to_buffer("b")
        assert not bp.should_pause()
        bp.add_to_buffer("c")
        assert bp.should_pause()
        assert bp.is_paused

    def test_should_resume(self) -> None:
        bp = BackpressureManager(high_watermark=3, low_watermark=1)
        bp.add_to_buffer("a")
        bp.add_to_buffer("b")
        bp.add_to_buffer("c")
        bp.should_pause()
        # Each take_from_buffer calls should_resume internally
        bp.take_from_buffer()  # buffer=2, not resumed yet
        assert bp.is_paused
        bp.take_from_buffer()  # buffer=1, auto-resumes
        assert not bp.is_paused

    def test_take_from_buffer(self) -> None:
        bp = BackpressureManager()
        bp.add_to_buffer("item1")
        bp.add_to_buffer("item2")
        assert bp.take_from_buffer() == "item1"
        assert bp.take_from_buffer() == "item2"
        assert bp.take_from_buffer() is None

    def test_clear_buffer(self) -> None:
        bp = BackpressureManager(high_watermark=2)
        bp.add_to_buffer("a")
        bp.add_to_buffer("b")
        bp.should_pause()
        bp.clear_buffer()
        assert bp.buffer_size == 0
        assert not bp.is_paused
