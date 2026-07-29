"""Latency health tracking.

Tracks latency metrics for provider operations,
enabling performance-based selection and alerting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.providers.health.status import ProviderStatus


@dataclass(frozen=True, slots=True)
class LatencyHealth:
    """Latency-based health metrics for a provider.

    Tracks p50, p95, p99 latencies and uses thresholds
    to determine health status.
    """

    provider_name: str
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    sample_count: int = 0
    threshold_healthy_ms: float = 2000.0
    threshold_degraded_ms: float = 5000.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> ProviderStatus:
        """Determine health status from p95 latency."""
        if self.sample_count == 0:
            return ProviderStatus.UNKNOWN
        if self.p95_ms <= self.threshold_healthy_ms:
            return ProviderStatus.HEALTHY
        if self.p95_ms <= self.threshold_degraded_ms:
            return ProviderStatus.DEGRADED
        return ProviderStatus.UNHEALTHY

    @property
    def is_healthy(self) -> bool:
        """Check if latency indicates healthy status."""
        return self.status == ProviderStatus.HEALTHY
