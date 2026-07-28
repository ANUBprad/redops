"""Pure domain services for the Evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.evaluation.domain.state_machine.run_state_machine import RunStateMachine, TransitionContext
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    ExecutionBudget,
    ExecutionPolicy,
    FailureSummary,
)

if TYPE_CHECKING:
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun, ItemResult
    from app.evaluation.domain.enums.evaluation_enums import FailureReason, RunStatus


class TransitionValidator:
    """Validates state transitions for evaluation runs."""

    def __init__(self) -> None:
        """Initialize with the run state machine."""
        self._state_machine = RunStateMachine()

    def validate(self, run: EvaluationRun, target: RunStatus) -> TransitionResult:
        """Validate a transition for the given run."""
        ctx = TransitionContext(
            run_id=run.id,
            items_completed=run.items_completed,
            items_total=run.items_total,
            has_checkpoint=run.checkpoint is not None,
        )
        return self._state_machine.transition(run.status, target, ctx)

    def valid_targets(self, run: EvaluationRun) -> list[RunStatus]:
        """Return all valid target states for the given run."""
        return self._state_machine.valid_targets(run.status)


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Result of a transition validation."""

    success: bool
    new_status: RunStatus
    error: object | None = None
    guard_failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FailureThresholdConfig:
    """Configuration for failure threshold policy."""

    max_failure_rate: float = 0.5
    max_consecutive_failures: int = 10
    min_success_rate: float = 0.5


class FailureThresholdPolicy:
    """Evaluates whether a run should continue based on failure rates."""

    def should_continue(
        self,
        run: EvaluationRun,
        config: FailureThresholdConfig | None = None,
    ) -> bool:
        """Determine if the run should continue processing."""
        effective_config = config or FailureThresholdConfig()

        if run.items_completed == 0:
            return True

        failure_rate = run.items_failed / run.items_completed
        if failure_rate > effective_config.max_failure_rate:
            return False

        success_rate = (run.items_completed - run.items_failed) / run.items_completed
        return success_rate >= effective_config.min_success_rate

    def build_failure_summary(
        self,
        run: EvaluationRun,
        item_results: list[ItemResult],
    ) -> FailureSummary:
        """Build a failure summary from item results."""
        reason_counts: dict[str, int] = {}
        first_failure: str | None = None
        last_failure: str | None = None

        for result in item_results:
            if result.error is not None:
                if first_failure is None:
                    first_failure = result.error
                last_failure = result.error
                reason_key = result.failure_reason.value if result.failure_reason else "unknown"
                reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1

        return FailureSummary(
            total_items=run.items_total,
            failed_items=run.items_failed,
            failure_reasons=reason_counts,
            first_failure=first_failure,
            last_failure=last_failure,
        )


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    """Current budget consumption status."""

    cost_usd: float = 0.0
    tokens_used: int = 0
    elapsed_seconds: float = 0.0
    cost_exceeded: bool = False
    tokens_exceeded: bool = False
    time_exceeded: bool = False

    @property
    def is_within_budget(self) -> bool:
        """Return True if all budgets are within limits."""
        return not self.cost_exceeded and not self.tokens_exceeded and not self.time_exceeded


class BudgetPolicy:
    """Evaluates whether a run is within its execution budget."""

    def check_budget(
        self,
        budget: ExecutionBudget,
        total_tokens: int = 0,
        cost_usd: float = 0.0,
        elapsed_seconds: float = 0.0,
    ) -> BudgetStatus:
        """Check current budget consumption against limits."""
        cost_exceeded = budget.max_cost_usd is not None and cost_usd > budget.max_cost_usd
        tokens_exceeded = budget.max_tokens is not None and total_tokens > budget.max_tokens
        time_exceeded = (
            budget.max_duration_seconds is not None
            and elapsed_seconds > budget.max_duration_seconds
        )

        return BudgetStatus(
            cost_usd=cost_usd,
            tokens_used=total_tokens,
            elapsed_seconds=elapsed_seconds,
            cost_exceeded=cost_exceeded,
            tokens_exceeded=tokens_exceeded,
            time_exceeded=time_exceeded,
        )


class ExecutionPolicyResolver:
    """Resolves the effective execution policy for a run."""

    @staticmethod
    def resolve(
        base_policy: ExecutionPolicy,
        overrides: ExecutionPolicy | None = None,
    ) -> ExecutionPolicy:
        """Resolve effective execution policy."""
        if overrides is None:
            return base_policy

        return ExecutionPolicy(
            continue_on_item_failure=(
                overrides.continue_on_item_failure
                if overrides.continue_on_item_failure != base_policy.continue_on_item_failure
                else base_policy.continue_on_item_failure
            ),
            max_retries_per_item=(
                overrides.max_retries_per_item
                if overrides.max_retries_per_item != 0
                else base_policy.max_retries_per_item
            ),
            timeout_per_item_seconds=(
                overrides.timeout_per_item_seconds
                if overrides.timeout_per_item_seconds is not None
                else base_policy.timeout_per_item_seconds
            ),
        )

    @staticmethod
    def should_retry(
        policy: ExecutionPolicy,
        current_retry: int,
        failure_reason: FailureReason,
    ) -> bool:
        """Determine if an item should be retried."""
        if current_retry >= policy.max_retries_per_item:
            return False
        return failure_reason.is_retryable
