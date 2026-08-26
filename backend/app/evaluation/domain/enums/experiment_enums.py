"""Domain enums for the Experiment aggregate."""

from __future__ import annotations

from enum import Enum, unique


@unique
class ExperimentStatus(Enum):
    """Lifecycle status of an experiment."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

    @property
    def is_editable(self) -> bool:
        """Return True if the experiment can be modified."""
        return self in (ExperimentStatus.DRAFT, ExperimentStatus.ACTIVE)

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self == ExperimentStatus.ARCHIVED
