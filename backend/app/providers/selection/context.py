"""Highest context window selection strategy.

Selects the model with the largest context window.
Ties are broken by cost.
"""

from __future__ import annotations

from app.providers.catalog.model import ModelMetadata  # noqa: TC001
from app.providers.selection.strategy import SelectionStrategy


class HighestContextStrategy(SelectionStrategy):
    """Select the model with the largest context window.

    Prioritizes context window size, then lower cost
    as a tiebreaker.
    """

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select the model with the highest context window.

        Args:
            candidates: Available models.

        Returns:
            The model with the largest context, or None if empty.

        """
        eligible = self.filter_candidates(candidates)
        if not eligible:
            return None
        return max(
            eligible,
            key=lambda m: (m.context_window, -m.input_price_per_1k),
        )

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        return "highest_context"
