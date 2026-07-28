"""Tests for provider exceptions."""

from __future__ import annotations

import pytest

from app.providers.exceptions import (
    AuthenticationRequired,
    ContextWindowExceeded,
    InvalidModel,
    ProviderException,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimitExceeded,
    StreamingFailure,
    TokenLimitExceeded,
)


class TestProviderException:
    """Tests for base provider exception."""

    def test_basic_creation(self) -> None:
        exc = ProviderException("test error")
        assert str(exc) == "test error"
        assert exc.error_code == "PROVIDER_ERROR"
        assert exc.retryable is False

    def test_with_provider_name(self) -> None:
        exc = ProviderException("error", provider_name="openai")
        assert exc.provider_name == "openai"

    def test_with_model_id(self) -> None:
        exc = ProviderException("error", model_id="gpt-4")
        assert exc.model_id == "gpt-4"

    def test_retryable(self) -> None:
        exc = ProviderException("error", retryable=True)
        assert exc.retryable is True


class TestAvailabilityErrors:
    """Tests for availability exceptions."""

    def test_provider_unavailable(self) -> None:
        exc = ProviderUnavailable()
        assert exc.error_code == "PROVIDER_UNAVAILABLE"
        assert exc.retryable is True

    def test_provider_unavailable_custom_message(self) -> None:
        exc = ProviderUnavailable("custom message")
        assert str(exc) == "custom message"


class TestModelError:
    """Tests for model validation errors."""

    def test_invalid_model(self) -> None:
        exc = InvalidModel(model_id="gpt-99")
        assert exc.error_code == "INVALID_MODEL"
        assert exc.model_id == "gpt-99"
        assert exc.retryable is False


class TestLimitErrors:
    """Tests for limit exceptions."""

    def test_context_window_exceeded(self) -> None:
        exc = ContextWindowExceeded(context_window=4096, token_count=5000)
        assert exc.error_code == "CONTEXT_WINDOW_EXCEEDED"
        assert exc.details["context_window"] == 4096
        assert exc.details["token_count"] == 5000

    def test_token_limit_exceeded(self) -> None:
        exc = TokenLimitExceeded(max_tokens=4096)
        assert exc.error_code == "TOKEN_LIMIT_EXCEEDED"
        assert exc.details["max_tokens"] == 4096


class TestAuthError:
    """Tests for authentication errors."""

    def test_authentication_required(self) -> None:
        exc = AuthenticationRequired(provider_name="anthropic")
        assert exc.error_code == "AUTHENTICATION_REQUIRED"
        assert exc.provider_name == "anthropic"
        assert exc.retryable is False


class TestStreamingError:
    """Tests for streaming errors."""

    def test_streaming_failure(self) -> None:
        exc = StreamingFailure(chunk_index=5)
        assert exc.error_code == "STREAMING_FAILURE"
        assert exc.details["chunk_index"] == 5
        assert exc.retryable is True


class TestRateLimitError:
    """Tests for rate limit errors."""

    def test_rate_limit_exceeded(self) -> None:
        exc = RateLimitExceeded(retry_after_seconds=30.0)
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.retry_after_seconds == 30.0
        assert exc.retryable is True


class TestTimeoutError:
    """Tests for timeout errors."""

    def test_provider_timeout(self) -> None:
        exc = ProviderTimeout(timeout_seconds=30.0)
        assert exc.error_code == "PROVIDER_TIMEOUT"
        assert exc.timeout_seconds == 30.0
        assert exc.retryable is True
