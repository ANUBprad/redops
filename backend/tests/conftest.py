"""Pytest configuration and shared fixtures for RedOps Eval."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app():
    """Create a fresh application instance for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client
