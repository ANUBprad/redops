"""OpenAI error mapping — converts SDK exceptions to framework errors."""

from __future__ import annotations

from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

from app.providers.exceptions.auth import AuthenticationRequired
from app.providers.exceptions.availability import ProviderUnavailable
from app.providers.exceptions.base import ProviderException
from app.providers.exceptions.limits import ContextWindowExceeded, TokenLimitExceeded
from app.providers.exceptions.model import InvalidModel
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.exceptions.streaming import StreamingFailure
from app.providers.exceptions.timeout import ProviderTimeout

PROVIDER_NAME = "openai"

_STATUS_UNAUTHORIZED = 401
_STATUS_NOT_FOUND = 404
_STATUS_RATE_LIMITED = 429
_STATUS_BAD_REQUEST = 400

_ERROR_MAP: dict[type, type[ProviderException]] = {
    AuthenticationError: AuthenticationRequired,
    PermissionDeniedError: AuthenticationRequired,
    NotFoundError: InvalidModel,
    RateLimitError: RateLimitExceeded,
    BadRequestError: ProviderUnavailable,
    UnprocessableEntityError: ProviderUnavailable,
    InternalServerError: ProviderUnavailable,
    APIConnectionError: ProviderUnavailable,
}


def map_openai_error(exc: Exception) -> ProviderException:
    """Convert an OpenAI SDK exception to a framework provider error.

    Args:
        exc: The raw OpenAI SDK exception.

    Returns:
        A typed ProviderException suitable for the framework.

    """
    exc_type = type(exc)

    if isinstance(exc, APIStatusError):
        return _map_status_error(exc)

    mapped_type = _ERROR_MAP.get(exc_type)
    if mapped_type is not None:
        return mapped_type(
            message=str(exc),
            provider_name=PROVIDER_NAME,
        )

    if isinstance(exc, TimeoutError):
        return ProviderTimeout(
            message=str(exc),
            provider_name=PROVIDER_NAME,
        )

    return ProviderUnavailable(
        message=f"Unexpected OpenAI error: {exc}",
        provider_name=PROVIDER_NAME,
        details={"original_error_type": exc_type.__name__},
    )


def _map_status_error(exc: APIStatusError) -> ProviderException:
    """Map HTTP status errors to specific framework exceptions."""
    status = exc.status_code

    if status == _STATUS_UNAUTHORIZED:
        return AuthenticationRequired(
            message=str(exc),
            provider_name=PROVIDER_NAME,
        )

    if status == _STATUS_NOT_FOUND:
        return InvalidModel(
            message=str(exc),
            provider_name=PROVIDER_NAME,
        )

    if status == _STATUS_RATE_LIMITED:
        retry_after = _extract_retry_after(exc)
        return RateLimitExceeded(
            message=str(exc),
            provider_name=PROVIDER_NAME,
            retry_after_seconds=retry_after,
        )

    if status == _STATUS_BAD_REQUEST:
        return _map_bad_request(exc)

    if status in (500, 502, 503, 504):
        return ProviderUnavailable(
            message=str(exc),
            provider_name=PROVIDER_NAME,
            details={"status_code": status},
        )

    return ProviderUnavailable(
        message=str(exc),
        provider_name=PROVIDER_NAME,
        details={"status_code": status},
    )


def _map_bad_request(exc: APIStatusError) -> ProviderException:
    """Map 400 Bad Request to specific framework exceptions."""
    message = str(exc).lower()

    if "context_length" in message or "maximum context" in message:
        return ContextWindowExceeded(
            message=str(exc),
            provider_name=PROVIDER_NAME,
        )

    if "max_tokens" in message or "maximum tokens" in message:
        return TokenLimitExceeded(
            message=str(exc),
            provider_name=PROVIDER_NAME,
        )

    if "model" in message and ("not found" in message or "does not exist" in message):
        return InvalidModel(
            message=str(exc),
            provider_name=PROVIDER_NAME,
        )

    return ProviderUnavailable(
        message=str(exc),
        provider_name=PROVIDER_NAME,
        details={"status_code": 400},
    )


def _extract_retry_after(exc: APIStatusError) -> float | None:
    """Extract retry-after header from API status error."""
    headers: dict[str, Any] = getattr(exc.response, "headers", {})
    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after is not None:
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            return None
    return None


def wrap_streaming_error(
    exc: Exception,
    *,
    chunk_index: int | None = None,
) -> StreamingFailure:
    """Wrap a streaming exception into a StreamingFailure.

    Args:
        exc: The raw exception from the stream.
        chunk_index: The chunk index where the error occurred.

    Returns:
        A StreamingFailure framework exception.

    """
    if isinstance(exc, ProviderException):
        return StreamingFailure(
            message=str(exc),
            provider_name=PROVIDER_NAME,
            chunk_index=chunk_index,
            details={"original_error_code": exc.error_code},
        )

    return StreamingFailure(
        message=f"Stream error: {exc}",
        provider_name=PROVIDER_NAME,
        chunk_index=chunk_index,
    )
