"""Domain events for the Evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.evaluation.domain.enums.evaluation_enums import CancellationReason, FailureReason
from app.kernel.entities.base import DomainEvent, UUIDv7


@dataclass(frozen=True, slots=True)
class EvaluationCreated(DomainEvent):
    """Raised when an evaluation is created."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    evaluation_name: str = ""
    eval_type: str = ""
    provider_name: str = ""
    model_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.created"


@dataclass(frozen=True, slots=True)
class EvaluationQueued(DomainEvent):
    """Raised when a run enters the QUEUED state."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    evaluation_name: str = ""
    priority: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.queued"


@dataclass(frozen=True, slots=True)
class EvaluationStarted(DomainEvent):
    """Raised when a run begins execution."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    provider_name: str = ""
    model_id: str = ""
    total_items: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.started"


@dataclass(frozen=True, slots=True)
class EvaluationPaused(DomainEvent):
    """Raised when a run is paused."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.paused"


@dataclass(frozen=True, slots=True)
class EvaluationResumed(DomainEvent):
    """Raised when a paused run is resumed."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.resumed"


@dataclass(frozen=True, slots=True)
class EvaluationCompleted(DomainEvent):
    """Raised when a run finishes successfully."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    items_completed: int = 0
    items_total: int = 0
    duration_ms: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.completed"


@dataclass(frozen=True, slots=True)
class EvaluationCancelled(DomainEvent):
    """Raised when a run is cancelled."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    reason: CancellationReason = CancellationReason.USER_CANCELLED
    force: bool = False
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.cancelled"


@dataclass(frozen=True, slots=True)
class EvaluationFailed(DomainEvent):
    """Raised when a run fails irrecoverably."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    error_code: str = ""
    error_message: str = ""
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.failed"


@dataclass(frozen=True, slots=True)
class EvaluationTimedOut(DomainEvent):
    """Raised when a run exceeds its maximum duration."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    timeout_seconds: int = 0
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.timed_out"


@dataclass(frozen=True, slots=True)
class ItemStarted(DomainEvent):
    """Raised when an item begins processing."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    item_index: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.item.started"


@dataclass(frozen=True, slots=True)
class ItemCompleted(DomainEvent):
    """Raised when an item finishes successfully."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    item_index: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.item.completed"


@dataclass(frozen=True, slots=True)
class ItemFailed(DomainEvent):
    """Raised when an item fails."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    item_index: int = 0
    error_code: str = ""
    error_message: str = ""
    failure_reason: FailureReason = FailureReason.INTERNAL_ERROR
    retry_count: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.item.failed"


@dataclass(frozen=True, slots=True)
class ItemRetried(DomainEvent):
    """Raised when an item is retried after failure."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    retry_count: int = 0
    previous_error: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.item.retried"


@dataclass(frozen=True, slots=True)
class ItemCancelled(DomainEvent):
    """Raised when an item is abandoned due to cancellation."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    item_index: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.item.cancelled"


@dataclass(frozen=True, slots=True)
class ItemSkipped(DomainEvent):
    """Raised when an item is skipped."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    reason: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.item.skipped"


@dataclass(frozen=True, slots=True)
class MetricComputed(DomainEvent):
    """Raised when a metric is computed for an item."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    metric_name: str = ""
    score: float = 0.0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.metric.computed"


@dataclass(frozen=True, slots=True)
class MetricFailed(DomainEvent):
    """Raised when a metric computation fails."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    item_id: UUIDv7 = field(default_factory=UUIDv7)
    metric_name: str = ""
    error_message: str = ""

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.metric.failed"


@dataclass(frozen=True, slots=True)
class MetricAggregated(DomainEvent):
    """Raised when metric scores are aggregated across items."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    metric_name: str = ""
    aggregated_score: float = 0.0
    item_count: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.metric.aggregated"


@dataclass(frozen=True, slots=True)
class CheckpointCreated(DomainEvent):
    """Raised when a checkpoint is persisted."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    checkpoint_number: int = 0
    items_completed: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.checkpoint.created"


@dataclass(frozen=True, slots=True)
class CheckpointLoaded(DomainEvent):
    """Raised when a checkpoint is loaded for resume."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    checkpoint_number: int = 0
    items_completed: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "evaluation.checkpoint.loaded"
