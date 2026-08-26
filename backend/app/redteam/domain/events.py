"""Domain events for the Red Team & Safety domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.kernel.entities.base import DomainEvent, UUIDv7


@dataclass(frozen=True, slots=True)
class AttackDefinitionCreated(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    definition_id: UUIDv7 = field(default_factory=UUIDv7)
    name: str = ""
    category: str = ""
    severity: str = ""

    @property
    def event_type(self) -> str:
        return "safety.attack_definition.created"


@dataclass(frozen=True, slots=True)
class AttackDefinitionUpdated(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    definition_id: UUIDv7 = field(default_factory=UUIDv7)
    name: str = ""

    @property
    def event_type(self) -> str:
        return "safety.attack_definition.updated"


@dataclass(frozen=True, slots=True)
class AttackDefinitionActivated(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    definition_id: UUIDv7 = field(default_factory=UUIDv7)
    name: str = ""

    @property
    def event_type(self) -> str:
        return "safety.attack_definition.activated"


@dataclass(frozen=True, slots=True)
class AttackDefinitionArchived(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    definition_id: UUIDv7 = field(default_factory=UUIDv7)
    name: str = ""

    @property
    def event_type(self) -> str:
        return "safety.attack_definition.archived"


@dataclass(frozen=True, slots=True)
class AttackRunCreated(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    evaluation_run_id: UUIDv7 | None = None
    attack_count: int = 0

    @property
    def event_type(self) -> str:
        return "safety.attack_run.created"


@dataclass(frozen=True, slots=True)
class AttackRunQueued(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)

    @property
    def event_type(self) -> str:
        return "safety.attack_run.queued"


@dataclass(frozen=True, slots=True)
class AttackRunStarted(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    items_total: int = 0

    @property
    def event_type(self) -> str:
        return "safety.attack_run.started"


@dataclass(frozen=True, slots=True)
class AttackRunCompleted(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    items_total: int = 0
    items_completed: int = 0
    items_passed: int = 0
    items_violated: int = 0

    @property
    def event_type(self) -> str:
        return "safety.attack_run.completed"


@dataclass(frozen=True, slots=True)
class AttackRunFailed(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    error_message: str = ""

    @property
    def event_type(self) -> str:
        return "safety.attack_run.failed"


@dataclass(frozen=True, slots=True)
class AttackRunCancelled(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    items_completed: int = 0

    @property
    def event_type(self) -> str:
        return "safety.attack_run.cancelled"


@dataclass(frozen=True, slots=True)
class FindingDetected(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    finding_id: UUIDv7 = field(default_factory=UUIDv7)
    campaign_id: str = ""
    attack_category: str = ""
    severity: str = ""
    verdict: str = ""

    @property
    def event_type(self) -> str:
        return "safety.finding.detected"


@dataclass(frozen=True, slots=True)
class CampaignCompleted(DomainEvent):
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    campaign_id: str = ""
    state: str = ""
    total_rounds: int = 0
    violation_count: int = 0
    cost_summary: dict[str, object] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return "safety.campaign.completed"
