"""R-11: readiness probe must fail closed while degraded.

Proven defect: GET /ready always returned HTTP 200, even with
status=degraded in the body, so the kubelet readinessProbe
(kubernetes/base/api-deployment.yaml, helm values) kept routing
traffic to pods with down dependencies.

Contract locked here:
* all dependencies healthy -> HTTP 200, status healthy;
* any dependency down (or bootstrap missing) -> HTTP 503 with the
  same body shape (status degraded + per-dependency checks);
* liveness (/health) is untouched and stays HTTP 200.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.health import health_router
from app.kernel.health.health import HealthRegistry, HealthResult
from app.schemas.health import HealthStatus


class _Healthy:
    contributor_name = "db"

    async def check_health(self) -> HealthResult:
        return HealthResult(name="db", status=HealthStatus.HEALTHY)


class _Sick:
    contributor_name = "db"

    async def check_health(self) -> HealthResult:
        return HealthResult(name="db", status=HealthStatus.UNHEALTHY, detail="down")


class _Exploding:
    contributor_name = "redis"

    async def check_health(self) -> HealthResult:
        raise RuntimeError("connection refused")


class _Bootstrap:
    def __init__(self, *contributors) -> None:
        self.health_registry = HealthRegistry()
        for contributor in contributors:
            self.health_registry.register(contributor)


def _client(*contributors, with_bootstrap: bool = True) -> TestClient:
    app = FastAPI()
    if with_bootstrap:
        app.state.bootstrap = _Bootstrap(*contributors)
    app.include_router(health_router)
    return TestClient(app)


class TestReadinessProbe:
    """Readiness HTTP status must reflect dependency health."""

    def test_healthy_returns_200(self) -> None:
        response = _client(_Healthy()).get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["checks"] == [{"name": "db", "healthy": True, "detail": ""}]

    def test_degraded_returns_503_with_checks(self) -> None:
        response = _client(_Sick()).get("/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["checks"] == [{"name": "db", "healthy": False, "detail": "down"}]

    def test_contributor_exception_returns_503(self) -> None:
        response = _client(_Healthy(), _Exploding()).get("/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"

    def test_missing_bootstrap_returns_503(self) -> None:
        response = _client(with_bootstrap=False).get("/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"

    def test_liveness_still_returns_200(self) -> None:
        response = _client(_Sick()).get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
