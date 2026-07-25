"""Correlation ID management for distributed tracing across services.

Correlation IDs are propagated across service boundaries through
event payloads, HTTP headers, and log contexts. This module provides
context variable management for request-scoped correlation IDs.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

CORRELATION_ID_CTX: ContextVar[str] = ContextVar("correlation_id", default="")
REQUEST_ID_CTX: ContextVar[str] = ContextVar("request_id", default="")


def get_correlation_id() -> str:
    """Return the current correlation ID.

    Returns:
        The correlation ID string, or an empty string if not set.

    """
    return CORRELATION_ID_CTX.get()


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Set and return a correlation ID for the current context.

    If no ID is provided, a new UUID is generated.

    Args:
        correlation_id: Optional explicit correlation ID.

    Returns:
        The correlation ID that was set.

    """
    cid = correlation_id or str(uuid.uuid4())
    CORRELATION_ID_CTX.set(cid)
    return cid


def get_request_id() -> str:
    """Return the current request ID.

    Returns:
        The request ID string, or an empty string if not set.

    """
    return REQUEST_ID_CTX.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set and return a request ID for the current context.

    If no ID is provided, a new UUID is generated.

    Args:
        request_id: Optional explicit request ID.

    Returns:
        The request ID that was set.

    """
    rid = request_id or str(uuid.uuid4())
    REQUEST_ID_CTX.set(rid)
    return rid


def reset_context() -> None:
    """Reset all context variables to their defaults."""
    CORRELATION_ID_CTX.set("")
    REQUEST_ID_CTX.set("")
