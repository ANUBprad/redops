"""Selection strategy base.

Defines the abstract interface for model selection strategies.
Each strategy encapsulates a different policy for choosing
among available models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.catalog.model import ModelMetadata


class SelectionStrategy(ABC):
    """Abstract model selection strategy.

    Strategies implement different policies for selecting
    a model from a list of candidates. The Evaluation Engine
    configures a strategy to match its selection criteria.
    """

    @abstractmethod
    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select the best model from candidates.

        Args:
            candidates: Available models to choose from.

        Returns:
            The selected model, or None if no candidates exist.

        """

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Return the human-readable strategy name."""

    def filter_candidates(
        self,
        candidates: list[ModelMetadata],
        *,
        active_only: bool = True,
    ) -> list[ModelMetadata]:
        """Filter candidates to active models.

        Args:
            candidates: The raw candidate list.
            active_only: If True, exclude deprecated/retired models.

        Returns:
            Filtered list of eligible candidates.

        """
        if active_only:
            return [m for m in candidates if m.is_active]
        return list(candidates)
