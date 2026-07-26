"""Model validation exceptions."""

from __future__ import annotations

from typing import Any

from app.providers.exceptions.base import ProviderException


class InvalidModel(ProviderException):
    """Raised when a model identifier is invalid or unrecognized.

    This may indicate a typo in the model name, a request for
    a model that does not exist, or a model that has been
    removed from the provider's catalog.

    """

    def __init__(
        self,
        message: str = "Invalid or unrecognized model",
        *,
        provider_name: str | None = None,
        model_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the provider.
            model_id: The invalid model identifier.
            details: Additional context.

        """
        super().__init__(
            message,
            provider_name=provider_name,
            model_id=model_id,
            error_code="INVALID_MODEL",
            details=details,
            retryable=False,
        )
