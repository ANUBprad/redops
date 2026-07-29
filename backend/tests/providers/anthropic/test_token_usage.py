"""Tests for Anthropic token usage extraction."""

from unittest.mock import MagicMock

from app.providers.anthropic.token_usage.analyzer import (
    extract_stream_usage,
    extract_usage,
)


class MessageStartEvent:
    def __init__(self, message=None):
        self.message = message


class MessageDeltaEvent:
    def __init__(self, usage=None):
        self.usage = usage


class _Usage:
    def __init__(self, input_tokens=None, output_tokens=None):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class TestExtractUsage:
    """Tests for extract_usage."""

    def test_basic_usage(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        response.usage = usage

        result = extract_usage(response)
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150
        assert result.cached_tokens == 0

    def test_none_usage(self) -> None:
        response = MagicMock()
        response.usage = None
        result = extract_usage(response)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_cached_tokens(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 20
        usage.cache_read_input_tokens = 30
        response.usage = usage

        result = extract_usage(response)
        assert result.cached_tokens == 50

    def test_cache_creation_only(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 15
        usage.cache_read_input_tokens = 0
        response.usage = usage

        result = extract_usage(response)
        assert result.cached_tokens == 15

    def test_cache_read_only(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 25
        response.usage = usage

        result = extract_usage(response)
        assert result.cached_tokens == 25

    def test_none_cache_tokens(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = None
        usage.cache_read_input_tokens = None
        response.usage = usage

        result = extract_usage(response)
        assert result.cached_tokens == 0

    def test_none_input_output_tokens(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.input_tokens = None
        usage.output_tokens = None
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        response.usage = usage

        result = extract_usage(response)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_no_usage_attribute(self) -> None:
        response = MagicMock(spec=[])
        result = extract_usage(response)
        assert result.input_tokens == 0
        assert result.output_tokens == 0


class TestExtractStreamUsage:
    """Tests for extract_stream_usage."""

    def test_message_start_event(self) -> None:
        event = MessageStartEvent(message=MagicMock(usage=_Usage(input_tokens=50)))
        result = extract_stream_usage(event)
        assert result is not None
        assert result.input_tokens == 50
        assert result.output_tokens == 0

    def test_message_start_event_no_usage(self) -> None:
        event = MessageStartEvent(message=MagicMock(usage=None))
        result = extract_stream_usage(event)
        assert result is None

    def test_message_start_event_no_message(self) -> None:
        event = MessageStartEvent(message=None)
        result = extract_stream_usage(event)
        assert result is None

    def test_message_delta_event(self) -> None:
        event = MessageDeltaEvent(usage=_Usage(output_tokens=30))
        result = extract_stream_usage(event)
        assert result is not None
        assert result.output_tokens == 30
        assert result.input_tokens == 0

    def test_message_delta_event_no_usage(self) -> None:
        event = MessageDeltaEvent(usage=None)
        result = extract_stream_usage(event)
        assert result is None

    def test_unknown_event_type(self) -> None:
        class ContentBlockDeltaEvent:
            pass

        event = ContentBlockDeltaEvent()
        result = extract_stream_usage(event)
        assert result is None

    def test_message_start_none_input_tokens(self) -> None:
        event = MessageStartEvent(message=MagicMock(usage=_Usage(input_tokens=None)))
        result = extract_stream_usage(event)
        assert result is not None
        assert result.input_tokens == 0

    def test_message_delta_none_output_tokens(self) -> None:
        event = MessageDeltaEvent(usage=_Usage(output_tokens=None))
        result = extract_stream_usage(event)
        assert result is not None
        assert result.output_tokens == 0
