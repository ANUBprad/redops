"""Tests for the evaluation run state machine."""

from __future__ import annotations

from app.evaluation.domain.enums.evaluation_enums import RunStatus
from app.evaluation.domain.state_machine.run_state_machine import (
    InvalidTransitionError,
    RunStateMachine,
    TransitionContext,
)
from app.kernel.entities.base import UUIDv7


class TestRunStateMachine:
    """Tests for RunStateMachine."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.sm = RunStateMachine()
        self.default_ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=0,
            items_total=100,
            has_checkpoint=False,
        )

    def test_created_to_queued(self) -> None:
        """CREATED → QUEUED is valid."""
        result = self.sm.transition(RunStatus.CREATED, RunStatus.QUEUED, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.QUEUED

    def test_queued_to_starting(self) -> None:
        """QUEUED → STARTING is valid."""
        result = self.sm.transition(RunStatus.QUEUED, RunStatus.STARTING, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.STARTING

    def test_queued_to_cancelled(self) -> None:
        """QUEUED → CANCELLED is valid with force."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=0,
            items_total=100,
            has_checkpoint=False,
            force=True,
        )
        result = self.sm.transition(RunStatus.QUEUED, RunStatus.CANCELLED, ctx)
        assert result.success is True
        assert result.new_status == RunStatus.CANCELLED

    def test_starting_to_running(self) -> None:
        """STARTING → RUNNING is valid."""
        result = self.sm.transition(RunStatus.STARTING, RunStatus.RUNNING, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.RUNNING

    def test_starting_to_failed(self) -> None:
        """STARTING → FAILED is valid."""
        result = self.sm.transition(RunStatus.STARTING, RunStatus.FAILED, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.FAILED

    def test_running_to_paused(self) -> None:
        """RUNNING → PAUSED is valid."""
        result = self.sm.transition(RunStatus.RUNNING, RunStatus.PAUSED, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.PAUSED

    def test_running_to_cancelling(self) -> None:
        """RUNNING → CANCELLING is valid."""
        result = self.sm.transition(RunStatus.RUNNING, RunStatus.CANCELLING, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.CANCELLING

    def test_running_to_completed_all_items(self) -> None:
        """RUNNING → COMPLETED is valid when all items done."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=100,
            items_total=100,
        )
        result = self.sm.transition(RunStatus.RUNNING, RunStatus.COMPLETED, ctx)
        assert result.success is True
        assert result.new_status == RunStatus.COMPLETED

    def test_running_to_completed_guard_fails(self) -> None:
        """RUNNING → COMPLETED fails when not all items done."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=50,
            items_total=100,
        )
        result = self.sm.transition(RunStatus.RUNNING, RunStatus.COMPLETED, ctx)
        assert result.success is False
        assert result.error is not None
        assert result.guard_failures

    def test_running_to_failed(self) -> None:
        """RUNNING → FAILED is valid."""
        result = self.sm.transition(RunStatus.RUNNING, RunStatus.FAILED, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.FAILED

    def test_running_to_timedout(self) -> None:
        """RUNNING → TIMEDOUT is valid."""
        result = self.sm.transition(RunStatus.RUNNING, RunStatus.TIMEDOUT, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.TIMEDOUT

    def test_paused_to_running(self) -> None:
        """PAUSED → RUNNING is valid with checkpoint."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=50,
            items_total=100,
            has_checkpoint=True,
        )
        result = self.sm.transition(RunStatus.PAUSED, RunStatus.RUNNING, ctx)
        assert result.success is True
        assert result.new_status == RunStatus.RUNNING

    def test_paused_to_running_no_checkpoint(self) -> None:
        """PAUSED → RUNNING fails without checkpoint."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=50,
            items_total=100,
            has_checkpoint=False,
        )
        result = self.sm.transition(RunStatus.PAUSED, RunStatus.RUNNING, ctx)
        assert result.success is False

    def test_paused_to_cancelling(self) -> None:
        """PAUSED → CANCELLING is valid."""
        result = self.sm.transition(RunStatus.PAUSED, RunStatus.CANCELLING, self.default_ctx)
        assert result.success is True
        assert result.new_status == RunStatus.CANCELLING

    def test_cancelling_to_completed(self) -> None:
        """CANCELLING → COMPLETED with all items done."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=100,
            items_total=100,
        )
        result = self.sm.transition(RunStatus.CANCELLING, RunStatus.COMPLETED, ctx)
        assert result.success is True

    def test_cancelling_to_cancelled(self) -> None:
        """CANCELLING → CANCELLED with force."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=50,
            items_total=100,
            force=True,
        )
        result = self.sm.transition(RunStatus.CANCELLING, RunStatus.CANCELLED, ctx)
        assert result.success is True

    def test_cancelling_to_cancelled_guard_fails(self) -> None:
        """CANCELLING → CANCELLED fails without force and incomplete items."""
        ctx = TransitionContext(
            run_id=UUIDv7.generate(),
            items_completed=50,
            items_total=100,
            force=False,
        )
        result = self.sm.transition(RunStatus.CANCELLING, RunStatus.CANCELLED, ctx)
        assert result.success is False

    def test_cancelling_to_failed(self) -> None:
        """CANCELLING → FAILED is valid."""
        result = self.sm.transition(RunStatus.CANCELLING, RunStatus.FAILED, self.default_ctx)
        assert result.success is True

    def test_invalid_transition(self) -> None:
        """Invalid transition returns failure."""
        result = self.sm.transition(RunStatus.CREATED, RunStatus.RUNNING, self.default_ctx)
        assert result.success is False
        assert isinstance(result.error, InvalidTransitionError)

    def test_terminal_state_blocks_transition(self) -> None:
        """Terminal states block further transitions."""
        result = self.sm.transition(RunStatus.COMPLETED, RunStatus.RUNNING, self.default_ctx)
        assert result.success is False

    def test_terminal_state_same_status(self) -> None:
        """Terminal state can transition to same status (no-op)."""
        result = self.sm.transition(RunStatus.COMPLETED, RunStatus.COMPLETED, self.default_ctx)
        assert result.success is True

    def test_can_transition(self) -> None:
        """can_transition checks validity."""
        assert self.sm.can_transition(RunStatus.CREATED, RunStatus.QUEUED) is True
        assert self.sm.can_transition(RunStatus.CREATED, RunStatus.RUNNING) is False

    def test_valid_targets(self) -> None:
        """valid_targets returns reachable states."""
        targets = self.sm.valid_targets(RunStatus.CREATED)
        assert RunStatus.QUEUED in targets
        assert RunStatus.RUNNING not in targets

    def test_is_terminal(self) -> None:
        """is_terminal checks terminal states."""
        assert self.sm.is_terminal(RunStatus.COMPLETED) is True
        assert self.sm.is_terminal(RunStatus.RUNNING) is False

    def test_invalid_transition_error_details(self) -> None:
        """InvalidTransitionError carries details."""
        error = InvalidTransitionError(
            current_status=RunStatus.CREATED,
            target_status=RunStatus.RUNNING,
        )
        assert error.error_code == "INVALID_TRANSITION"
        assert error.current_status == RunStatus.CREATED
        assert error.target_status == RunStatus.RUNNING
        assert error.http_status == 409
