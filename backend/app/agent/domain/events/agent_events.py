"""Domain events for the Agent Registry lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.kernel.entities.base import DomainEvent, UUIDv7


@dataclass(frozen=True, slots=True)
class AgentDefinitionCreated(DomainEvent):
    """Raised when an agent definition is created."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    agent_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "agent.definition.created"


@dataclass(frozen=True, slots=True)
class AgentDefinitionUpdated(DomainEvent):
    """Raised when an agent definition is updated."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    agent_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""
    name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "agent.definition.updated"


@dataclass(frozen=True, slots=True)
class AgentDefinitionActivated(DomainEvent):
    """Raised when an agent definition is activated."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    agent_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "agent.definition.activated"


@dataclass(frozen=True, slots=True)
class AgentDefinitionDeactivated(DomainEvent):
    """Raised when an agent definition is deactivated."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    agent_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "agent.definition.deactivated"


@dataclass(frozen=True, slots=True)
class AgentDefinitionArchived(DomainEvent):
    """Raised when an agent definition is archived."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    agent_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "agent.definition.archived"


@dataclass(frozen=True, slots=True)
class AgentDefinitionDeleted(DomainEvent):
    """Raised when an agent definition is deleted."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    agent_id: UUIDv7 = field(default_factory=UUIDv7)
    project_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "agent.definition.deleted"
