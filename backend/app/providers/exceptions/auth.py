"""Authentication exceptions."""

from __future__ import annotations

from typing import Any

from app.providers.exceptions.base import ProviderException


class AuthenticationRequired(ProviderException):
    """Raised when provider authentication fails or is missing.

    This indicates that API keys, tokens, or other credentials
    are invalid, expired, or not provided.

    """

    def __init__(
        self,
        message: str = "Authentication required or credentials invalid",
        *,
        provider_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the provider requiring auth.
            details: Additional context.

        """
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="AUTHENTICATION_REQUIRED",
            details=details,
            retryable=False,
        )
