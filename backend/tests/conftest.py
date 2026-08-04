"""Pytest configuration and shared fixtures for RedOps Eval."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import api_router


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
