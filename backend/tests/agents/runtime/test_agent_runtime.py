"""Tests for agent runtime components."""

from __future__ import annotations

import pytest

from app.agents.domain.entities.agent_entities import AgentRun
from app.agents.domain.value_objects.agent_value_objects import (
    AgentConfiguration,
    AgentProfile,
)
from app.agents.runtime.checkpoint import AgentCheckpointManager
from app.agents.runtime.executor import AgentExecutor
from app.agents.runtime.planner import AgentPlanner


def _make_run() -> AgentRun:
    config = AgentConfiguration(
        name="Test Agent",
        profile=AgentProfile(provider_name="openai", model_id="gpt-4"),
        max_steps=5,
    )
    return AgentRun(agent_name="Test Agent", config=config)


class TestAgentPlanner:
    """Tests for AgentPlanner."""

    @pytest.mark.asyncio
    async def test_plan_creation(self) -> None:
        run = _make_run()
        planner = AgentPlanner()
        plan = await planner.plan(run)
        assert plan.total_steps == 5
        assert plan.run_id == str(run.id)

    @pytest.mark.asyncio
    async def test_validate_plan(self) -> None:
        from app.agents.runtime.planner import AgentExecutionPlan

        planner = AgentPlanner()
        plan = AgentExecutionPlan(
            run_id="test-id",
            total_steps=5,
            timeout_per_step=60,
        )
        errors = await planner.validate_plan(plan)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_plan_invalid_steps(self) -> None:
        from app.agents.runtime.planner import AgentExecutionPlan

        planner = AgentPlanner()
        plan = AgentExecutionPlan(
            run_id="test-id",
            total_steps=0,
            timeout_per_step=60,
        )
        errors = await planner.validate_plan(plan)
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_estimate(self) -> None:
        run = _make_run()
        planner = AgentPlanner()
        estimate = await planner.estimate(run)
        assert estimate.estimated_steps == 5
        assert estimate.estimated_tokens > 0


class TestAgentExecutor:
    """Tests for AgentExecutor."""

    @pytest.mark.asyncio
    async def test_execute_step_success(self) -> None:
        run = _make_run()
        executor = AgentExecutor()
        result = await executor.execute_step(run, step_index=0, tool_name="search")
        assert result.success
        assert result.step_index == 0

    @pytest.mark.asyncio
    async def test_classify_failure_timeout(self) -> None:
        executor = AgentExecutor()
        from app.agents.domain.enums.agent_enums import AgentRunFailureReason

        reason = executor.classify_failure("Provider timeout error")
        assert reason == AgentRunFailureReason.PROVIDER_TIMEOUT

    @pytest.mark.asyncio
    async def test_classify_failure_rate_limit(self) -> None:
        executor = AgentExecutor()
        from app.agents.domain.enums.agent_enums import AgentRunFailureReason

        reason = executor.classify_failure("Rate limit exceeded")
        assert reason == AgentRunFailureReason.RATE_LIMITED


class TestAgentCheckpointManager:
    """Tests for AgentCheckpointManager."""

    @pytest.mark.asyncio
    async def test_should_checkpoint(self) -> None:
        manager = AgentCheckpointManager()
        assert manager.should_checkpoint(5, 5)
        assert not manager.should_checkpoint(3, 5)
        assert not manager.should_checkpoint(0, 5)

    @pytest.mark.asyncio
    async def test_next_checkpoint_target(self) -> None:
        manager = AgentCheckpointManager()
        target = manager.next_checkpoint_target(3, 5)
        assert target == 5

        target = manager.next_checkpoint_target(5, 5)
        assert target == 10
