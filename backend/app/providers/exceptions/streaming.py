"""Streaming exceptions."""

from __future__ import annotations

from typing import Any

from app.providers.exceptions.base import ProviderException


class StreamingFailure(ProviderException):
    """Raised when a streaming response fails mid-stream.

    This may occur due to network interruption, provider
    timeout, or malformed stream data.

    """

    def __init__(
        self,
        message: str = "Streaming response failed",
        *,
        provider_name: str | None = None,
        model_id: str | None = None,
        chunk_index: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error description.
            provider_name: Name of the provider.
            model_id: The model identifier.
            chunk_index: The stream chunk index where failure occurred.
            details: Additional context.

        """
        merged_details = dict(details or {})
        if chunk_index is not None:
            merged_details["chunk_index"] = chunk_index
        super().__init__(
            message,
            provider_name=provider_name,
            model_id=model_id,
            error_code="STREAMING_FAILURE",
            details=merged_details,
            retryable=True,
        )
