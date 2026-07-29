"""Health check endpoints for liveness and readiness probes.

Uses the Kernel HealthRegistry from the composition root for
consistent health reporting across all infrastructure components.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.config import AppConfig, get_config
from app.kernel.health.health import HealthRegistry, HealthResult
from app.schemas.health import (
    DependencyCheck,
    HealthCheckResponse,
    HealthStatus,
    ReadinessCheckResponse,
)

health_router = APIRouter(tags=["health"])


def _get_health_registry(request: Request) -> HealthRegistry | None:
    """Extract the HealthRegistry from the application bootstrap.

    Args:
        request: The current request.

    Returns:
        The HealthRegistry instance or None if not available.

    """
    bootstrap = getattr(request.app.state, "bootstrap", None)
    if bootstrap is not None:
        return getattr(bootstrap, "health_registry", None)
    return None


def _to_dependency_check(result: HealthResult) -> DependencyCheck:
    """Convert a Kernel HealthResult to a Pydantic DependencyCheck.

    Args:
        result: The Kernel health result.

    Returns:
        A Pydantic DependencyCheck model.

    """
    return DependencyCheck(
        name=result.name,
        healthy=result.is_healthy,
        detail=result.detail,
    )


@health_router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    config: AppConfig = Depends(get_config),
) -> HealthCheckResponse:
    """Liveness probe.

    Returns 200 when the application is running and can serve requests.
    Does NOT check dependencies — that is the readiness probe's job.
    """
    return HealthCheckResponse(
        status=HealthStatus.HEALTHY,
        version=config.app_version,
        service=config.app_name,
    )


@health_router.get("/ready", response_model=ReadinessCheckResponse)
async def readiness_check(
    request: Request,
    config: AppConfig = Depends(get_config),
) -> ReadinessCheckResponse:
    """Readiness probe.

    Returns 200 only when all core dependencies are reachable.
    Returns 200 with status=degraded when some dependencies are down.
    """
    checks: list[DependencyCheck] = []

    health_registry = _get_health_registry(request)
    if health_registry is not None:
        report = await health_registry.check_all()
        checks = [_to_dependency_check(r) for r in report.checks]
    else:
        checks = [
            DependencyCheck(name="bootstrap", healthy=False, detail="not initialized"),
        ]

    all_healthy = all(c.healthy for c in checks)

    return ReadinessCheckResponse(
        status=HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED,
        version=config.app_version,
        service=config.app_name,
        checks=checks,
    )
