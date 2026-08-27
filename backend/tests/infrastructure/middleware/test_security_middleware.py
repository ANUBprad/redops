"""Tests for the HTTP security middleware (rate limiting, headers)."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.infrastructure.middleware.security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


def _plain_response(request: object) -> JSONResponse:
    return JSONResponse({"ok": True})


def _build_app(middleware_class: type, **kwargs: object) -> Starlette:
    """Build a minimal Starlette app wrapped in the given middleware."""
    routes = [
        Route("/{path:path}", _plain_response),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(middleware_class, **kwargs)
    return app


class TestRateLimitMiddleware:
    def test_default_limit_applies(self) -> None:
        """Should enforce the default max_requests."""
        app = _build_app(RateLimitMiddleware, max_requests=3, window_seconds=60)
        client = TestClient(app)
        for _ in range(3):
            response = client.get("/api/v1/anything")
            assert response.status_code == 200
        blocked = client.get("/api/v1/anything")
        assert blocked.status_code == 429
        assert blocked.headers["X-RateLimit-Limit"] == "3"

    def test_per_route_limit_overrides_default(self) -> None:
        """More specific route prefixes should override the default."""
        app = _build_app(
            RateLimitMiddleware,
            max_requests=100,
            window_seconds=60,
            route_limits={"/api/v1/auth/": (2, 60)},
        )
        client = TestClient(app)

        for _ in range(2):
            response = client.get("/api/v1/auth/login")
            assert response.status_code == 200
            assert response.headers["X-RateLimit-Limit"] == "2"
        blocked = client.get("/api/v1/auth/login")
        assert blocked.status_code == 429

        # Non-matching routes use the default.
        other = client.get("/api/v1/evaluations")
        assert other.status_code == 200
        assert other.headers["X-RateLimit-Limit"] == "100"

    def test_default_rule_star(self) -> None:
        """A '*' route limit should act as the fallback default."""
        app = _build_app(
            RateLimitMiddleware,
            max_requests=100,
            window_seconds=60,
            route_limits={"/api/v1/sensitive/": (1, 60), "*": (50, 60)},
        )
        client = TestClient(app)

        blocked_sensitive = client.get("/api/v1/sensitive/do")
        assert blocked_sensitive.status_code == 200
        blocked_sensitive = client.get("/api/v1/sensitive/do")
        assert blocked_sensitive.status_code == 429

        # Fallback uses the '*' rule (50), not the constructor default (100).
        for _ in range(50):
            assert client.get("/api/v1/other").status_code == 200
        assert client.get("/api/v1/other").status_code == 429

    def test_most_specific_prefix_wins(self) -> None:
        """When multiple prefixes match, the longest should win."""
        app = _build_app(
            RateLimitMiddleware,
            max_requests=100,
            window_seconds=60,
            route_limits={
                "/api/v1/": (100, 60),
                "/api/v1/auth/": (5, 60),
            },
        )
        client = TestClient(app)

        for _ in range(5):
            assert client.get("/api/v1/auth/login").status_code == 200
        assert client.get("/api/v1/auth/login").status_code == 429


class TestSecurityHeadersMiddleware:
    def test_security_headers_present(self) -> None:
        """Should add security headers to responses."""
        app = _build_app(SecurityHeadersMiddleware)
        client = TestClient(app)
        response = client.get("/whatever")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers

    def test_no_hsts_on_docs(self) -> None:
        """HSTS should be skipped on docs/redoc endpoints."""
        app = _build_app(SecurityHeadersMiddleware)
        client = TestClient(app)
        response = client.get("/docs")
        assert "Strict-Transport-Security" not in response.headers
