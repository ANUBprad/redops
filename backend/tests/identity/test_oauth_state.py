"""Tests for OAuth state CSRF protection."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import asyncio as aioredis

from app.core.dependencies import CurrentUser, get_current_user, get_db_session, get_redis_client
from app.identity.api.router import identity_router


class FakeRedis:
    """Minimal in-memory Redis fake for testing.

    Methods are sync because TestClient runs the event loop internally
    and we only need to simulate Redis behaviour for unit tests.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:  # noqa: ARG002
        self._store[key] = (value, time.time() + ttl)

    async def get(self, key: str) -> bytes | str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.time() > expires_at:
            del self._store[key]
            return None
        return value

    async def delete(self, key: str) -> int:
        if key in self._store:
            del self._store[key]
            return 1
        return 0


def _build_test_app(fake_redis: FakeRedis) -> FastAPI:
    """Build a minimal FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(identity_router)

    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id="u")
    app.dependency_overrides[get_redis_client] = lambda: fake_redis

    return app


class TestOAuthStateValidation:
    """Tests for OAuth state CSRF protection on callback endpoints."""

    def test_github_callback_rejects_missing_state(self) -> None:
        """Callback without a stored state should return 400."""
        fake_redis = FakeRedis()
        app = _build_test_app(fake_redis)
        client = TestClient(app)

        response = client.post(
            "/auth/oauth/github/callback",
            json={"code": "auth-code-123", "state": "unknown-state"},
        )
        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]

    def test_github_callback_accepts_valid_state(self) -> None:
        """Callback with a valid stored state should pass state validation."""
        fake_redis = FakeRedis()
        fake_redis._store["oauth:state:valid-state-abc"] = ("1", time.time() + 600)

        app = _build_test_app(fake_redis)
        client = TestClient(app)

        with (
            patch(
                "app.identity.services.oauth_service.OAuthService.handle_github_callback",
                new_callable=AsyncMock,
            ) as mock_handle,
            patch(
                "app.identity.api.router._resolve_org_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.identity.api.router.AuthService.create_access_token",
                return_value="fake-jwt",
            ),
        ):
            mock_handle.return_value = (
                SimpleNamespace(id="user-1"),
                "fake-access-token",
                "fake-refresh-token",
            )
            response = client.post(
                "/auth/oauth/github/callback",
                json={"code": "auth-code-123", "state": "valid-state-abc"},
            )

        # State was consumed
        assert "oauth:state:valid-state-abc" not in fake_redis._store
        # Should not be a state-validation error
        assert response.status_code != 400 or "OAuth state" not in response.json().get("detail", "")

    def test_github_callback_rejects_replayed_state(self) -> None:
        """Reusing the same state twice should fail on the second attempt."""
        fake_redis = FakeRedis()
        fake_redis._store["oauth:state:replay-me"] = ("1", time.time() + 600)

        app = _build_test_app(fake_redis)
        client = TestClient(app)

        with (
            patch(
                "app.identity.services.oauth_service.OAuthService.handle_github_callback",
                new_callable=AsyncMock,
            ) as mock_handle,
            patch(
                "app.identity.api.router._resolve_org_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.identity.api.router.AuthService.create_access_token",
                return_value="fake-jwt",
            ),
        ):
            mock_handle.return_value = (
                SimpleNamespace(id="user-1"),
                "fake-access-token",
                "fake-refresh-token",
            )
            # First callback consumes the state
            client.post(
                "/auth/oauth/github/callback",
                json={"code": "code-1", "state": "replay-me"},
            )

        # State should now be deleted
        assert "oauth:state:replay-me" not in fake_redis._store

        # Second callback with same state should fail
        response = client.post(
            "/auth/oauth/github/callback",
            json={"code": "code-2", "state": "replay-me"},
        )
        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]

    def test_google_callback_rejects_missing_state(self) -> None:
        """Google callback without stored state should return 400."""
        fake_redis = FakeRedis()
        app = _build_test_app(fake_redis)
        client = TestClient(app)

        response = client.post(
            "/auth/oauth/google/callback",
            json={"code": "auth-code-456", "state": "unknown-google-state"},
        )
        assert response.status_code == 400
        assert "Invalid or expired OAuth state" in response.json()["detail"]

    def test_github_callback_rejects_missing_state_field(self) -> None:
        """Callback without state field should return 422 (validation error)."""
        app = _build_test_app(FakeRedis())
        client = TestClient(app)

        response = client.post(
            "/auth/oauth/github/callback",
            json={"code": "auth-code-789"},
        )
        assert response.status_code == 422

    def test_state_deleted_after_use(self) -> None:
        """State should be removed from Redis after successful consumption."""
        fake_redis = FakeRedis()
        fake_redis._store["oauth:state:consume-me"] = ("1", time.time() + 600)

        assert "oauth:state:consume-me" in fake_redis._store

        app = _build_test_app(fake_redis)
        client = TestClient(app)

        with (
            patch(
                "app.identity.services.oauth_service.OAuthService.handle_github_callback",
                new_callable=AsyncMock,
            ) as mock_handle,
            patch(
                "app.identity.api.router._resolve_org_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.identity.api.router.AuthService.create_access_token",
                return_value="fake-jwt",
            ),
        ):
            mock_handle.return_value = (
                SimpleNamespace(id="user-1"),
                "fake-access-token",
                "fake-refresh-token",
            )
            client.post(
                "/auth/oauth/github/callback",
                json={"code": "code-1", "state": "consume-me"},
            )

        assert "oauth:state:consume-me" not in fake_redis._store
