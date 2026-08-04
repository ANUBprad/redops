"""Health contributors for provider runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.kernel.health.health import HealthStatus as HealthStatus


@dataclass(frozen=True, slots=True)
class HealthCheckResult:
    """Immutable health check result.

    Attributes:
        name: Component name.
        status: Health status.
        message: Human-readable message.
        latency_ms: Check latency.
        metadata: Additional metadata.

    """

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AggregateHealth:
    """Aggregated health across all contributors.

    Attributes:
        status: Overall status.
        checks: Individual check results.

    """

    status: HealthStatus
    checks: tuple[HealthCheckResult, ...]


class RuntimeHealthAggregator:
    """Aggregates health from multiple contributors.

    Usage:
        aggregator = RuntimeHealthAggregator()
        aggregator.add_check(result)
        aggregate = aggregator.aggregate()

    """

    def __init__(self) -> None:
        """Initialize aggregator."""
        self._checks: list[HealthCheckResult] = []

    def add_check(self, result: HealthCheckResult) -> None:
        """Add a health check result."""
        self._checks.append(result)

    def aggregate(self) -> AggregateHealth:
        """Aggregate all check results."""
        if not self._checks:
            return AggregateHealth(
                status=HealthStatus.HEALTHY,
                checks=(),
            )

        statuses = [c.status for c in self._checks]

        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return AggregateHealth(
            status=overall,
            checks=tuple(self._checks),
        )

    def reset(self) -> None:
        """Reset all checks."""
        self._checks.clear()
