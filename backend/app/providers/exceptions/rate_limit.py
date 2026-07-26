"""Rate limiting exceptions."""

from __future__ import annotations

from typing import Any

from app.providers.exceptions.base import ProviderException


class RateLimitExceeded(ProviderException):
    """Raised when provider rate limits are exceeded.

    Includes retry-after guidance when the provider supplies it.

    Attributes:
        retry_after_seconds: Seconds to wait before retrying, if known.

    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        provider_name: str | None = None,
        retry_after_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the rate-limited provider.
            retry_after_seconds: Seconds to wait before retrying.
            details: Additional context.

        """
        merged_details = dict(details or {})
        if retry_after_seconds is not None:
            merged_details["retry_after_seconds"] = retry_after_seconds
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="RATE_LIMIT_EXCEEDED",
            details=merged_details,
            retryable=True,
        )
        self.retry_after_seconds = retry_after_seconds
