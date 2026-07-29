"""Provider timeout exceptions."""

from __future__ import annotations

from typing import Any

from app.providers.exceptions.base import ProviderException


class ProviderTimeout(ProviderException):
    """Raised when a provider request times out.

    Wraps the Kernel's TimeoutError with provider-specific context.

    """

    def __init__(
        self,
        message: str = "Provider request timed out",
        *,
        provider_name: str | None = None,
        model_id: str | None = None,
        timeout_seconds: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the provider.
            model_id: The model identifier.
            timeout_seconds: The timeout duration that was exceeded.
            details: Additional context.

        """
        merged_details = dict(details or {})
        if timeout_seconds is not None:
            merged_details["timeout_seconds"] = timeout_seconds
        super().__init__(
            message,
            provider_name=provider_name,
            model_id=model_id,
            error_code="PROVIDER_TIMEOUT",
            details=merged_details,
            retryable=True,
        )
        self.timeout_seconds = timeout_seconds
