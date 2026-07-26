"""Fallback chain selection strategy.

Tries strategies in order, returning the first successful
selection. Provides resilience when preferred models are
unavailable.
"""

from __future__ import annotations

from app.providers.catalog.model import ModelMetadata  # noqa: TC001
from app.providers.selection.strategy import SelectionStrategy


class FallbackChainStrategy(SelectionStrategy):
    """Try multiple strategies in order.

    Each strategy is attempted in sequence. The first
    strategy to return a non-None result wins.
    """

    def __init__(self, strategies: list[SelectionStrategy]) -> None:
        """Initialize with an ordered list of strategies.

        Args:
            strategies: Strategies to try in order.

        """
        if not strategies:
            msg = "At least one strategy is required"
            raise ValueError(msg)
        self._strategies = list(strategies)

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select using the first successful strategy.

        Args:
            candidates: Available models.

        Returns:
            The selected model, or None if all strategies fail.

        """
        for strategy in self._strategies:
            result = strategy.select(candidates)
            if result is not None:
                return result
        return None

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        names = " -> ".join(s.strategy_name for s in self._strategies)
        return f"fallback_chain({names})"
