"""Base provider exception.

All provider-specific errors inherit from this class, which extends
the Kernel's InfrastructureError to maintain a consistent error
hierarchy across the platform.
"""

from __future__ import annotations

from typing import Any

from app.kernel.exceptions.errors import InfrastructureError


class ProviderException(InfrastructureError):
    """Base exception for all provider-related errors.

    Provides structured error context including provider name,
    model identifier, and optional retry guidance.

    Attributes:
        provider_name: The name of the provider that raised the error.
        model_id: The model identifier involved, if applicable.
        error_code: A machine-readable error code string.

    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str | None = None,
        model_id: str | None = None,
        error_code: str = "PROVIDER_ERROR",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        """Initialize the provider exception.

        Args:
            message: Human-readable error description.
            provider_name: Name of the AI provider.
            model_id: Model identifier involved.
            error_code: Machine-readable error code.
            details: Additional context about the error.
            retryable: Whether the operation can be retried.

        """
        super().__init__(
            message,
            error_code=error_code,
            details=details or {},
            retryable=retryable,
        )
        self.provider_name = provider_name
        self.model_id = model_id
