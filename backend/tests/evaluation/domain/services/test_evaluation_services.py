"""Tests for evaluation domain services."""

from __future__ import annotations

from app.evaluation.domain.entities.evaluation_entities import (
    EvaluationRun,
    ItemResult,
    RunCheckpoint,
)
from app.evaluation.domain.enums.evaluation_enums import (
    FailureReason,
    ItemStatus,
    RunStatus,
)
from app.evaluation.domain.services.evaluation_services import (
    BudgetPolicy,
    ExecutionPolicyResolver,
    FailureThresholdConfig,
    FailureThresholdPolicy,
    TransitionValidator,
)
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionPolicy,
)
from app.kernel.entities.base import UUIDv7


def _make_run(
    status: RunStatus = RunStatus.RUNNING,
    items_completed: int = 0,
    items_total: int = 100,
    items_failed: int = 0,
) -> EvaluationRun:
    """Create a run with specified state."""
    config = EvaluationConfiguration(
        name="Test",
        eval_type="single",
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        metrics=("accuracy",),
    )
    run = EvaluationRun(
        evaluation_name="Test",
        config=config,
        profile=config.profile,
    )
    # Force status through state machine
    if status != RunStatus.CREATED:
        run.queue()
    if status in (
        RunStatus.RUNNING,
        RunStatus.PAUSED,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.TIMEDOUT,
    ):
        run.start(total_items=items_total)
    if status == RunStatus.PAUSED:
        run.save_checkpoint(
            RunCheckpoint(
                run_id=run.id,
                checkpoint_number=1,
                items_completed=items_completed,
                items_total=items_total,
                last_item_index=items_completed - 1,
            ),
        )
        run.pause()

    run.items_completed = items_completed
    run.items_failed = items_failed
    return run


class TestTransitionValidator:
    """Tests for TransitionValidator service."""

    def test_valid_transition(self) -> None:
        """Valid transition succeeds."""
        run = _make_run(RunStatus.RUNNING)
        validator = TransitionValidator()
        result = validator.validate(run, RunStatus.PAUSED)
        assert result.success is True

    def test_invalid_transition(self) -> None:
        """Invalid transition fails."""
        run = _make_run(RunStatus.RUNNING)
        validator = TransitionValidator()
        result = validator.validate(run, RunStatus.QUEUED)
        assert result.success is False
        assert result.error is not None

    def test_valid_targets(self) -> None:
        """valid_targets returns reachable states."""
        run = _make_run(RunStatus.RUNNING)
        validator = TransitionValidator()
        targets = validator.valid_targets(run)
        assert RunStatus.PAUSED in targets
        assert RunStatus.CANCELLING in targets
        assert RunStatus.COMPLETED in targets


class TestFailureThresholdPolicy:
    """Tests for FailureThresholdPolicy service."""

    def test_continue_when_no_failures(self) -> None:
        """Continue when no failures."""
        run = _make_run(items_completed=10, items_failed=0)
        policy = FailureThresholdPolicy()
        assert policy.should_continue(run) is True

    def test_continue_within_threshold(self) -> None:
        """Continue when within failure threshold."""
        run = _make_run(items_completed=100, items_failed=10)
        policy = FailureThresholdPolicy()
        assert policy.should_continue(run) is True

    def test_stop_when_exceeds_threshold(self) -> None:
        """Stop when failure rate exceeds threshold."""
        run = _make_run(items_completed=100, items_failed=60)
        policy = FailureThresholdPolicy()
        assert policy.should_continue(run) is False

    def test_custom_threshold(self) -> None:
        """Custom threshold configuration."""
        run = _make_run(items_completed=100, items_failed=30)
        config = FailureThresholdConfig(max_failure_rate=0.2)
        policy = FailureThresholdPolicy()
        assert policy.should_continue(run, config) is False

    def test_no_items_completed(self) -> None:
        """Always continue when no items completed."""
        run = _make_run(items_completed=0, items_failed=0)
        policy = FailureThresholdPolicy()
        assert policy.should_continue(run) is True

    def test_build_failure_summary(self) -> None:
        """Build failure summary from results."""
        run = _make_run(items_completed=3, items_failed=2)
        results = [
            ItemResult(
                item_id=UUIDv7.generate(),
                item_index=0,
                status=ItemStatus.COMPLETED,
            ),
            ItemResult(
                item_id=UUIDv7.generate(),
                item_index=1,
                status=ItemStatus.FAILED,
                error="Timeout",
                failure_reason=FailureReason.PROVIDER_TIMEOUT,
            ),
            ItemResult(
                item_id=UUIDv7.generate(),
                item_index=2,
                status=ItemStatus.FAILED,
                error="Unavailable",
                failure_reason=FailureReason.PROVIDER_UNAVAILABLE,
            ),
        ]
        policy = FailureThresholdPolicy()
        summary = policy.build_failure_summary(run, results)
        assert summary.total_items == 100
        assert summary.failed_items == 2
        assert summary.first_failure == "Timeout"
        assert summary.last_failure == "Unavailable"


