"""Health framework for aggregating service health checks.

The HealthRegistry collects HealthContributor instances from
all registered services and plugins, then provides a unified
health report for the /ready endpoint.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.schemas.health import HealthStatus as HealthStatus

__all__ = ["HealthStatus"]


@dataclass
class HealthResult:
    """Result of a single health check."""

    name: str
    status: HealthStatus
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Return True if the component is healthy."""
        return self.status is HealthStatus.HEALTHY


@dataclass
class HealthReport:
    """Aggregated health report for the entire platform."""

    status: HealthStatus
    checks: list[HealthResult] = field(default_factory=list)

    @property
    def all_healthy(self) -> bool:
        """Return True if every check passed."""
        return all(c.is_healthy for c in self.checks)


class HealthContributor(ABC):
    """Interface for components that can report their health.

    Implemented by services, plugins, and infrastructure adapters.
    """

    @abstractmethod
    async def check_health(self) -> HealthResult:
        """Perform a health check and return the result.

        Returns:
            A HealthResult describing the component's health.
        """
        ...

    @property
    @abstractmethod
    def contributor_name(self) -> str:
        """Return a unique name for this health contributor."""
        ...


class HealthRegistry:
    """Registry for collecting and aggregating health checks.

    All LifecycleService implementations and Plugin instances
    should register a HealthContributor here at startup.
    """

    def __init__(self) -> None:
        self._contributors: dict[str, HealthContributor] = {}

    def register(self, contributor: HealthContributor) -> None:
        """Register a health contributor.

        Args:
            contributor: The contributor to register.

        """
        self._contributors[contributor.contributor_name] = contributor

    def unregister(self, name: str) -> None:
        """Remove a contributor by name."""
        self._contributors.pop(name, None)

    async def check_all(self) -> HealthReport:
        """Run health checks for all registered contributors.

        Returns:
            An aggregated HealthReport.
        """
        results: list[HealthResult] = []

        for name, contributor in self._contributors.items():
            try:
                result = await contributor.check_health()
                results.append(result)
            except Exception as exc:
                results.append(
                    HealthResult(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        detail=f"Health check raised exception: {exc}",
                    )
                )

        all_healthy = all(r.is_healthy for r in results)
        overall = HealthStatus.HEALTHY if all_healthy else HealthStatus.DEGRADED

        return HealthReport(status=overall, checks=results)

    @property
    def contributor_count(self) -> int:
        """Return the number of registered contributors."""
        return len(self._contributors)
