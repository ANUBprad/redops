"""Tests for the HTTP security middleware (rate limiting, headers)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

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


def _build_app_with_redis(redis_client: Any, **middleware_kwargs: Any) -> Starlette:
    """Build a Starlette app with a mocked Redis client on app.state."""
    routes = [
        Route("/{path:path}", _plain_response),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(RateLimitMiddleware, **middleware_kwargs)
    app.state.redis_client = redis_client
    return app


class FakeRedisZSet:
    """Minimal fake Redis supporting ZSET operations used by RateLimitMiddleware."""

    def __init__(self) -> None:
        self._store: dict[str, list[tuple[str, float]]] = {}

    def pipeline(self) -> FakeRedisPipeline:
        return FakeRedisPipeline(self)


class FakeRedisPipeline:
    """Fake pipeline that executes commands sequentially."""

    def __init__(self, parent: FakeRedisZSet) -> None:
        self._parent = parent
        self._ops: list[tuple[str, tuple[Any, ...]]] = []

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> FakeRedisPipeline:
        self._ops.append(("zremrangebyscore", (key, min_score, max_score)))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> FakeRedisPipeline:
        self._ops.append(("zadd", (key, mapping)))
        return self

    def zcard(self, key: str) -> FakeRedisPipeline:
        self._ops.append(("zcard", (key,)))
        return self

    def expire(self, key: str, ttl: int) -> FakeRedisPipeline:
        self._ops.append(("expire", (key, ttl)))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op, args in self._ops:
            if op == "zremrangebyscore":
                key, min_s, max_s = args
                entries = self._parent._store.get(key, [])
                self._parent._store[key] = [(m, s) for m, s in entries if not (min_s <= s <= max_s)]
                results.append(0)
            elif op == "zadd":
                key, mapping = args
                if key not in self._parent._store:
                    self._parent._store[key] = []
                for member, score in mapping.items():
                    self._parent._store[key].append((member, score))
                results.append(len(mapping))
            elif op == "zcard":
                key = args[0]
                results.append(len(self._parent._store.get(key, [])))
            elif op == "expire":
                results.append(True)
        self._ops.clear()
        return results


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


class TestRedisRateLimit:
    """Tests for the Redis-backed sliding window rate limiter."""

    def test_redis_enforces_limit(self) -> None:
        """Redis ZSET-based limiter should block after max_requests."""
        fake_redis = FakeRedisZSet()
        app = _build_app_with_redis(fake_redis, max_requests=3, window_seconds=60)
        client = TestClient(app)

        for _ in range(3):
            resp = client.get("/api/v1/test")
            assert resp.status_code == 200
            assert resp.headers["X-RateLimit-Limit"] == "3"

        blocked = client.get("/api/v1/test")
        assert blocked.status_code == 429
        assert blocked.headers["X-RateLimit-Remaining"] == "0"

    def test_redis_route_limits_applied(self) -> None:
        """Per-route limits should be enforced via Redis."""
        fake_redis = FakeRedisZSet()
        app = _build_app_with_redis(
            fake_redis,
            max_requests=100,
            window_seconds=60,
            route_limits={"/api/v1/auth/": (2, 60)},
        )
        client = TestClient(app)

        for _ in range(2):
            assert client.get("/api/v1/auth/login").status_code == 200

        blocked = client.get("/api/v1/auth/login")
        assert blocked.status_code == 429

        # Other routes use default
        assert client.get("/api/v1/other").status_code == 200

    def test_fallback_on_redis_error(self) -> None:
        """Should fall back to in-memory limiter if Redis raises."""
        failing_redis = MagicMock()
        failing_redis.pipeline.return_value.execute = AsyncMock(
            side_effect=ConnectionError("Redis down"),
        )

        app = _build_app_with_redis(failing_redis, max_requests=3, window_seconds=60)
        client = TestClient(app)

        # Should still enforce limits via in-memory fallback
        for _ in range(3):
            resp = client.get("/api/v1/test")
            assert resp.status_code == 200

        blocked = client.get("/api/v1/test")
        assert blocked.status_code == 429

    def test_fallback_when_no_redis(self) -> None:
        """Should use in-memory limiter when no redis_client on app.state."""
        app = _build_app(RateLimitMiddleware, max_requests=2, window_seconds=60)
        # No redis_client set on app.state
        client = TestClient(app)

        for _ in range(2):
            assert client.get("/test").status_code == 200
        assert client.get("/test").status_code == 429


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
