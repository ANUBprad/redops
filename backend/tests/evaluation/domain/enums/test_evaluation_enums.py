"""Tests for evaluation domain enums."""

from __future__ import annotations

from app.evaluation.domain.enums.evaluation_enums import (
    CancellationReason,
    EvaluationType,
    FailureReason,
    ItemStatus,
    Priority,
    RunStatus,
)


class TestRunStatus:
    """Tests for RunStatus enum."""

    def test_terminal_states(self) -> None:
        """Terminal states are COMPLETED, FAILED, TIMEDOUT, CANCELLED."""
        assert RunStatus.COMPLETED.is_terminal is True
        assert RunStatus.FAILED.is_terminal is True
        assert RunStatus.TIMEDOUT.is_terminal is True
        assert RunStatus.CANCELLED.is_terminal is True

    def test_non_terminal_states(self) -> None:
        """Non-terminal states return False for is_terminal."""
        assert RunStatus.CREATED.is_terminal is False
        assert RunStatus.QUEUED.is_terminal is False
        assert RunStatus.STARTING.is_terminal is False
        assert RunStatus.RUNNING.is_terminal is False
        assert RunStatus.PAUSED.is_terminal is False
        assert RunStatus.CANCELLING.is_terminal is False

    def test_active_states(self) -> None:
        """Active states are STARTING, RUNNING, PAUSED, CANCELLING."""
        assert RunStatus.STARTING.is_active is True
        assert RunStatus.RUNNING.is_active is True
        assert RunStatus.PAUSED.is_active is True
        assert RunStatus.CANCELLING.is_active is True

    def test_non_active_states(self) -> None:
        """Non-active states return False for is_active."""
        assert RunStatus.CREATED.is_active is False
        assert RunStatus.QUEUED.is_active is False
        assert RunStatus.COMPLETED.is_active is False
        assert RunStatus.FAILED.is_active is False
        assert RunStatus.TIMEDOUT.is_active is False
        assert RunStatus.CANCELLED.is_active is False

    def test_is_success(self) -> None:
        """Only COMPLETED is success."""
        assert RunStatus.COMPLETED.is_success is True
        assert RunStatus.FAILED.is_success is False
        assert RunStatus.TIMEDOUT.is_success is False
        assert RunStatus.CANCELLED.is_success is False

    def test_all_values(self) -> None:
        """All expected values exist."""
        expected = {
            "created",
            "queued",
            "starting",
            "running",
            "paused",
            "cancelling",
            "completed",
            "failed",
            "timedout",
            "cancelled",
        }
        assert {s.value for s in RunStatus} == expected


class TestItemStatus:
    """Tests for ItemStatus enum."""

    def test_terminal_states(self) -> None:
        """Terminal states are COMPLETED, FAILED, SKIPPED, CANCELLED."""
        assert ItemStatus.COMPLETED.is_terminal is True
        assert ItemStatus.FAILED.is_terminal is True
        assert ItemStatus.SKIPPED.is_terminal is True
        assert ItemStatus.CANCELLED.is_terminal is True

    def test_non_terminal_states(self) -> None:
        """PENDING and RUNNING are not terminal."""
        assert ItemStatus.PENDING.is_terminal is False
        assert ItemStatus.RUNNING.is_terminal is False


class TestFailureReason:
    """Tests for FailureReason enum."""

    def test_retryable_reasons(self) -> None:
        """Retryable reasons are timeout, unavailable, rate limited."""
        assert FailureReason.PROVIDER_TIMEOUT.is_retryable is True
        assert FailureReason.PROVIDER_UNAVAILABLE.is_retryable is True
        assert FailureReason.RATE_LIMITED.is_retryable is True

    def test_non_retryable_reasons(self) -> None:
        """Non-retryable reasons return False."""
        assert FailureReason.AUTHENTICATION_FAILED.is_retryable is False
        assert FailureReason.INVALID_MODEL.is_retryable is False
        assert FailureReason.CONTEXT_WINDOW_EXCEEDED.is_retryable is False
        assert FailureReason.INTERNAL_ERROR.is_retryable is False


class TestPriority:
    """Tests for Priority enum."""

    def test_numeric_ordering(self) -> None:
        """Numeric values maintain expected ordering."""
        assert Priority.LOW.numeric < Priority.NORMAL.numeric
        assert Priority.NORMAL.numeric < Priority.HIGH.numeric
        assert Priority.HIGH.numeric < Priority.CRITICAL.numeric

    def test_numeric_values(self) -> None:
        """Numeric values are as expected."""
        assert Priority.LOW.numeric == 0
        assert Priority.NORMAL.numeric == 1
        assert Priority.HIGH.numeric == 2
        assert Priority.CRITICAL.numeric == 3


class TestCancellationReason:
    """Tests for CancellationReason enum."""

    def test_all_values(self) -> None:
        """All expected values exist."""
        expected = {
            "user_cancelled",
            "system_cancelled",
            "quota_exceeded",
            "budget_exceeded",
            "deployment_cancelled",
            "timeout_exceeded",
        }
        assert {r.value for r in CancellationReason} == expected


class TestEvaluationType:
    """Tests for EvaluationType enum."""

    def test_all_values(self) -> None:
        """All expected values exist."""
        expected = {"single", "dataset", "regression", "safety", "rag", "comparison"}
        assert {t.value for t in EvaluationType} == expected
