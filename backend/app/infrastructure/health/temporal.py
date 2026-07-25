"""TemporalHealthContributor implementing the Kernel HealthContributor interface.

Provides health check functionality for Temporal Server via the
managed Temporal client connection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.kernel.health.health import HealthContributor, HealthResult, HealthStatus

if TYPE_CHECKING:
    from app.infrastructure.temporal.client import TemporalClientFactory


class TemporalHealthContributor(HealthContributor):
    """Health contributor for Temporal Server.

    Checks Temporal server reachability via the health service endpoint.
    """

    def __init__(self, temporal_client_factory: TemporalClientFactory) -> None:
        """Initialize with Temporal client factory."""
        self._temporal_client_factory = temporal_client_factory

    @property
    def contributor_name(self) -> str:
        """Return a unique name for this health contributor."""
        return "temporal"

    async def check_health(self) -> HealthResult:
        """Check if Temporal Server is reachable.

        Returns:
            A HealthResult indicating the Temporal health status.

        """
        try:
            healthy = await self._temporal_client_factory.health()
            if healthy:
                return HealthResult(
                    name=self.contributor_name,
                    status=HealthStatus.HEALTHY,
                    detail="temporal is reachable",
                )
            return HealthResult(
                name=self.contributor_name,
                status=HealthStatus.UNHEALTHY,
                detail="temporal health check failed",
            )
        except Exception as exc:  # noqa: BLE001
            return HealthResult(
                name=self.contributor_name,
                status=HealthStatus.UNHEALTHY,
                detail=f"temporal health check failed: {exc}",
            )
