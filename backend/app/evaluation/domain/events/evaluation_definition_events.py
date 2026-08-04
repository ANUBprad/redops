"""Domain events for the Evaluation definition lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.kernel.entities.base import DomainEvent, UUIDv7


@dataclass(frozen=True, slots=True)
class EvaluationDefinitionCreated(DomainEvent):
    """Raised when an evaluation definition is created."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    evaluation_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.config.created"


@dataclass(frozen=True, slots=True)
class EvaluationDefinitionUpdated(DomainEvent):
    """Raised when an evaluation definition is updated."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    evaluation_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.config.updated"


@dataclass(frozen=True, slots=True)
class EvaluationDefinitionArchived(DomainEvent):
    """Raised when an evaluation definition is archived."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    evaluation_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.config.archived"


@dataclass(frozen=True, slots=True)
class EvaluationDefinitionDeleted(DomainEvent):
    """Raised when an evaluation definition is deleted."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    evaluation_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.config.deleted"


@dataclass(frozen=True, slots=True)
class EvaluationDefinitionDuplicated(DomainEvent):
    """Raised when an evaluation definition is duplicated."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    source_id: UUIDv7 = field(default_factory=UUIDv7)
    new_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.config.duplicated"
