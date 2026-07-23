"""Health check endpoints for liveness and readiness probes."""

from fastapi import APIRouter, Depends, Request
from redis import asyncio as aioredis
from temporalio.client import Client as TemporalClient

from app.core.config import AppConfig
from app.core.dependencies import get_config
from app.db.health import check_database_health
from app.schemas.health import (
    DependencyCheck,
    HealthCheckResponse,
    HealthStatus,
    ReadinessCheckResponse,
)

health_router = APIRouter(tags=["health"])


async def _check_redis_health(request: Request) -> DependencyCheck:
    """Check if Redis is reachable."""
    redis_client: aioredis.Redis | None = request.app.state.redis_client
    if redis_client is None:
        return DependencyCheck(name="redis", healthy=False, detail="unreachable (failed at startup)")

    try:
        pong = await redis_client.ping()
        return DependencyCheck(
            name="redis",
            healthy=pong,
            detail="connected" if pong else "ping failed",
        )
    except Exception as exc:
        return DependencyCheck(
            name="redis",
            healthy=False,
            detail=str(exc),
        )


async def _check_temporal_health(request: Request) -> DependencyCheck:
    """Check if Temporal Server is reachable."""
    temporal_client: TemporalClient | None = request.app.state.temporal_client
    if temporal_client is None:
        return DependencyCheck(
            name="temporal", healthy=False, detail="unreachable (failed at startup)"
        )

    try:
        await temporal_client.health_service.check()
        return DependencyCheck(name="temporal", healthy=True, detail="connected")
    except Exception as exc:
        return DependencyCheck(
            name="temporal",
            healthy=False,
            detail=str(exc),
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

    # Database check
    db_healthy = await check_database_health()
    checks.append(
        DependencyCheck(
            name="database",
            healthy=db_healthy,
            detail="connected" if db_healthy else "unreachable",
        )
    )

    # Redis check
    checks.append(await _check_redis_health(request))

    # Temporal check
    checks.append(await _check_temporal_health(request))

    all_healthy = all(c.healthy for c in checks)

    return ReadinessCheckResponse(
        status=HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED,
        version=config.app_version,
        service=config.app_name,
        checks=checks,
    )
