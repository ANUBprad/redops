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
    """Simple in-memory rate limiter using sliding window.

    Supports per-route limits via ``route_limits``, a mapping of path
    prefixes (or the special key ``"*"`` for the default) to
    ``(max_requests, window_seconds)`` tuples. The most specific matching
    prefix wins; otherwise the default limit applies.
    """

    def __init__(
        self,
        app: Any,
        max_requests: int = 100,
        window_seconds: int = 60,
        route_limits: dict[str, tuple[int, int]] | None = None,
    ) -> None:
        super().__init__(app)
        self._default_max = max_requests
        self._default_window = window_seconds
        self._route_limits = route_limits or {}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _resolved_limit(self, path: str) -> tuple[str, int, int]:
        """Resolve the (route_key, max_requests, window_seconds) for a path.

        The route_key namespaces the per-client counter so limits are
        enforced independently per matched route.

        Args:
            path: The request path.

        Returns:
            A tuple of (route_key, max_requests, window_seconds).

        """
        if self._route_limits:
            best: tuple[int, int] | None = None
            best_prefix = ""
            best_len = -1
            for prefix, limit in self._route_limits.items():
                if prefix != "*" and path.startswith(prefix) and len(prefix) > best_len:
                    best = limit
                    best_prefix = prefix
                    best_len = len(prefix)
            if best is not None:
                return (best_prefix, best[0], best[1])
            if "*" in self._route_limits:
                limit = self._route_limits["*"]
                return ("*", limit[0], limit[1])
        return ("_default", self._default_max, self._default_window)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        route_key, max_requests, window_seconds = self._resolved_limit(request.url.path)
        key = f"{client_ip}:{route_key}"
        now = time.time()
        cutoff = now - window_seconds

        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

        if len(self._requests[key]) >= max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={
                    "Retry-After": str(window_seconds),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        self._requests[key].append(now)
        remaining = max_requests - len(self._requests[key])

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
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
