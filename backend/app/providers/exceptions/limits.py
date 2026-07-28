"""Token and context limit exceptions."""

from __future__ import annotations

from typing import Any

from app.providers.exceptions.base import ProviderException


class ContextWindowExceeded(ProviderException):
    """Raised when input exceeds the model's context window.

    The total token count (input + output) exceeds the maximum
    allowed by the model's context window size.

    """

    def __init__(
        self,
        message: str = "Context window exceeded",
        *,
        provider_name: str | None = None,
        model_id: str | None = None,
        context_window: int | None = None,
        token_count: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the provider.
            model_id: The model identifier.
            context_window: Maximum context window size.
            token_count: Actual token count that exceeded the limit.
            details: Additional context.

        """
        merged_details = dict(details or {})
        if context_window is not None:
            merged_details["context_window"] = context_window
        if token_count is not None:
            merged_details["token_count"] = token_count
        super().__init__(
            message,
            provider_name=provider_name,
            model_id=model_id,
            error_code="CONTEXT_WINDOW_EXCEEDED",
            details=merged_details,
            retryable=False,
        )


class TokenLimitExceeded(ProviderException):
    """Raised when output tokens would exceed the model's limit.

    This occurs when the maximum output tokens parameter
    exceeds what the model supports, or when generation
    would be truncated.

    """

    def __init__(
        self,
        message: str = "Token limit exceeded",
        *,
        provider_name: str | None = None,
        model_id: str | None = None,
        max_tokens: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the provider.
            model_id: The model identifier.
            max_tokens: The token limit that was exceeded.
            details: Additional context.

        """
        merged_details = dict(details or {})
        if max_tokens is not None:
            merged_details["max_tokens"] = max_tokens
        super().__init__(
            message,
            provider_name=provider_name,
            model_id=model_id,
            error_code="TOKEN_LIMIT_EXCEEDED",
            details=merged_details,
            retryable=False,
        )
