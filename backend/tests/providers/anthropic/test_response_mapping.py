"""Tests for Anthropic response mapping."""

import json
from unittest.mock import MagicMock

from app.providers.models.enums import FinishReason
from app.providers.models.messages import ToolCallContent
from app.providers.models.responses import ChatResponse, Usage
from app.providers.anthropic.mappers.response import (
    _extract_content_and_tools,
    _map_finish_reason,
    _map_usage,
    map_chat_response,
)


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_block(id: str, name: str, input: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = id
    block.name = name
    block.input = input
    return block


def _make_anthropic_response(
    *,
    content: list | None = None,
    text: str | None = "Hello!",
    model: str = "claude-sonnet-4-20250514",
    stop_reason: str | None = "end_turn",
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    response_id: str = "msg_abc123",
    stop_sequence: str | None = None,
) -> MagicMock:
    response = MagicMock()
    response.model = model
    response.id = response_id
    response.stop_reason = stop_reason
    response.stop_sequence = stop_sequence

    if content is None:
        content = [_make_text_block(text)] if text is not None else []
    response.content = content

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_creation_input_tokens = cache_creation_input_tokens
    usage.cache_read_input_tokens = cache_read_input_tokens
    response.usage = usage

    return response


class TestMapChatResponse:
    """Tests for map_chat_response."""

    def test_basic_response(self) -> None:
        raw = _make_anthropic_response(text="Hello!", model="claude-sonnet-4-20250514")
        result = map_chat_response(raw)
        assert isinstance(result, ChatResponse)
        assert result.content == "Hello!"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.provider == "anthropic"
        assert result.finish_reason == FinishReason.STOP
        assert result.request_id == "msg_abc123"

    def test_tool_calls_response(self) -> None:
        tool_block = _make_tool_block("toolu_abc", "get_weather", {"city": "NYC"})
        raw = _make_anthropic_response(content=[tool_block], stop_reason="tool_use")
        result = map_chat_response(raw)
        assert result.finish_reason == FinishReason.TOOL_CALLS
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_call_id == "toolu_abc"
        assert result.tool_calls[0].name == "get_weather"
        assert json.loads(result.tool_calls[0].arguments) == {"city": "NYC"}

    def test_mixed_content_and_tools(self) -> None:
        text_block = _make_text_block("Let me check.")
        tool_block = _make_tool_block("toolu_1", "search", {"q": "test"})
        raw = _make_anthropic_response(content=[text_block, tool_block], stop_reason="tool_use")
        result = map_chat_response(raw)
        assert result.content == "Let me check."
        assert len(result.tool_calls) == 1

    def test_empty_content(self) -> None:
        raw = _make_anthropic_response(content=[])
        result = map_chat_response(raw)
        assert result.content == ""
        assert result.tool_calls == ()

    def test_none_content(self) -> None:
        raw = _make_anthropic_response(text=None)
        result = map_chat_response(raw)
        assert result.content == ""

    def test_stop_sequence_in_metadata(self) -> None:
        raw = _make_anthropic_response(stop_sequence="END")
        result = map_chat_response(raw)
        assert result.metadata["stop_sequence"] == "END"

    def test_no_stop_sequence(self) -> None:
        raw = _make_anthropic_response(stop_sequence=None)
        result = map_chat_response(raw)
        assert "stop_sequence" not in result.metadata

    def test_custom_provider(self) -> None:
        raw = _make_anthropic_response()
        result = map_chat_response(raw, provider="custom")
        assert result.provider == "custom"


class TestMapUsage:
    """Tests for _map_usage."""

    def test_basic_usage(self) -> None:
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        result = _map_usage(usage)
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150
        assert result.cached_tokens == 0

    def test_none_usage(self) -> None:
        result = _map_usage(None)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_cached_tokens_from_cache_creation_and_read(self) -> None:
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 20
        usage.cache_read_input_tokens = 30
        result = _map_usage(usage)
        assert result.cached_tokens == 50

    def test_cached_tokens_only_creation(self) -> None:
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 15
        usage.cache_read_input_tokens = 0
        result = _map_usage(usage)
        assert result.cached_tokens == 15

    def test_cached_tokens_only_read(self) -> None:
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 25
        result = _map_usage(usage)
        assert result.cached_tokens == 25

    def test_none_cache_tokens(self) -> None:
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = None
        usage.cache_read_input_tokens = None
        result = _map_usage(usage)
        assert result.cached_tokens == 0

    def test_none_input_output_tokens(self) -> None:
        usage = MagicMock()
        usage.input_tokens = None
        usage.output_tokens = None
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        result = _map_usage(usage)
        assert result.input_tokens == 0
        assert result.output_tokens == 0


class TestMapFinishReason:
    """Tests for _map_finish_reason."""

    def test_end_turn(self) -> None:
        assert _map_finish_reason("end_turn") == FinishReason.STOP

    def test_stop_sequence(self) -> None:
        assert _map_finish_reason("stop_sequence") == FinishReason.STOP

    def test_max_tokens(self) -> None:
        assert _map_finish_reason("max_tokens") == FinishReason.LENGTH

    def test_tool_use(self) -> None:
        assert _map_finish_reason("tool_use") == FinishReason.TOOL_CALLS

    def test_none(self) -> None:
        assert _map_finish_reason(None) == FinishReason.UNKNOWN

    def test_unknown_reason(self) -> None:
        assert _map_finish_reason("something_else") == FinishReason.UNKNOWN


class TestExtractContentAndTools:
    """Tests for _extract_content_and_tools."""

    def test_text_only(self) -> None:
        block = _make_text_block("Hello!")
        content, tools = _extract_content_and_tools([block])
        assert content == "Hello!"
        assert tools == []

    def test_tool_use_only(self) -> None:
        block = _make_tool_block("toolu_1", "search", {"q": "test"})
        content, tools = _extract_content_and_tools([block])
        assert content == ""
        assert len(tools) == 1
        assert isinstance(tools[0], ToolCallContent)
        assert tools[0].tool_call_id == "toolu_1"

    def test_mixed_content(self) -> None:
        text_block = _make_text_block("Thinking...")
        tool_block = _make_tool_block("toolu_2", "calc", {"x": 1})
        content, tools = _extract_content_and_tools([text_block, tool_block])
        assert content == "Thinking..."
        assert len(tools) == 1

    def test_empty_content(self) -> None:
        content, tools = _extract_content_and_tools([])
        assert content == ""
        assert tools == []

    def test_none_content(self) -> None:
        content, tools = _extract_content_and_tools(None)
        assert content == ""
        assert tools == []

    def test_empty_text_block(self) -> None:
        block = _make_text_block("")
        content, tools = _extract_content_and_tools([block])
        assert content == ""

    def test_tool_use_non_dict_input(self) -> None:
        block = _make_tool_block("toolu_3", "log", "not a dict")
        content, tools = _extract_content_and_tools([block])
        assert len(tools) == 1
        assert tools[0].arguments == "not a dict"

    def test_unknown_block_type(self) -> None:
        block = MagicMock()
        block.type = "unknown_type"
        content, tools = _extract_content_and_tools([block])
        assert content == ""
        assert tools == []
