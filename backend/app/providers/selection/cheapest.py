"""Cheapest model selection strategy.

Selects the model with the lowest input price per 1K tokens.
Ties are broken by output price, then context window.
"""

from __future__ import annotations

from app.providers.catalog.model import ModelMetadata
from app.providers.selection.strategy import SelectionStrategy


class CheapestStrategy(SelectionStrategy):
    """Select the most cost-effective model.

    Prioritizes input cost, then output cost, then
    larger context window as a tiebreaker.
    """

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select the cheapest model.

        Args:
            candidates: Available models.

        Returns:
            The cheapest model, or None if empty.

        """
        eligible = self.filter_candidates(candidates)
        if not eligible:
            return None
        return min(
            eligible,
            key=lambda m: (m.input_price_per_1k, m.output_price_per_1k, -m.context_window),
        )

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        return "cheapest"
