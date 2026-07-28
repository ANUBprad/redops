"""Fastest model selection strategy.

Selects the model with the lowest latency tier.
Ties are broken by cost, then context window.
"""

from __future__ import annotations

from app.providers.catalog.model import ModelMetadata
from app.providers.selection.strategy import SelectionStrategy

_LATENCY_RANK: dict[str, int] = {
    "realtime": 0,
    "fast": 1,
    "standard": 2,
    "slow": 3,
}


class FastestStrategy(SelectionStrategy):
    """Select the lowest-latency model.

    Uses the model's latency_tier to rank, falling back
    to cost and context window as tiebreakers.
    """

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select the fastest model.

        Args:
            candidates: Available models.

        Returns:
            The fastest model, or None if empty.

        """
        eligible = self.filter_candidates(candidates)
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda m: (
                _LATENCY_RANK.get(m.latency_tier, 99),
                m.input_price_per_1k,
                -m.context_window,
            ),
        )

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        return "fastest"
