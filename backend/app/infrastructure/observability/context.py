"""Request context middleware for FastAPI.

Extracts or generates correlation IDs and request IDs from incoming
HTTP requests, binds them to context variables, and enriches the
structlog context for structured logging.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from app.infrastructure.observability.correlation import (
    set_correlation_id,
    set_request_id,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request, Response

CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that manages correlation IDs across requests.

    Extracts the correlation ID from the incoming request headers
    or generates a new one. Sets the correlation ID and a request ID
    into context variables for downstream use.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request and set correlation context.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response with correlation headers set.

        """
        correlation_id = request.headers.get(
            CORRELATION_ID_HEADER,
            str(uuid.uuid4()),
        )
        request_id = str(uuid.uuid4())

        set_correlation_id(correlation_id)
        set_request_id(request_id)

        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        response.headers[REQUEST_ID_HEADER] = request_id

        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that captures basic request context for observability.

    Extracts method, path, client host, and user agent from the
    incoming request and stores them for logging enrichment.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Capture request context and pass through.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response.

        """
        structlog = __import__("structlog")
        log = structlog.get_logger("redops_eval.http")
        log.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            client_host=request.client.host if request.client else None,
        )
        response = await call_next(request)
        log.info(
            "request_finished",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        return response
