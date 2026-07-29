"""DatabaseHealthContributor implementing the Kernel HealthContributor interface.

Provides health check functionality for the PostgreSQL database
via the managed DatabaseEngine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.kernel.health.health import HealthContributor, HealthResult, HealthStatus

if TYPE_CHECKING:
    from app.infrastructure.database.engine import DatabaseEngine


class DatabaseHealthContributor(HealthContributor):
    """Health contributor for the PostgreSQL database.

    Checks database reachability by executing a lightweight query
    against the connection pool.
    """

    def __init__(self, database_engine: DatabaseEngine) -> None:
        """Initialize with database engine."""
        self._database_engine = database_engine

    @property
    def contributor_name(self) -> str:
        """Return a unique name for this health contributor."""
        return "database"

    async def check_health(self) -> HealthResult:
        """Check if the database is reachable.

        Returns:
            A HealthResult indicating the database health status.

        """
        try:
            healthy = await self._database_engine.health()
            if healthy:
                return HealthResult(
                    name=self.contributor_name,
                    status=HealthStatus.HEALTHY,
                    detail="database is reachable",
                )
            return HealthResult(
                name=self.contributor_name,
                status=HealthStatus.UNHEALTHY,
                detail="database ping failed",
            )
        except Exception as exc:
            return HealthResult(
                name=self.contributor_name,
                status=HealthStatus.UNHEALTHY,
                detail=f"database health check failed: {exc}",
            )
