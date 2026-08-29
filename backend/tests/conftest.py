"""Pytest configuration and shared fixtures for RedOps Eval."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router


@pytest.fixture(autouse=True, scope="session")
def _ensure_secret_key():
    """Guarantee APP_SECRET_KEY is set so JWT signing works in CI.

    CI has no .env file; the config default is empty which makes PyJWT
    reject HMAC signing.  We inject a test-only key and clear the
    cached AppConfig so it picks up the new value.
    """
    os.environ.setdefault("APP_SECRET_KEY", "test-secret-not-for-production")
    os.environ.setdefault("APP_DEBUG", "true")

    from app.core.config import get_config

    get_config.cache_clear()


@pytest.fixture
def app():
    """Create a fresh application instance for testing.

    Builds a lightweight app that skips the full lifespan
    (which requires database/redis/temporal connections).
    Only wires routing so endpoints are testable.
    """
    app = FastAPI(title="redops-eval-test", version="0.1.0", debug=True)
    app.include_router(api_router)
    return app


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client
