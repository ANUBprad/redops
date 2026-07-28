"""RedisHealthContributor implementing the Kernel HealthContributor interface.

Provides health check functionality for Redis via the async Redis client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.kernel.health.health import HealthContributor, HealthResult, HealthStatus

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis


class RedisHealthContributor(HealthContributor):
    """Health contributor for Redis.

    Checks Redis reachability by issuing a PING command.
    """

    def __init__(self, redis_client: AsyncRedis) -> None:
        """Initialize with Redis client."""
        self._redis_client = redis_client

    @property
    def contributor_name(self) -> str:
        """Return a unique name for this health contributor."""
        return "redis"

    async def check_health(self) -> HealthResult:
        """Check if Redis is reachable.

        Returns:
            A HealthResult indicating the Redis health status.

        """
        try:
            pong = await self._redis_client.ping()
            if pong:
                return HealthResult(
                    name=self.contributor_name,
                    status=HealthStatus.HEALTHY,
                    detail="redis is reachable",
                )
            return HealthResult(
                name=self.contributor_name,
                status=HealthStatus.UNHEALTHY,
                detail="redis ping returned false",
            )
        except Exception as exc:
            return HealthResult(
                name=self.contributor_name,
                status=HealthStatus.UNHEALTHY,
                detail=f"redis health check failed: {exc}",
            )
