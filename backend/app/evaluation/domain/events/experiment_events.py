"""Domain events for the Experiment aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.kernel.entities.base import DomainEvent, UUIDv7


@dataclass(frozen=True, slots=True)
class ExperimentCreated(DomainEvent):
    """Raised when an experiment is created."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    experiment_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "experiment.created"


@dataclass(frozen=True, slots=True)
class ExperimentUpdated(DomainEvent):
    """Raised when an experiment is updated."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    experiment_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "experiment.updated"


@dataclass(frozen=True, slots=True)
class ExperimentCompleted(DomainEvent):
    """Raised when an experiment is completed."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    experiment_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "experiment.completed"


@dataclass(frozen=True, slots=True)
class ExperimentArchived(DomainEvent):
    """Raised when an experiment is archived."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    experiment_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "experiment.archived"


@dataclass(frozen=True, slots=True)
class ExperimentBaselineSet(DomainEvent):
    """Raised when an experiment's baseline run is set."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    experiment_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    baseline_run_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "experiment.baseline_set"
