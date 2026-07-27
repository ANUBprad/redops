"""Execution Context — immutable context flowing through the runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.kernel.entities.base import UUIDv7


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    """Immutable execution budget for a request."""

    max_cost_usd: float | None = None
    max_tokens: int | None = None
    max_duration_seconds: float | None = None

    @property
    def is_unlimited(self) -> bool:
        """Return True if all budget dimensions are unlimited."""
        return (
            self.max_cost_usd is None
            and self.max_tokens is None
            and self.max_duration_seconds is None
        )


@dataclass(frozen=True, slots=True)
class CancellationToken:
    """Immutable cancellation token for cooperative cancellation."""

    is_cancelled: bool = False
    reason: str = ""

    def cancel(self, reason: str = "") -> CancellationToken:
        """Return a new cancelled token."""
        return CancellationToken(is_cancelled=True, reason=reason)


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable execution context for a single provider invocation.

    Flows through the entire runtime pipeline. Every component
    reads from this context; none mutate it.

    Attributes:
        request_id: Unique identifier for this execution request.
        trace_id: Distributed tracing identifier.
        correlation_id: Links related operations.
        evaluation_id: Evaluation that triggered this execution.
        run_id: Specific evaluation run.
        experiment_id: Experiment identifier.
        provider_name: Name of the provider being invoked.
        model_id: Model identifier within the provider.
        budget: Execution budget constraints.
        deadline: Absolute deadline for this execution.
        cancellation: Cancellation token.
        retry_count: Current retry attempt number.
        max_retries: Maximum retry attempts allowed.
        metadata: Arbitrary execution metadata.

    """

    request_id: UUIDv7 = field(default_factory=UUIDv7)
    trace_id: str = ""
    correlation_id: str = ""
    evaluation_id: str = ""
    run_id: str = ""
    experiment_id: str = ""
    provider_name: str = ""
    model_id: str = ""
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)
    deadline: datetime | None = None
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_cancelled(self) -> bool:
        """Return True if cancellation was requested."""
        return self.cancellation.is_cancelled

    @property
    def is_expired(self) -> bool:
        """Return True if the deadline has passed."""
        if self.deadline is None:
            return False
        return datetime.now(UTC) > self.deadline

    @property
    def remaining_budget(self) -> float | None:
        """Return remaining time budget in seconds, or None if unlimited."""
        if self.budget.max_duration_seconds is None or self.deadline is None:
            return None
        remaining = (self.deadline - datetime.now(UTC)).total_seconds()
        return max(0.0, remaining)

    def with_retry(self, attempt: int) -> ExecutionContext:
        """Return a new context with updated retry count."""
        return ExecutionContext(
            request_id=self.request_id,
            trace_id=self.trace_id,
            correlation_id=self.correlation_id,
            evaluation_id=self.evaluation_id,
            run_id=self.run_id,
            experiment_id=self.experiment_id,
            provider_name=self.provider_name,
            model_id=self.model_id,
            budget=self.budget,
            deadline=self.deadline,
            cancellation=self.cancellation,
            retry_count=attempt,
            max_retries=self.max_retries,
            metadata=self.metadata,
            created_at=self.created_at,
        )

    def cancel(self, reason: str = "") -> ExecutionContext:
        """Return a new cancelled context."""
        return ExecutionContext(
            request_id=self.request_id,
            trace_id=self.trace_id,
            correlation_id=self.correlation_id,
            evaluation_id=self.evaluation_id,
            run_id=self.run_id,
            experiment_id=self.experiment_id,
            provider_name=self.provider_name,
            model_id=self.model_id,
            budget=self.budget,
            deadline=self.deadline,
            cancellation=CancellationToken(is_cancelled=True, reason=reason),
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            metadata=self.metadata,
            created_at=self.created_at,
        )
