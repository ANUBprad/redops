"""Fallback chain — provider selection on failure."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


@unique
class FallbackStrategy(Enum):
    """Fallback selection strategy."""

    ROUND_ROBIN = "round_robin"
    COST_OPTIMIZED = "cost_optimized"
    LATENCY_OPTIMIZED = "latency_optimized"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class FallbackEntry:
    """Immutable entry in a fallback chain.

    Attributes:
        provider_name: Provider identifier.
        model_id: Model to use.
        priority: Lower is preferred.
        max_retries: Max retries before moving to next entry.

    """

    provider_name: str
    model_id: str
    priority: int = 0
    max_retries: int = 1


@dataclass(frozen=True, slots=True)
class FallbackDecision:
    """Immutable result of a fallback decision.

    Attributes:
        provider_name: Selected provider.
        model_id: Selected model.
        index: Position in fallback chain.
        is_final: Whether this is the last fallback option.
        attempt_count: How many attempts made on this entry.

    """

    provider_name: str
    model_id: str
    index: int
    is_final: bool
    attempt_count: int


@dataclass
class FallbackState:
    """Mutable fallback chain state."""

    current_index: int = 0
    attempt_counts: dict[int, int] = field(default_factory=dict)

    def reset(self) -> None:
        """Reset chain state."""
        self.current_index = 0
        self.attempt_counts.clear()


class FallbackChain:
    """Manages fallback selection across providers.

    Usage:
        chain = FallbackChain(entries, strategy)
        decision = chain.next()
        # Execute with decision.provider_name
        chain.record_success()
        # Or on failure:
        decision = chain.next()

    """

    def __init__(
        self,
        entries: list[FallbackEntry],
        strategy: FallbackStrategy = FallbackStrategy.ROUND_ROBIN,
        custom_selector: Callable[[list[FallbackEntry], int], int] | None = None,
    ) -> None:
        """Initialize fallback chain."""
        if not entries:
            msg = "Fallback chain requires at least one entry"
            raise ValueError(msg)

        self._entries = sorted(entries, key=lambda e: e.priority)
        self._strategy = strategy
        self._custom_selector = custom_selector
        self._state = FallbackState()

    @property
    def is_exhausted(self) -> bool:
        """Return True if all fallback options exhausted."""
        return self._state.current_index >= len(self._entries)

    def next(self) -> FallbackDecision | None:
        """Get next fallback entry.

        Returns:
            FallbackDecision or None if chain exhausted.

        """
        if self.is_exhausted:
            return None

        index = self._select_next()
        if index >= len(self._entries):
            return None

        entry = self._entries[index]
        attempt = self._state.attempt_counts.get(index, 0)

        return FallbackDecision(
            provider_name=entry.provider_name,
            model_id=entry.model_id,
            index=index,
            is_final=index == len(self._entries) - 1,
            attempt_count=attempt,
        )

    def record_success(self) -> None:
        """Record successful execution (resets chain)."""
        self._state.reset()

    def record_failure(self) -> None:
        """Record failed execution (advance chain)."""
        current = self._state.current_index
        self._state.attempt_counts[current] = self._state.attempt_counts.get(current, 0) + 1

        entry = self._entries[current]
        if self._state.attempt_counts[current] >= entry.max_retries:
            self._state.current_index = current + 1

    def reset(self) -> None:
        """Reset chain to beginning."""
        self._state.reset()

    def _select_next(self) -> int:
        """Select next index based on strategy."""
        if self._strategy == FallbackStrategy.ROUND_ROBIN:
            return self._state.current_index

        if self._strategy == FallbackStrategy.CUSTOM and self._custom_selector:
            return self._custom_selector(self._entries, self._state.current_index)

        return self._state.current_index
