"""Capability matching selection strategy.

Selects models that match required capabilities,
then applies a secondary ranking strategy.
"""

from __future__ import annotations

from app.providers.capabilities.capability_set import CapabilitySet
from app.providers.catalog.model import ModelMetadata
from app.providers.selection.strategy import SelectionStrategy


class CapabilityMatchingStrategy(SelectionStrategy):
    """Select models matching required capabilities.

    Filters candidates to those supporting all required
    capabilities, then selects the cheapest matching model.
    """

    def __init__(self, required: CapabilitySet) -> None:
        """Initialize with required capabilities.

        Args:
            required: The capabilities that must be supported.

        """
        self._required = required

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select the cheapest model matching capabilities.

        Args:
            candidates: Available models.

        Returns:
            The best matching model, or None if no match.

        """
        eligible = self.filter_candidates(candidates)
        matching = [m for m in eligible if m.capabilities.supports_all(self._required)]
        if not matching:
            return None
        return min(
            matching,
            key=lambda m: (m.input_price_per_1k, -m.context_window),
        )

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        return "capability_matching"
