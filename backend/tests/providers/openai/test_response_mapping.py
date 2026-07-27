"""Tests for OpenAI response mapping."""

from unittest.mock import MagicMock

from app.providers.models.enums import FinishReason
from app.providers.models.messages import ToolCallContent
from app.providers.models.responses import ChatResponse, Usage
from app.providers.openai.mappers.response import (
    _map_finish_reason,
    _map_tool_calls,
    _map_usage,
    map_chat_response,
)


def _make_openai_response(
    *,
    content: str = "Hello!",
    model: str = "gpt-4o",
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    tool_calls: list | None = None,
    response_id: str = "chatcmpl-123",
    system_fingerprint: str | None = None,
) -> MagicMock:
    """Create a mock OpenAI ChatCompletion."""
    response = MagicMock()
    response.model = model
    response.id = response_id
    response.system_fingerprint = system_fingerprint

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens
    usage.prompt_tokens_details = None
    usage.completion_tokens_details = None
    response.usage = usage

    choice = MagicMock()
    choice.finish_reason = finish_reason
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    choice.message = message
    response.choices = [choice]

    return response


class TestMapChatResponse:
    """Tests for map_chat_response."""

    def test_basic_response(self) -> None:
        raw = _make_openai_response(content="Hello!", model="gpt-4o")
        result = map_chat_response(raw)
        assert isinstance(result, ChatResponse)
        assert result.content == "Hello!"
        assert result.model == "gpt-4o"
        assert result.provider == "openai"
        assert result.finish_reason == FinishReason.STOP
        assert result.request_id == "chatcmpl-123"

    def test_usage_mapping(self) -> None:
        raw = _make_openai_response(
            prompt_tokens=20, completion_tokens=10, total_tokens=30,
        )
        result = map_chat_response(raw)
        assert result.usage.input_tokens == 20
        assert result.usage.output_tokens == 10
        assert result.usage.total_tokens == 30

    def test_tool_calls_mapping(self) -> None:
        tc = MagicMock()
        tc.id = "call_abc"
        function = MagicMock()
        function.name = "get_weather"
        function.arguments = '{"city":"NYC"}'
        tc.function = function

        raw = _make_openai_response(tool_calls=[tc], finish_reason="tool_calls")
        result = map_chat_response(raw)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_call_id == "call_abc"
        assert result.tool_calls[0].name == "get_weather"
        assert result.tool_calls[0].arguments == '{"city":"NYC"}'
        assert result.finish_reason == FinishReason.TOOL_CALLS

    def test_empty_choices(self) -> None:
        raw = _make_openai_response()
        raw.choices = []
        result = map_chat_response(raw)
        assert result.content == ""
        assert result.finish_reason == FinishReason.UNKNOWN

    def test_system_fingerprint_metadata(self) -> None:
        raw = _make_openai_response(system_fingerprint="fp_abc123")
        result = map_chat_response(raw)
        assert result.metadata["system_fingerprint"] == "fp_abc123"


class TestMapUsage:
    """Tests for _map_usage."""

    def test_basic_usage(self) -> None:
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        usage.total_tokens = 15
        usage.prompt_tokens_details = None
        usage.completion_tokens_details = None
        result = _map_usage(usage)
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.total_tokens == 15

    def test_none_usage(self) -> None:
        result = _map_usage(None)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_cached_tokens(self) -> None:
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        usage.total_tokens = 15
        details = MagicMock()
        details.cached_tokens = 3
        details.audio_tokens = None
        usage.prompt_tokens_details = details
        usage.completion_tokens_details = None
        result = _map_usage(usage)
        assert result.cached_tokens == 3


class TestMapFinishReason:
    """Tests for _map_finish_reason."""

    def test_stop(self) -> None:
        assert _map_finish_reason("stop") == FinishReason.STOP

    def test_length(self) -> None:
        assert _map_finish_reason("length") == FinishReason.LENGTH

    def test_tool_calls(self) -> None:
        assert _map_finish_reason("tool_calls") == FinishReason.TOOL_CALLS

    def test_none(self) -> None:
        assert _map_finish_reason(None) == FinishReason.UNKNOWN

    def test_unknown_reason(self) -> None:
        assert _map_finish_reason("something_else") == FinishReason.UNKNOWN


class TestMapToolCalls:
    """Tests for _map_tool_calls."""

    def test_empty(self) -> None:
        assert _map_tool_calls(None) == []
        assert _map_tool_calls([]) == []

    def test_maps_tool_calls(self) -> None:
        tc = MagicMock()
        tc.id = "call_1"
        func = MagicMock()
        func.name = "search"
        func.arguments = '{"q":"test"}'
        tc.function = func
        result = _map_tool_calls([tc])
        assert len(result) == 1
        assert isinstance(result[0], ToolCallContent)
        assert result[0].tool_call_id == "call_1"
        assert result[0].name == "search"
