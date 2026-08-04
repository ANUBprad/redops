"""Domain enums for the Evaluation engine.

Re-exports shared enums from ai.core for backward compatibility.
Evaluation-specific enums (ItemStatus, EvaluationStatus, EvaluationType)
remain defined here.
"""

from __future__ import annotations

from enum import Enum, unique

from app.ai.core.enums import CancellationReason as CancellationReason
from app.ai.core.enums import FailureReason as FailureReason
from app.ai.core.enums import Priority as Priority
from app.ai.core.enums import RunStatus as RunStatus

__all__ = [
    "CancellationReason",
    "EvaluationStatus",
    "EvaluationType",
    "FailureReason",
    "ItemStatus",
    "Priority",
    "RunStatus",
]


@unique
class ItemStatus(Enum):
    """Status of a single evaluation item."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self in _ITEM_TERMINAL_STATES


_ITEM_TERMINAL_STATES: frozenset[ItemStatus] = frozenset(
    {
        ItemStatus.COMPLETED,
        ItemStatus.FAILED,
        ItemStatus.SKIPPED,
        ItemStatus.CANCELLED,
    }
)


@unique
class EvaluationStatus(Enum):
    """Lifecycle status of an evaluation definition."""

    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"

    @property
    def is_editable(self) -> bool:
        """Return True if the evaluation can be modified."""
        return self == EvaluationStatus.DRAFT

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self == EvaluationStatus.ARCHIVED


@unique
class EvaluationType(Enum):
    """Type of evaluation determining execution behavior."""

    SINGLE = "single"
    DATASET = "dataset"
    REGRESSION = "regression"
    SAFETY = "safety"
    RAG = "rag"
    COMPARISON = "comparison"
