"""Pydantic schemas for health check responses."""

from enum import Enum

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Possible health check statuses."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResponse(BaseModel):
    """Response model for the liveness probe."""

    status: HealthStatus = Field(..., description="Current application health status")
    version: str = Field(..., description="Application version")
    service: str = Field(..., description="Service name")


class DependencyCheck(BaseModel):
    """Result of a single dependency health check."""

    name: str = Field(..., description="Dependency name")
    healthy: bool = Field(..., description="Whether the dependency is reachable")
    detail: str = Field(default="", description="Additional detail about the check")


class ReadinessCheckResponse(HealthCheckResponse):
    """Response model for the readiness probe with dependency details."""

    checks: list[DependencyCheck] = Field(
        default_factory=list,
        description="Results of individual dependency checks",
    )
