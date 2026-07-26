"""Round robin selection strategy.

Distributes requests evenly across candidates in order.
"""

from __future__ import annotations

from app.providers.catalog.model import ModelMetadata  # noqa: TC001
from app.providers.selection.strategy import SelectionStrategy


class RoundRobinStrategy(SelectionStrategy):
    """Distribute selection evenly across candidates.

    Maintains an internal counter and cycles through
    candidates in order. Thread-safe via simple counter.
    """

    def __init__(self) -> None:
        """Initialize the round robin counter."""
        self._counter: int = 0

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select the next model in rotation.

        Args:
            candidates: Available models.

        Returns:
            The next model in rotation, or None if empty.

        """
        eligible = self.filter_candidates(candidates)
        if not eligible:
            return None
        index = self._counter % len(eligible)
        self._counter += 1
        return eligible[index]

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        return "round_robin"
