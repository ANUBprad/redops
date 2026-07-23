"""Tests for health check endpoints."""

from fastapi.testclient import TestClient


class TestHealthCheck:
    """Suite of tests for the health endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """The health endpoint should return a 200 status code."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_service_name(self, client: TestClient) -> None:
        """The health response should contain the service name."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["service"] == "redops-eval"

    def test_health_returns_version(self, client: TestClient) -> None:
        """The health response should contain a version string."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_status_is_healthy(self, client: TestClient) -> None:
        """The health status should be 'healthy'."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "healthy"
