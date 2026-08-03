"""Tests for agent domain enums."""

from __future__ import annotations

from app.agents.domain.enums.agent_enums import (
    AgentRunFailureReason,
    AgentRunPriority,
    AgentRunStatus,
    StepStatus,
)


class TestAgentRunStatus:
    """Tests for AgentRunStatus enum."""

    def test_created_is_not_terminal(self) -> None:
        assert not AgentRunStatus.CREATED.is_terminal

    def test_completed_is_terminal(self) -> None:
        assert AgentRunStatus.COMPLETED.is_terminal

    def test_failed_is_terminal(self) -> None:
        assert AgentRunStatus.FAILED.is_terminal

    def test_timedout_is_terminal(self) -> None:
        assert AgentRunStatus.TIMEDOUT.is_terminal

    def test_cancelled_is_terminal(self) -> None:
        assert AgentRunStatus.CANCELLED.is_terminal

    def test_running_is_active(self) -> None:
        assert AgentRunStatus.RUNNING.is_active

    def test_completed_is_success(self) -> None:
        assert AgentRunStatus.COMPLETED.is_success

    def test_failed_is_not_success(self) -> None:
        assert not AgentRunStatus.FAILED.is_success


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_completed_is_terminal(self) -> None:
        assert StepStatus.COMPLETED.is_terminal

    def test_pending_is_not_terminal(self) -> None:
        assert not StepStatus.PENDING.is_terminal


class TestAgentRunPriority:
    """Tests for AgentRunPriority enum."""

    def test_numeric_ordering(self) -> None:
        assert AgentRunPriority.LOW.numeric < AgentRunPriority.NORMAL.numeric
        assert AgentRunPriority.NORMAL.numeric < AgentRunPriority.HIGH.numeric
        assert AgentRunPriority.HIGH.numeric < AgentRunPriority.CRITICAL.numeric


class TestAgentRunFailureReason:
    """Tests for AgentRunFailureReason enum."""

    def test_provider_timeout_is_retryable(self) -> None:
        assert AgentRunFailureReason.PROVIDER_TIMEOUT.is_retryable

    def test_internal_error_is_not_retryable(self) -> None:
        assert not AgentRunFailureReason.INTERNAL_ERROR.is_retryable
