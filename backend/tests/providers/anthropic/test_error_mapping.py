"""Tests for Anthropic error mapping."""

from unittest.mock import MagicMock

from anthropic import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

from app.providers.anthropic.errors.mapping import map_anthropic_error, wrap_streaming_error
from app.providers.exceptions.auth import AuthenticationRequired
from app.providers.exceptions.availability import ProviderUnavailable
from app.providers.exceptions.limits import ContextWindowExceeded, TokenLimitExceeded
from app.providers.exceptions.model import InvalidModel
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.exceptions.streaming import StreamingFailure
from app.providers.exceptions.timeout import ProviderTimeout


def _make_response(status: int, headers: dict | None = None) -> MagicMock:
    """Create a mock httpx.Response for Anthropic exceptions."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.request = MagicMock()
    resp.request.url = "https://api.anthropic.com/v1/messages"
    resp.content = b'{"error": {"message": "test", "type": "test"}}'
    return resp


class TestMapAnthropicError:
    """Tests for map_anthropic_error."""

    def test_authentication_error(self) -> None:
        exc = AuthenticationError(
            message="Invalid API key",
            response=_make_response(401),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, AuthenticationRequired)
        assert result.provider_name == "anthropic"
        assert result.retryable is False

    def test_not_found_error(self) -> None:
        exc = NotFoundError(
            message="Model not found",
            response=_make_response(404),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, InvalidModel)
        assert result.provider_name == "anthropic"

    def test_rate_limit_error(self) -> None:
        exc = RateLimitError(
            message="Rate limited",
            response=_make_response(429, {"retry-after": "30"}),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, RateLimitExceeded)
        assert result.retry_after_seconds == 30.0

    def test_rate_limit_no_retry_after(self) -> None:
        exc = RateLimitError(
            message="Rate limited",
            response=_make_response(429),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, RateLimitExceeded)
        assert result.retry_after_seconds is None

    def test_rate_limit_invalid_retry_after(self) -> None:
        exc = RateLimitError(
            message="Rate limited",
            response=_make_response(429, {"retry-after": "not-a-number"}),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, RateLimitExceeded)
        assert result.retry_after_seconds is None

    def test_rate_limit_capital_retry_after(self) -> None:
        exc = RateLimitError(
            message="Rate limited",
            response=_make_response(429, {"Retry-After": "15"}),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, RateLimitExceeded)
        assert result.retry_after_seconds == 15.0

    def test_bad_request_context_length(self) -> None:
        exc = BadRequestError(
            message="context_length exceeded",
            response=_make_response(400),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ContextWindowExceeded)

    def test_bad_request_maximum_context(self) -> None:
        exc = BadRequestError(
            message="maximum context length exceeded",
            response=_make_response(400),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ContextWindowExceeded)

    def test_bad_request_max_tokens(self) -> None:
        exc = BadRequestError(
            message="max_tokens exceeded",
            response=_make_response(400),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, TokenLimitExceeded)

    def test_bad_request_maximum_tokens(self) -> None:
        exc = BadRequestError(
            message="maximum tokens limit reached",
            response=_make_response(400),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, TokenLimitExceeded)

    def test_bad_request_model_not_found(self) -> None:
        exc = BadRequestError(
            message="model not found",
            response=_make_response(400),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, InvalidModel)

    def test_bad_request_model_does_not_exist(self) -> None:
        exc = BadRequestError(
            message="model does not exist: claude-xyz",
            response=_make_response(400),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, InvalidModel)

    def test_bad_request_generic(self) -> None:
        exc = BadRequestError(
            message="something else went wrong",
            response=_make_response(400),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ProviderUnavailable)

    def test_internal_server_error(self) -> None:
        exc = InternalServerError(
            message="Server error",
            response=_make_response(500),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ProviderUnavailable)
        assert result.retryable is True

    def test_bad_gateway_error(self) -> None:
        exc = InternalServerError(
            message="Bad gateway",
            response=_make_response(502),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ProviderUnavailable)

    def test_service_unavailable_error(self) -> None:
        exc = InternalServerError(
            message="Service unavailable",
            response=_make_response(503),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ProviderUnavailable)

    def test_gateway_timeout_error(self) -> None:
        exc = InternalServerError(
            message="Gateway timeout",
            response=_make_response(504),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ProviderUnavailable)

    def test_api_connection_error(self) -> None:
        exc = APIConnectionError(request=MagicMock())
        result = map_anthropic_error(exc)
        assert isinstance(result, ProviderUnavailable)
        assert result.retryable is True

    def test_timeout_error(self) -> None:
        result = map_anthropic_error(TimeoutError("timed out"))
        assert isinstance(result, ProviderTimeout)

    def test_unexpected_error(self) -> None:
        result = map_anthropic_error(ValueError("something weird"))
        assert isinstance(result, ProviderUnavailable)
        assert "Unexpected" in str(result)

    def test_api_status_error_unknown_status(self) -> None:
        exc = APIStatusError(
            message="Unknown status",
            response=_make_response(418),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert isinstance(result, ProviderUnavailable)

    def test_error_includes_provider_name(self) -> None:
        exc = AuthenticationError(
            message="Invalid key",
            response=_make_response(401),
            body=None,
        )
        result = map_anthropic_error(exc)
        assert result.provider_name == "anthropic"


class TestWrapStreamingError:
    """Tests for wrap_streaming_error."""

    def test_wraps_provider_exception(self) -> None:
        original = AuthenticationRequired(message="auth failed")
        result = wrap_streaming_error(original, chunk_index=5)
        assert isinstance(result, StreamingFailure)
        assert result.details.get("chunk_index") == 5
        assert result.details.get("original_error_code") == "AUTHENTICATION_REQUIRED"

    def test_wraps_generic_exception(self) -> None:
        result = wrap_streaming_error(RuntimeError("oops"), chunk_index=3)
        assert isinstance(result, StreamingFailure)
        assert result.details.get("chunk_index") == 3
        assert "oops" in str(result)

    def test_wraps_without_chunk_index(self) -> None:
        result = wrap_streaming_error(RuntimeError("fail"))
        assert isinstance(result, StreamingFailure)
        assert result.retryable is True
