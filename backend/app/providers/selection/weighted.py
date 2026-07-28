"""Weighted random selection strategy.

Selects models based on assigned weights, favoring
higher-weighted candidates.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.providers.catalog.model import ModelMetadata  # noqa: TC001
from app.providers.selection.strategy import SelectionStrategy


@dataclass
class WeightedStrategy(SelectionStrategy):
    """Weighted random model selection.

    Assigns weights to models and selects proportionally.
    Higher weights increase selection probability.
    """

    _weights: dict[str, float] = field(default_factory=dict, init=False)
    _default_weight: float = 1.0
    _rng: random.Random = field(default_factory=random.Random, init=False)

    def __init__(self, seed: int | None = None) -> None:
        """Initialize with optional seed for reproducibility.

        Args:
            seed: Random seed for deterministic selection.

        """
        self._weights = {}
        self._default_weight = 1.0
        self._rng = random.Random(seed)

    def set_weight(self, model_id: str, weight: float) -> None:
        """Set the weight for a specific model.

        Args:
            model_id: The model identifier.
            weight: The selection weight (must be >= 0).

        """
        if weight < 0:
            msg = "Weight must be non-negative"
            raise ValueError(msg)
        self._weights[model_id] = weight

    def select(self, candidates: list[ModelMetadata]) -> ModelMetadata | None:
        """Select a model using weighted random selection.

        Args:
            candidates: Available models.

        Returns:
            A randomly selected model, or None if empty.

        """
        eligible = self.filter_candidates(candidates)
        if not eligible:
            return None
        weights = [
            self._weights.get(m.model_id, self._default_weight)
            for m in eligible
        ]
        total = sum(weights)
        if total == 0:
            return eligible[0]
        return self._rng.choices(eligible, weights=weights, k=1)[0]

    @property
    def strategy_name(self) -> str:
        """Return the strategy name."""
        return "weighted"
