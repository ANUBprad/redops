"""Health-based selection strategy.

Selects models from healthy providers, degrading to
all candidates if no healthy providers exist.
"""

from __future__ import annotations

from app.providers.catalog.model import ModelMetadata  # noqa: TC001
from app.providers.health.provider_health import ProviderHealth  # noqa: TC001
from app.providers.health.status import ProviderStatus
from app.providers.selection.strategy import SelectionStrategy


class HealthBasedStrategy(SelectionStrategy):
    """Select models from healthy providers.

    Filters candidates to healthy providers first.
    Falls back to all candidates if none are healthy.
    """

    def __init__(self, health_reports: dict[str, ProviderHealth] | None = None) -> None:
        """Initialize with health reports.

        Args:
            health_reports: Mapping of provider name to health.

        """
        self._health_reports: dict[str, ProviderHealth] = health_reports or {}

    def update_health(self, provider_name: str, health: ProviderHealth) -> None:
        """Update a provider's health report.

        Args:
            provider_name: The provider name.
            health: The health status.

        """
        self._health_reports[provider_name] = health

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select from healthy providers, fallback to all.

        Args:
            candidates: Available models.

        Returns:
            A model from a healthy provider, or any model.

        """
        eligible = self.filter_candidates(candidates)
        if not eligible:
            return None

        healthy = [
            m for m in eligible
            if self._is_healthy(m.provider_name)
        ]
        pool = healthy or eligible
        return min(
            pool,
            key=lambda m: (m.input_price_per_1k, -m.context_window),
        )

    def _is_healthy(self, provider_name: str) -> bool:
        """Check if a provider is healthy."""
        health = self._health_reports.get(provider_name)
        if health is None:
            return True  # Unknown providers treated as healthy
        return health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        return "health_based"
