"""Tests for agent domain events."""

from __future__ import annotations

from app.agents.domain.events.agent_events import (
    AgentCheckpointCreated,
    AgentRunCancelled,
    AgentRunCompleted,
    AgentRunCreated,
    AgentRunFailed,
    AgentRunQueued,
    AgentRunStarted,
    AgentRunTimedOut,
    AgentStepCompleted,
    AgentStepFailed,
    AgentStepStarted,
)


class TestAgentRunCreated:
    """Tests for AgentRunCreated event."""

    def test_event_type(self) -> None:
        event = AgentRunCreated()
        assert event.event_type == "agents.run.created"

    def test_has_event_id(self) -> None:
        event = AgentRunCreated()
        assert event.event_id is not None

    def test_has_occurred_at(self) -> None:
        event = AgentRunCreated()
        assert event.occurred_at is not None


class TestAgentRunQueued:
    """Tests for AgentRunQueued event."""

    def test_event_type(self) -> None:
        event = AgentRunQueued()
        assert event.event_type == "agents.run.queued"


class TestAgentRunStarted:
    """Tests for AgentRunStarted event."""

    def test_event_type(self) -> None:
        event = AgentRunStarted()
        assert event.event_type == "agents.run.started"


class TestAgentRunCompleted:
    """Tests for AgentRunCompleted event."""

    def test_event_type(self) -> None:
        event = AgentRunCompleted()
        assert event.event_type == "agents.run.completed"


class TestAgentRunFailed:
    """Tests for AgentRunFailed event."""

    def test_event_type(self) -> None:
        event = AgentRunFailed()
        assert event.event_type == "agents.run.failed"


class TestAgentRunCancelled:
    """Tests for AgentRunCancelled event."""

    def test_event_type(self) -> None:
        event = AgentRunCancelled()
        assert event.event_type == "agents.run.cancelled"


class TestAgentRunTimedOut:
    """Tests for AgentRunTimedOut event."""

    def test_event_type(self) -> None:
        event = AgentRunTimedOut()
        assert event.event_type == "agents.run.timed_out"


class TestAgentStepStarted:
    """Tests for AgentStepStarted event."""

    def test_event_type(self) -> None:
        event = AgentStepStarted()
        assert event.event_type == "agents.step.started"


class TestAgentStepCompleted:
    """Tests for AgentStepCompleted event."""

    def test_event_type(self) -> None:
        event = AgentStepCompleted()
        assert event.event_type == "agents.step.completed"


class TestAgentStepFailed:
    """Tests for AgentStepFailed event."""

    def test_event_type(self) -> None:
        event = AgentStepFailed()
        assert event.event_type == "agents.step.failed"


class TestAgentCheckpointCreated:
    """Tests for AgentCheckpointCreated event."""

    def test_event_type(self) -> None:
        event = AgentCheckpointCreated()
        assert event.event_type == "agents.checkpoint.created"
