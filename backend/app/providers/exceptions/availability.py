"""Provider availability exceptions."""

from __future__ import annotations

from typing import Any

from app.providers.exceptions.base import ProviderException


class ProviderUnavailable(ProviderException):
    """Raised when a provider is unreachable or degraded.

    The provider may be experiencing an outage, maintenance,
    or network connectivity issues.

    Attributes:
        retryable: Defaults to True (providers may recover).

    """

    def __init__(
        self,
        message: str = "Provider is unavailable",
        *,
        provider_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the unavailable provider.
            details: Additional context.

        """
        super().__init__(
            message,
            provider_name=provider_name,
            error_code="PROVIDER_UNAVAILABLE",
            details=details,
            retryable=True,
        )
