"""Domain events for the Evaluation Profile aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.kernel.entities.base import DomainEvent, UUIDv7


@dataclass(frozen=True, slots=True)
class ProfileCreated(DomainEvent):
    """Raised when a profile is created."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    profile_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "profile.created"


@dataclass(frozen=True, slots=True)
class ProfileUpdated(DomainEvent):
    """Raised when a profile is updated."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    profile_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "profile.updated"


@dataclass(frozen=True, slots=True)
class ProfileDeleted(DomainEvent):
    """Raised when a profile is deleted."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    profile_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "profile.deleted"
