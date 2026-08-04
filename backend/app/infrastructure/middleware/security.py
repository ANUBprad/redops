"""Security middleware: rate limiting, security headers, request ID propagation."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter using sliding window."""

    def __init__(
        self,
        app: Any,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - self._window_seconds

        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]

        if len(self._requests[client_ip]) >= self._max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={
                    "Retry-After": str(self._window_seconds),
                    "X-RateLimit-Limit": str(self._max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        self._requests[client_ip].append(now)
        remaining = self._max_requests - len(self._requests[client_ip])

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        if not request.url.path.startswith("/docs") and not request.url.path.startswith(
            "/redoc",
        ):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Propagate request ID through the request lifecycle."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
