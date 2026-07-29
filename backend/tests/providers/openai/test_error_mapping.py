"""Tests for OpenAI error mapping."""

from unittest.mock import MagicMock

from openai import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

from app.providers.exceptions.auth import AuthenticationRequired
from app.providers.exceptions.availability import ProviderUnavailable
from app.providers.exceptions.limits import ContextWindowExceeded, TokenLimitExceeded
from app.providers.exceptions.model import InvalidModel
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.exceptions.streaming import StreamingFailure
from app.providers.exceptions.timeout import ProviderTimeout
from app.providers.openai.errors.mapping import map_openai_error, wrap_streaming_error


def _make_response(status: int, headers: dict | None = None) -> MagicMock:
    """Create a mock httpx.Response for OpenAI exceptions."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.request = MagicMock()
    resp.request.url = "https://api.openai.com/v1/chat/completions"
    resp.content = b'{"error": {"message": "test", "type": "test"}}'
    return resp


class TestMapOpenaiError:
    """Tests for map_openai_error."""

    def test_authentication_error(self) -> None:
        exc = AuthenticationError(
            message="Invalid API key",
            response=_make_response(401),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, AuthenticationRequired)
        assert result.provider_name == "openai"
        assert result.retryable is False

    def test_not_found_error(self) -> None:
        exc = NotFoundError(
            message="Model not found",
            response=_make_response(404),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, InvalidModel)
        assert result.provider_name == "openai"

    def test_rate_limit_error(self) -> None:
        exc = RateLimitError(
            message="Rate limited",
            response=_make_response(429, {"retry-after": "30"}),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, RateLimitExceeded)
        assert result.retry_after_seconds == 30.0

    def test_rate_limit_no_retry_after(self) -> None:
        exc = RateLimitError(
            message="Rate limited",
            response=_make_response(429),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, RateLimitExceeded)
        assert result.retry_after_seconds is None

    def test_bad_request_context_length(self) -> None:
        exc = BadRequestError(
            message="context_length_exceeded",
            response=_make_response(400),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, ContextWindowExceeded)

    def test_bad_request_max_tokens(self) -> None:
        exc = BadRequestError(
            message="max_tokens exceeded",
            response=_make_response(400),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, TokenLimitExceeded)

    def test_bad_request_model_not_found(self) -> None:
        exc = BadRequestError(
            message="model not found",
            response=_make_response(400),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, InvalidModel)

    def test_internal_server_error(self) -> None:
        exc = InternalServerError(
            message="Server error",
            response=_make_response(500),
            body=None,
        )
        result = map_openai_error(exc)
        assert isinstance(result, ProviderUnavailable)
        assert result.retryable is True

    def test_api_connection_error(self) -> None:
        exc = APIConnectionError(request=MagicMock())
        result = map_openai_error(exc)
        assert isinstance(result, ProviderUnavailable)
        assert result.retryable is True

    def test_timeout_error(self) -> None:
        result = map_openai_error(TimeoutError("timed out"))
        assert isinstance(result, ProviderTimeout)

    def test_unexpected_error(self) -> None:
        result = map_openai_error(ValueError("something weird"))
        assert isinstance(result, ProviderUnavailable)
        assert "Unexpected" in str(result)


class TestWrapStreamingError:
    """Tests for wrap_streaming_error."""

    def test_wraps_provider_exception(self) -> None:
        original = AuthenticationRequired(message="auth failed")
        result = wrap_streaming_error(original, chunk_index=5)
        assert isinstance(result, StreamingFailure)
        assert result.details.get("chunk_index") == 5

    def test_wraps_generic_exception(self) -> None:
        result = wrap_streaming_error(RuntimeError("oops"), chunk_index=3)
        assert isinstance(result, StreamingFailure)
        assert result.details.get("chunk_index") == 3
