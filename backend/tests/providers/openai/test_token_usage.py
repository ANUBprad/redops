"""Tests for OpenAI token usage extraction."""

from unittest.mock import MagicMock

from app.providers.openai.token_usage.analyzer import (
    extract_stream_usage,
    extract_usage,
)


class TestExtractUsage:
    """Tests for extract_usage."""

    def test_basic_usage(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        usage.total_tokens = 150
        usage.prompt_tokens_details = None
        usage.completion_tokens_details = None
        response.usage = usage

        result = extract_usage(response)
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150

    def test_none_usage(self) -> None:
        response = MagicMock()
        response.usage = None
        result = extract_usage(response)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_cached_tokens(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        usage.total_tokens = 150
        details = MagicMock()
        details.cached_tokens = 20
        details.audio_tokens = None
        usage.prompt_tokens_details = details
        usage.completion_tokens_details = None
        response.usage = usage

        result = extract_usage(response)
        assert result.cached_tokens == 20

    def test_audio_tokens(self) -> None:
        response = MagicMock()
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        usage.total_tokens = 150
        prompt_details = MagicMock()
        prompt_details.cached_tokens = None
        prompt_details.audio_tokens = 10
        usage.prompt_tokens_details = prompt_details
        comp_details = MagicMock()
        comp_details.audio_tokens = 5
        usage.completion_tokens_details = comp_details
        response.usage = usage

        result = extract_usage(response)
        assert result.audio_tokens == 10


class TestExtractStreamUsage:
    """Tests for extract_stream_usage."""

    def test_with_usage(self) -> None:
        chunk = MagicMock()
        usage = MagicMock()
        usage.prompt_tokens = 50
        usage.completion_tokens = 25
        usage.total_tokens = 75
        chunk.usage = usage

        result = extract_stream_usage(chunk)
        assert result is not None
        assert result.input_tokens == 50
        assert result.output_tokens == 25

    def test_without_usage(self) -> None:
        chunk = MagicMock()
        chunk.usage = None
        result = extract_stream_usage(chunk)
        assert result is None
