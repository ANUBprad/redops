"""Tests for agent domain entities."""

from __future__ import annotations

import pytest

from app.agents.domain.entities.agent_entities import (
    AgentRun,
    AgentRunTransitionError,
    AgentStep,
    InvalidAgentStepStateError,
)
from app.agents.domain.enums.agent_enums import (
    AgentRunFailureReason,
    AgentRunStatus,
    StepStatus,
)
from app.agents.domain.value_objects.agent_value_objects import (
    AgentConfiguration,
    AgentProfile,
    AgentStepResult,
)
from app.kernel.entities.base import UUIDv7


def _make_config(
    name: str = "Test Agent",
) -> AgentConfiguration:
    return AgentConfiguration(
        name=name,
        profile=AgentProfile(provider_name="openai", model_id="gpt-4"),
    )


def _make_run(
    name: str = "Test Agent",
) -> AgentRun:
    config = _make_config(name=name)
    return AgentRun(
        agent_name=name,
        config=config,
    )


class TestAgentStep:
    """Tests for AgentStep entity."""

    def test_creation(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0, tool_name="search")
        assert step.index == 0
        assert step.tool_name == "search"
        assert step.status == StepStatus.PENDING

    def test_start(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0)
        step.start()
        assert step.status == StepStatus.RUNNING

    def test_complete(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0)
        step.start()
        result = AgentStepResult(step_id=str(step.id), step_index=0, success=True)
        step.complete(result)
        assert step.status == StepStatus.COMPLETED
        assert step.result is not None

    def test_fail(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0)
        step.start()
        step.fail("Something went wrong")
        assert step.status == StepStatus.FAILED

    def test_skip(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0)
        step.skip()
        assert step.status == StepStatus.SKIPPED

    def test_cancel(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0)
        step.cancel()
        assert step.status == StepStatus.CANCELLED

    def test_cannot_start_running_step(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0)
        step.start()
        with pytest.raises(InvalidAgentStepStateError):
            step.start()

    def test_cannot_complete_pending_step(self) -> None:
        step = AgentStep(run_id=UUIDv7.generate(), index=0)
        with pytest.raises(InvalidAgentStepStateError):
            step.complete(AgentStepResult(step_id=str(step.id), step_index=0))


class TestAgentRun:
    """Tests for AgentRun aggregate."""

    def test_creation(self) -> None:
        run = _make_run()
        assert run.status == AgentRunStatus.CREATED
        assert run.agent_name == "Test Agent"

    def test_queue(self) -> None:
        run = _make_run()
        run.queue()
        assert run.status == AgentRunStatus.QUEUED

    def test_start(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=5)
        assert run.status == AgentRunStatus.RUNNING
        assert run.steps_total == 5
        assert run.started_at is not None

    def test_complete(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        run.complete()
        assert run.status == AgentRunStatus.COMPLETED
        assert run.completed_at is not None

    def test_fail(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        run.fail(error_code="INTERNAL_ERROR", error_message="Something failed")
        assert run.status == AgentRunStatus.FAILED
        assert run.failure_summary == AgentRunFailureReason.INTERNAL_ERROR

    def test_cancel(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        run.cancel()
        assert run.status == AgentRunStatus.CANCELLING

    def test_cancel_force(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        run.cancel(force=True)
        assert run.status == AgentRunStatus.CANCELLED

    def test_timeout(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        run.timeout()
        assert run.status == AgentRunStatus.TIMEDOUT

    def test_record_step_success(self) -> None:
        run = _make_run()
        run.record_step_success()
        assert run.steps_completed == 1

    def test_record_step_failure(self) -> None:
        run = _make_run()
        run.record_step_failure()
        assert run.steps_failed == 1
        assert run.steps_completed == 1

    def test_record_token_usage(self) -> None:
        run = _make_run()
        run.record_token_usage(100, 50)
        assert run.token_input == 100
        assert run.token_output == 50
        assert run.total_tokens == 150

    def test_record_cost(self) -> None:
        run = _make_run()
        run.record_cost(0.05)
        assert run.cost == 0.05

    def test_record_latency(self) -> None:
        run = _make_run()
        run.record_latency(100)
        assert run.average_latency_ms == 100

    def test_progress(self) -> None:
        run = _make_run()
        run.steps_total = 10
        run.steps_completed = 5
        assert run.progress == 50.0

    def test_duration_ms_not_started(self) -> None:
        run = _make_run()
        assert run.duration_ms == 0

    def test_cannot_queue_from_running(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        with pytest.raises(AgentRunTransitionError):
            run.queue()

    def test_cannot_start_from_created(self) -> None:
        run = _make_run()
        with pytest.raises(AgentRunTransitionError):
            run.start(total_steps=1)

    def test_events_raised_on_queue(self) -> None:
        run = _make_run()
        run.queue()
        events = run.collect_events()
        assert len(events) == 1
        assert events[0].event_type == "agents.run.queued"

    def test_events_raised_on_start(self) -> None:
        run = _make_run()
        run.queue()
        run.collect_events()  # clear queued event
        run.start(total_steps=3)
        events = run.collect_events()
        assert len(events) == 1
        assert events[0].event_type == "agents.run.started"

    def test_events_raised_on_complete(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        run.collect_events()  # clear prior events
        run.complete()
        events = run.collect_events()
        assert len(events) == 1
        assert events[0].event_type == "agents.run.completed"

    def test_events_raised_on_fail(self) -> None:
        run = _make_run()
        run.queue()
        run.start(total_steps=1)
        run.collect_events()  # clear prior events
        run.fail(error_code="test_error", error_message="test")
        events = run.collect_events()
        assert len(events) == 1
        assert events[0].event_type == "agents.run.failed"
