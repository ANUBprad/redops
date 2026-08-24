"""Enums for the adaptive campaign domain."""

from __future__ import annotations

from enum import Enum, unique


@unique
class CampaignState(Enum):
    """Lifecycle states for an adaptive campaign."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"

    @property
    def is_terminal(self) -> bool:
        return self.value in ("completed", "failed", "budget_exhausted")

    @property
    def is_active(self) -> bool:
        return self.value in ("running", "paused")


@unique
class MutationPhase(Enum):
    """Phases of mutation strategy selection."""

    EXPLORATION = "exploration"
    EXPLOITATION = "exploitation"
    ADAPTIVE = "adaptive"
