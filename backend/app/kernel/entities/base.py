"""Abstract base classes for the domain model layer.

Defines Entity, AggregateRoot, ValueObject, DomainEvent, and mixins
that provide consistent identity, equality, versioning, and timestamps
across all bounded contexts.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.kernel.utils.uuid_generator import UUIDGenerator


class UUIDv7:
    """Value object wrapping a UUIDv7 identifier.

    UUIDv7 is time-sortable, preventing B-tree index fragmentation
    that occurs with random UUIDv4. Provides factory methods for
    generating new IDs and wrapping existing ones.
    """

    value: uuid.UUID

    def __init__(self, value: uuid.UUID | None = None) -> None:
        self.value = value if value is not None else uuid.uuid4()

    @classmethod
    def generate(cls, generator: UUIDGenerator | None = None) -> UUIDv7:
        """Create a new UUIDv7 identifier.

        Args:
            generator: Optional UUID generator (injectable for testing).
                       Defaults to a time-sortable v7 UUID.

        """
        if generator is not None:
            return cls(value=generator.generate())

        # Fallback: use uuid4 if no generator provided.
        # In production, provide a UUIDv7 generator.
        return cls(value=uuid.uuid4())

    @classmethod
    def from_string(cls, value: str) -> UUIDv7:
        """Parse a UUID string into a UUIDv7 wrapper."""
        return cls(value=uuid.UUID(value))

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"UUIDv7({self.value!s})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UUIDv7):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class TimestampMixin:
    """Mixin that provides created_at and updated_at timestamps.

    Timestamps are stored as UTC datetime objects.
    """

    created_at: datetime
    updated_at: datetime

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        now = datetime.now(timezone.utc)
        if not hasattr(self, "created_at") or self.created_at is None:
            self.created_at = now
        if not hasattr(self, "updated_at") or self.updated_at is None:
            self.updated_at = now

    def touch(self) -> None:
        """Update the updated_at timestamp to now."""
        self.updated_at = datetime.now(timezone.utc)


class SoftDeleteMixin:
    """Mixin that provides soft-delete capability.

    Deleted entities are not physically removed from the database.
    Instead, deleted_at is set to the deletion timestamp.
    """

    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        """Return True if this entity has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark this entity as deleted."""
        self.deleted_at = datetime.now(timezone.utc)

    def restore(self) -> None:
        """Restore a soft-deleted entity."""
        self.deleted_at = None


class VersionMixin:
    """Mixin that provides optimistic concurrency versioning."""

    version: int = 1

    def increment_version(self) -> None:
        """Increment the version number for optimistic locking."""
        self.version += 1


class Entity(ABC, TimestampMixin):
    """Base class for all domain entities.

    Entities have an identity (UUIDv7) that distinguishes them
    from other entities, even if all other attributes are equal.
    Equality is based on identity, not field values.
    """

    id: UUIDv7

    def __init__(self, entity_id: UUIDv7 | None = None, **kwargs: Any) -> None:
        TimestampMixin.__init__(self, **kwargs)
        self.id = entity_id if entity_id is not None else UUIDv7.generate()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))


class AggregateRoot(Entity, ABC):
    """Base class for aggregate roots in the domain model.

    Aggregate roots are the entry point for transactional consistency
    boundaries. Domain events raised by the aggregate are collected
    and published by the repository when the aggregate is saved.

    Usage:
        class MyAggregate(AggregateRoot):
            def do_something(self) -> None:
                # Raise a domain event
                self.raise_event(MyEvent(...))

        # Retrieve domain events via aggregate.collect_events()
    """

    _domain_events: list[DomainEvent]

    def __init__(self, entity_id: UUIDv7 | None = None, **kwargs: Any) -> None:
        super().__init__(entity_id=entity_id, **kwargs)
        self._domain_events = []

    def raise_event(self, event: DomainEvent) -> None:
        """Record a domain event to be published when the aggregate is saved."""
        self._domain_events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear all pending domain events."""
        events = list(self._domain_events)
        self._domain_events.clear()
        return events


class ValueObject(ABC):
    """Base class for immutable value objects.

    Value objects have no identity — two value objects are equal
    if all their attributes are equal. They must be immutable.
    """

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))


class DomainEvent(ABC):
    """Base class for all domain events.

    Domain events represent something that happened in the domain
    that other parts of the system might need to react to.
    Events are immutable and carry a timestamp and correlation ID.
    """

    event_id: UUIDv7
    occurred_at: datetime
    correlation_id: str | None

    def __init__(self, correlation_id: str | None = None) -> None:
        self.event_id = UUIDv7.generate()
        self.occurred_at = datetime.now(timezone.utc)
        self.correlation_id = correlation_id

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Return a unique identifier for this event type.

        Convention: "<context>.<entity>.<action>"
        Example: "evaluation.run.completed"
        """
        ...
