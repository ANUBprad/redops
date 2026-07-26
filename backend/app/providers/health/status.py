"""Provider status enum."""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class ProviderStatus(StrEnum):
    """Operational status of a provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"
