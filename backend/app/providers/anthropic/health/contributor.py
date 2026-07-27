"""Anthropic health contributor."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.providers.health.provider_health import ProviderHealth
from app.providers.health.status import ProviderStatus

if TYPE_CHECKING:
    from app.providers.anthropic.client.anthropic_client import AnthropicClient


class AnthropicHealthContributor:
    """Health contributor for the Anthropic provider.

    Performs lightweight health checks against the Anthropic API.

    Usage:
        contributor = AnthropicHealthContributor(client)
        health = await contributor.check()

    """

    PROVIDER_NAME = "anthropic"

    def __init__(self, client: AnthropicClient) -> None:
        """Initialize health contributor."""
        self._client = client
        self._last_check_time: datetime | None = None
        self._last_check_result: ProviderStatus = ProviderStatus.UNKNOWN
        self._last_latency_ms: float | None = None

    async def check(self) -> ProviderHealth:
        """Perform a health check against the Anthropic API.

        Returns:
            ProviderHealth with current status and latency.

        """
        start = time.monotonic()
        is_healthy = await self._client.check_health()
        elapsed_ms = (time.monotonic() - start) * 1000

        self._last_check_time = datetime.now(UTC)
        self._last_latency_ms = elapsed_ms

        if is_healthy:
            self._last_check_result = ProviderStatus.HEALTHY
        else:
            self._last_check_result = ProviderStatus.UNHEALTHY

        return ProviderHealth(
            provider_name=self.PROVIDER_NAME,
            status=self._last_check_result,
            message="Anthropic API reachable" if is_healthy else "Anthropic API unreachable",
            latency_ms=elapsed_ms,
            last_check=self._last_check_time.isoformat() if self._last_check_time else None,
        )

    @property
    def last_status(self) -> ProviderStatus:
        """Return the last known status."""
        return self._last_check_result

    @property
    def last_latency_ms(self) -> float | None:
        """Return the last check latency in milliseconds."""
        return self._last_latency_ms
