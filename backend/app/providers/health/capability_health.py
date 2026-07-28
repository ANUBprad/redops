"""Capability health tracking.

Tracks the health of individual provider capabilities,
allowing the framework to degrade gracefully when specific
features are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.providers.capabilities.capability import Capability  # noqa: TC001
from app.providers.health.status import ProviderStatus


@dataclass(frozen=True, slots=True)
class CapabilityHealth:
    """Health status of a specific capability.

    Tracks whether a particular capability (e.g., streaming,
    vision) is operational within a provider.
    """

    capability: Capability
    status: ProviderStatus = ProviderStatus.UNKNOWN
    message: str = ""
    latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_operational(self) -> bool:
        """Check if this capability is operational."""
        return self.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
