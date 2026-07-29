"""Domain entities for the Evaluation engine."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Self

from app.evaluation.domain.enums.evaluation_enums import (
    CancellationReason,
    FailureReason,
    ItemStatus,
    RunStatus,
)
from app.evaluation.domain.events.evaluation_events import (
    EvaluationCancelled,
    EvaluationCompleted,
    EvaluationFailed,
    EvaluationPaused,
    EvaluationQueued,
    EvaluationResumed,
    EvaluationStarted,
    EvaluationTimedOut,
)
from app.evaluation.domain.state_machine.run_state_machine import (
    InvalidTransitionError,
    RunStateMachine,
    TransitionContext,
    TransitionResult,
)
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
    FailureSummary,
)
from app.kernel.entities.base import AggregateRoot, Entity, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import DomainError

_ITEM_CANCELLED_TERMINAL_STATES: frozenset[ItemStatus] = frozenset(
    {
        ItemStatus.COMPLETED,
        ItemStatus.FAILED,
        ItemStatus.SKIPPED,
        ItemStatus.CANCELLED,
    }
)


@dataclass(frozen=True, slots=True)
class ItemResult:
    """Result of processing a single evaluation item."""

    item_id: UUIDv7
    item_index: int
    prompt: str = ""
    response: str = ""
    parsed_response: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    status: ItemStatus = ItemStatus.PENDING
    error: str | None = None
    failure_reason: FailureReason | None = None
    retry_count: int = 0

    @property
    def total_tokens(self) -> int:
        """Return total tokens consumed."""
        return self.tokens_input + self.tokens_output

    @property
    def is_success(self) -> bool:
        """Return True if the item completed successfully."""
        return self.status == ItemStatus.COMPLETED

    @property
    def has_scores(self) -> bool:
        """Return True if any metric scores were computed."""
        return bool(self.scores)


@dataclass(frozen=True, slots=True)
class AggregatedMetrics:
    """Aggregated metric scores across multiple items."""

    metric_name: str
    scores: tuple[float, ...] = ()
    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    item_count: int = 0
    partial: bool = False

    @classmethod
    def from_scores(cls, metric_name: str, scores: list[float]) -> Self:
        """Create aggregated metrics from a list of scores.

        Args:
            metric_name: Name of the metric.
            scores: List of individual item scores.

        Returns:
            AggregatedMetrics with computed statistics.

        """
        if not scores:
            return cls(metric_name=metric_name, item_count=0)

        return cls(
            metric_name=metric_name,
            scores=tuple(scores),
            mean=statistics.mean(scores),
            median=statistics.median(scores),
            std_dev=statistics.stdev(scores) if len(scores) > 1 else 0.0,
            min_score=min(scores),
            max_score=max(scores),
            item_count=len(scores),
        )


@dataclass(frozen=True, slots=True)
class RunCheckpoint:
    """Serialized evaluation state for resume."""

    run_id: UUIDv7
    checkpoint_number: int
    items_completed: int
    items_total: int
    last_item_index: int
    completed_item_ids: tuple[UUIDv7, ...] = ()
    accumulated_metrics: dict[str, list[float]] = field(default_factory=dict)
    accumulated_tokens_input: int = 0
    accumulated_tokens_output: int = 0
    accumulated_cost_usd: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def completion_ratio(self) -> float:
        """Return completion ratio as a fraction."""
        if self.items_total == 0:
            return 1.0
        return self.items_completed / self.items_total

    @property
    def is_complete(self) -> bool:
        """Return True if all items have been completed."""
        return self.items_completed >= self.items_total


class EvaluationItem(Entity):
    """A single item to be evaluated."""

    def __init__(
        self,
        run_id: UUIDv7,
        index: int,
        data: dict[str, Any] | None = None,
        entity_id: UUIDv7 | None = None,
    ) -> None:
        """Initialize evaluation item.

        Args:
            run_id: ID of the parent run.
            index: Position in the dataset.
            data: Raw dataset row.
            entity_id: Optional ID for reconstruction.

        """
        super().__init__(entity_id=entity_id)
        self.run_id = run_id
        self.index = index
        self.data = data or {}
        self._status = ItemStatus.PENDING
        self._result: ItemResult | None = None

    @property
    def status(self) -> ItemStatus:
        """Return current item status."""
        return self._status

    @property
    def result(self) -> ItemResult | None:
        """Return the item result if completed."""
        return self._result

    def start(self) -> None:
        """Transition item to RUNNING state."""
        if self._status != ItemStatus.PENDING:
            msg = f"Cannot start item in {self._status.value} state"
            raise InvalidItemStateError(msg, current_status=self._status)
        self._status = ItemStatus.RUNNING
        self.touch()

    def complete(self, result: ItemResult) -> None:
        """Mark item as completed with a result.

        Args:
            result: The item execution result.

        """
        if self._status != ItemStatus.RUNNING:
            msg = f"Cannot complete item in {self._status.value} state"
            raise InvalidItemStateError(msg, current_status=self._status)
        self._result = result
        self._status = ItemStatus.COMPLETED
        self.touch()

    def fail(self, error: str, reason: FailureReason | None = None) -> None:
        """Mark item as failed.

        Args:
            error: Error description.
            reason: Categorized failure reason.

        """
        if self._status == ItemStatus.COMPLETED:
            msg = "Cannot fail a completed item"
            raise InvalidItemStateError(msg, current_status=self._status)
        self._result = ItemResult(
            item_id=self.id,
            item_index=self.index,
            status=ItemStatus.FAILED,
            error=error,
            failure_reason=reason,
        )
        self._status = ItemStatus.FAILED
        self.touch()

    def skip(self, reason: str = "") -> None:
        """Skip this item.

        Args:
            reason: Optional skip reason.

        """
        if self._status in _ITEM_CANCELLED_TERMINAL_STATES:
            msg = f"Cannot skip item in {self._status.value} state"
            raise InvalidItemStateError(msg, current_status=self._status)
        self._status = ItemStatus.SKIPPED
        self.touch()

    def cancel(self) -> None:
        """Cancel this item."""
        if self._status in _ITEM_CANCELLED_TERMINAL_STATES:
            msg = f"Cannot cancel item in {self._status.value} state"
            raise InvalidItemStateError(msg, current_status=self._status)
        self._status = ItemStatus.CANCELLED
        self.touch()


class InvalidItemStateError(DomainError):
    """Raised when an item state transition is invalid."""

    def __init__(
        self,
        message: str = "",
        *,
        current_status: ItemStatus,
        trace_id: str | None = None,
    ) -> None:
        """Initialize InvalidItemStateError.

        Args:
            message: Error description.
            current_status: Current item status.
            trace_id: Optional trace ID.

        """
        self.current_status = current_status
        super().__init__(
            message or f"Invalid item state: {current_status.value}",
            error_code="INVALID_ITEM_STATE",
            details={"current_status": current_status.value},
            http_status=409,
            trace_id=trace_id,
        )


class EvaluationRun(AggregateRoot, VersionMixin):
    """An execution instance of an evaluation."""

    def __init__(
        self,
        evaluation_name: str,
        config: EvaluationConfiguration,
        profile: EvaluationProfile,
        metadata: EvaluationMetadata | None = None,
        entity_id: UUIDv7 | None = None,
    ) -> None:
        """Initialize evaluation run.

        Args:
            evaluation_name: Name of the parent evaluation.
            config: Evaluation configuration.
            profile: Resolved execution profile.
            metadata: Optional evaluation metadata.
            entity_id: Optional ID for reconstruction.

        """
        super().__init__(entity_id=entity_id)
        self.evaluation_name = evaluation_name
        self.config = config
        self.profile = profile
        self.metadata = metadata or EvaluationMetadata()
        self._status = RunStatus.CREATED
        self.items_total = 0
        self.items_completed = 0
        self.items_failed = 0
        self.priority = config.priority
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self._checkpoint: RunCheckpoint | None = None
        self._failure_summary: FailureSummary | None = None
        self._state_machine = RunStateMachine()
        self._cancellation_reason: CancellationReason | None = None

    @property
    def status(self) -> RunStatus:
        """Return current run status."""
        return self._status

    @property
    def checkpoint(self) -> RunCheckpoint | None:
        """Return the latest checkpoint."""
        return self._checkpoint

    @property
    def failure_summary(self) -> FailureSummary | None:
        """Return failure summary if run failed."""
        return self._failure_summary

    @property
    def cancellation_reason(self) -> CancellationReason | None:
        """Return cancellation reason if run was cancelled."""
        return self._cancellation_reason

    @property
    def duration_ms(self) -> int:
        """Return duration in milliseconds, or 0 if not started."""
        if self.started_at is None:
            return 0
        end = self.completed_at or datetime.now(UTC)
        delta = end - self.started_at
        return int(delta.total_seconds() * 1000)

    def _transition_to(
        self,
        target: RunStatus,
        ctx: TransitionContext | None = None,
    ) -> TransitionResult:
        """Execute a state transition through the state machine."""
        effective_ctx = ctx or TransitionContext(
            run_id=self.id,
            items_completed=self.items_completed,
            items_total=self.items_total,
            has_checkpoint=self._checkpoint is not None,
        )
        result = self._state_machine.transition(self._status, target, effective_ctx)
        if result.success:
            self._status = result.new_status
            self.touch()
            self.increment_version()
        return result

    def _raise_transition_error(
        self,
        target: RunStatus,
        result: TransitionResult,
    ) -> None:
        """Raise appropriate error for failed transition."""
        if result.error is not None:
            raise result.error
        msg = f"Failed to transition to {target.value}"
        raise InvalidTransitionError(
            message=msg,
            current_status=self._status,
            target_status=target,
        )

    def queue(self) -> None:
        """Transition to QUEUED state."""
        result = self._transition_to(RunStatus.QUEUED)
        if result.success:
            self.raise_event(
                EvaluationQueued(
                    correlation_id=str(self.id),
                    run_id=self.id,
                    evaluation_name=self.evaluation_name,
                    priority=self.priority.value,
                ),
            )

    def start(self, total_items: int) -> None:
        """Transition to RUNNING state.

        Args:
            total_items: Total items in the dataset.

        """
        if total_items < 0:
            msg = "Total items cannot be negative"
            raise ValueError(msg)
        self.items_total = total_items
        result = self._transition_to(RunStatus.STARTING)
        if not result.success:
            self._raise_transition_error(RunStatus.STARTING, result)
        result = self._transition_to(RunStatus.RUNNING)
        if not result.success:
            self._raise_transition_error(RunStatus.RUNNING, result)
        self.started_at = datetime.now(UTC)
        self.raise_event(
            EvaluationStarted(
                correlation_id=str(self.id),
                run_id=self.id,
                provider_name=self.profile.provider_name,
                model_id=self.profile.model_id,
                total_items=total_items,
            ),
        )

    def pause(self) -> None:
        """Pause the evaluation run."""
        result = self._transition_to(RunStatus.PAUSED)
        if not result.success:
            self._raise_transition_error(RunStatus.PAUSED, result)
        self.raise_event(
            EvaluationPaused(
                correlation_id=str(self.id),
                run_id=self.id,
                items_completed=self.items_completed,
                items_total=self.items_total,
            ),
        )

    def resume(self) -> None:
        """Resume a paused evaluation run."""
        result = self._transition_to(
            RunStatus.RUNNING,
            TransitionContext(
                run_id=self.id,
                items_completed=self.items_completed,
                items_total=self.items_total,
                has_checkpoint=self._checkpoint is not None,
            ),
        )
        if not result.success:
            self._raise_transition_error(RunStatus.RUNNING, result)
        self.raise_event(
            EvaluationResumed(
                correlation_id=str(self.id),
                run_id=self.id,
                items_completed=self.items_completed,
                items_total=self.items_total,
            ),
        )

    def complete(self) -> None:
        """Complete the evaluation run successfully."""
        result = self._transition_to(
            RunStatus.COMPLETED,
            TransitionContext(
                run_id=self.id,
                items_completed=self.items_completed,
                items_total=self.items_total,
                has_checkpoint=self._checkpoint is not None,
            ),
        )
        if not result.success:
            self._raise_transition_error(RunStatus.COMPLETED, result)
        self.completed_at = datetime.now(UTC)
        self.raise_event(
            EvaluationCompleted(
                correlation_id=str(self.id),
                run_id=self.id,
                items_completed=self.items_completed,
                items_total=self.items_total,
                duration_ms=self.duration_ms,
            ),
        )

    def fail(
        self,
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        """Fail the evaluation run irrecoverably.

        Args:
            error_code: Machine-readable error code.
            error_message: Human-readable error description.

        """
        result = self._transition_to(RunStatus.FAILED)
        if not result.success:
            self._raise_transition_error(RunStatus.FAILED, result)
        self.completed_at = datetime.now(UTC)
        self._failure_summary = FailureSummary(
            total_items=self.items_total,
            failed_items=self.items_failed,
        )
        self.raise_event(
            EvaluationFailed(
                correlation_id=str(self.id),
                run_id=self.id,
                error_code=error_code,
                error_message=error_message,
                items_completed=self.items_completed,
                items_total=self.items_total,
            ),
        )

    def timeout(self) -> None:
        """Mark the run as timed out."""
        result = self._transition_to(RunStatus.TIMEDOUT)
        if not result.success:
            self._raise_transition_error(RunStatus.TIMEDOUT, result)
        self.completed_at = datetime.now(UTC)
        self.raise_event(
            EvaluationTimedOut(
                correlation_id=str(self.id),
                run_id=self.id,
                timeout_seconds=self.config.budget.max_duration_seconds or 0,
                items_completed=self.items_completed,
                items_total=self.items_total,
            ),
        )

    def cancel(
        self,
        reason: CancellationReason = CancellationReason.USER_CANCELLED,
        *,
        force: bool = False,
    ) -> None:
        """Cancel the evaluation run.

        Args:
            reason: Reason for cancellation.
            force: If True, skip waiting for current item to complete.

        """
        self._cancellation_reason = reason
        target = RunStatus.CANCELLED if force else RunStatus.CANCELLING
        result = self._transition_to(
            target,
            TransitionContext(
                run_id=self.id,
                items_completed=self.items_completed,
                items_total=self.items_total,
                has_checkpoint=self._checkpoint is not None,
                force=force,
            ),
        )
        if not result.success:
            self._raise_transition_error(target, result)
        if force:
            self.completed_at = datetime.now(UTC)
        self.raise_event(
            EvaluationCancelled(
                correlation_id=str(self.id),
                run_id=self.id,
                reason=reason,
                force=force,
                items_completed=self.items_completed,
                items_total=self.items_total,
            ),
        )

    def record_item_success(self) -> None:
        """Record a successful item completion."""
        self.items_completed += 1
        self.touch()

    def record_item_failure(self) -> None:
        """Record an item failure."""
        self.items_failed += 1
        self.items_completed += 1
        self.touch()

    def save_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        """Save a checkpoint for resume.

        Args:
            checkpoint: Checkpoint to save.

        """
        self._checkpoint = checkpoint
        self.touch()

    def can_transition_to(self, target: RunStatus) -> bool:
        """Check if a transition to the target status is valid.

        Args:
            target: Target status to check.

        Returns:
            True if transition is valid.

        """
        return self._state_machine.can_transition(
            self._status,
            target,
            TransitionContext(
                run_id=self.id,
                items_completed=self.items_completed,
                items_total=self.items_total,
                has_checkpoint=self._checkpoint is not None,
            ),
        )
