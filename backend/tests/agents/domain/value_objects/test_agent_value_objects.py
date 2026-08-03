"""Tests for agent domain value objects."""

from __future__ import annotations

from app.agents.domain.value_objects.agent_value_objects import (
    AgentCheckpoint,
    AgentConfiguration,
    AgentProfile,
    AgentStepResult,
)


class TestAgentProfile:
    """Tests for AgentProfile value object."""

    def test_defaults(self) -> None:
        profile = AgentProfile()
        assert profile.provider_name == ""
        assert profile.model_id == ""
        assert profile.temperature == 0.0
        assert profile.max_tokens == 4096

    def test_equality(self) -> None:
        p1 = AgentProfile(provider_name="openai", model_id="gpt-4")
        p2 = AgentProfile(provider_name="openai", model_id="gpt-4")
        assert p1 == p2


class TestAgentConfiguration:
    """Tests for AgentConfiguration value object."""

    def test_defaults(self) -> None:
        config = AgentConfiguration()
        assert config.max_steps == 10
        assert config.max_retries == 3
        assert config.timeout_seconds == 300

    def test_with_tools(self) -> None:
        config = AgentConfiguration(tools=("search", "code_exec"))
        assert len(config.tools) == 2


class TestAgentCheckpoint:
    """Tests for AgentCheckpoint value object."""

    def test_completion_ratio(self) -> None:
        cp = AgentCheckpoint(
            run_id="test-run-id",
            checkpoint_number=1,
            steps_completed=5,
            steps_total=10,
            last_step_index=4,
        )
        assert cp.completion_ratio == 0.5

    def test_is_complete(self) -> None:
        cp = AgentCheckpoint(
            run_id="test-run-id",
            checkpoint_number=1,
            steps_completed=10,
            steps_total=10,
            last_step_index=9,
        )
        assert cp.is_complete

    def test_not_complete(self) -> None:
        cp = AgentCheckpoint(
            run_id="test-run-id",
            checkpoint_number=1,
            steps_completed=3,
            steps_total=10,
            last_step_index=2,
        )
        assert not cp.is_complete


class TestAgentStepResult:
    """Tests for AgentStepResult value object."""

    def test_success_result(self) -> None:
        result = AgentStepResult(
            step_id="step-1",
            step_index=0,
            success=True,
        )
        assert result.success
        assert result.error is None

    def test_failure_result(self) -> None:
        result = AgentStepResult(
            step_id="step-1",
            step_index=0,
            success=False,
            error="Tool execution failed",
        )
        assert not result.success
        assert result.error == "Tool execution failed"