class TestBudgetPolicy:
    """Tests for BudgetPolicy service."""

    def test_within_budget(self) -> None:
        """Within budget when no limits exceeded."""
        budget = ExecutionBudget(max_cost_usd=10.0, max_tokens=100000)
        policy = BudgetPolicy()
        status = policy.check_budget(budget, total_tokens=50000, cost_usd=5.0)
        assert status.is_within_budget is True

    def test_cost_exceeded(self) -> None:
        """Cost exceeded detection."""
        budget = ExecutionBudget(max_cost_usd=10.0)
        policy = BudgetPolicy()
        status = policy.check_budget(budget, cost_usd=15.0)
        assert status.cost_exceeded is True
        assert status.is_within_budget is False

    def test_tokens_exceeded(self) -> None:
        """Tokens exceeded detection."""
        budget = ExecutionBudget(max_tokens=100000)
        policy = BudgetPolicy()
        status = policy.check_budget(budget, total_tokens=150000)
        assert status.tokens_exceeded is True
        assert status.is_within_budget is False

    def test_time_exceeded(self) -> None:
        """Time exceeded detection."""
        budget = ExecutionBudget(max_duration_seconds=3600)
        policy = BudgetPolicy()
        status = policy.check_budget(budget, elapsed_seconds=5000)
        assert status.time_exceeded is True
        assert status.is_within_budget is False

    def test_unlimited_budget(self) -> None:
        """Unlimited budget is always within budget."""
        budget = ExecutionBudget()
        policy = BudgetPolicy()
        status = policy.check_budget(
            budget, cost_usd=999999, total_tokens=999999999, elapsed_seconds=999999
        )
        assert status.is_within_budget is True


class TestExecutionPolicyResolver:
    """Tests for ExecutionPolicyResolver service."""

    def test_resolve_no_overrides(self) -> None:
        """No overrides returns base policy."""
        base = ExecutionPolicy(max_retries_per_item=2)
        result = ExecutionPolicyResolver.resolve(base)
        assert result.max_retries_per_item == 2

    def test_resolve_with_overrides(self) -> None:
        """Overrides replace base values."""
        base = ExecutionPolicy(max_retries_per_item=2, timeout_per_item_seconds=30)
        overrides = ExecutionPolicy(max_retries_per_item=5)
        result = ExecutionPolicyResolver.resolve(base, overrides)
        assert result.max_retries_per_item == 5
        assert result.timeout_per_item_seconds == 30

    def test_should_retry_within_limit(self) -> None:
        """Should retry when within limit and retryable reason."""
        policy = ExecutionPolicy(max_retries_per_item=3)
        assert (
            ExecutionPolicyResolver.should_retry(policy, 1, FailureReason.PROVIDER_TIMEOUT) is True
        )

    def test_should_retry_at_limit(self) -> None:
        """Should not retry at retry limit."""
        policy = ExecutionPolicy(max_retries_per_item=3)
        assert (
            ExecutionPolicyResolver.should_retry(policy, 3, FailureReason.PROVIDER_TIMEOUT) is False
        )

    def test_should_retry_non_retryable(self) -> None:
        """Should not retry non-retryable reason."""
        policy = ExecutionPolicy(max_retries_per_item=3)
        assert (
            ExecutionPolicyResolver.should_retry(policy, 1, FailureReason.AUTHENTICATION_FAILED)
            is False
        )
