"""Provider health data model.

Immutable health status for a provider, integrating with
the Kernel's HealthContributor pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.providers.health.status import ProviderStatus


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Health status of a provider.

    Captures the provider's operational status, latency
    metrics, and capability health details.
    """

    provider_name: str
    status: ProviderStatus = ProviderStatus.UNKNOWN
    message: str = ""
    latency_ms: float | None = None
    last_check: str | None = None
    capability_health: tuple[CapabilityHealth, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if the provider is healthy."""
        return self.status == ProviderStatus.HEALTHY

    @property
    def is_available(self) -> bool:
        """Check if the provider can serve requests."""
        return self.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)


# Avoid circular import; re-export for convenience.
from app.providers.health.capability_health import CapabilityHealth  # noqa: E402
