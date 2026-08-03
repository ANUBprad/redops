"""Tests for the AgentDefinition aggregate."""

from __future__ import annotations

import pytest

from app.agent.domain.entities.agent_definition import AgentDefinition
from app.agent.domain.enums.agent_enums import AgentStatus, AgentType
from app.agent.domain.events.agent_events import (
    AgentDefinitionActivated,
    AgentDefinitionArchived,
    AgentDefinitionCreated,
    AgentDefinitionDeactivated,
    AgentDefinitionDeleted,
    AgentDefinitionUpdated,
)
from app.agent.domain.value_objects.agent_vos import (
    AgentDescription,
    AgentEndpoint,
    AgentName,
)
from app.kernel.exceptions.errors import ConflictError, ValidationError


def _make_agent(**overrides: object) -> AgentDefinition:
    """Create a test agent with sensible defaults."""
    defaults: dict[str, object] = {
        "project_id": "proj-001",
        "name": AgentName(value="test-agent"),
        "agent_type": AgentType.LLM,
        "model": "gpt-4",
        "provider": "openai",
    }
    defaults.update(overrides)
    return AgentDefinition(**defaults)  # type: ignore[arg-type]


class TestAgentDefinitionCreation:
    """Tests for agent definition creation via factory."""

    def test_create_agent_success(self) -> None:
        agent = AgentDefinition.create(
            project_id="proj-001",
            name=AgentName(value="my-agent"),
            agent_type=AgentType.LLM,
            model="gpt-4",
            provider="openai",
        )
        assert agent.project_id == "proj-001"
        assert str(agent.name.value) == "my-agent"
        assert agent.agent_type == AgentType.LLM
        assert agent.model == "gpt-4"
        assert agent.provider == "openai"
        assert agent.status == AgentStatus.ACTIVE
        assert agent.version == 1

    def test_create_agent_raises_event(self) -> None:
        agent = AgentDefinition.create(
            project_id="proj-001",
            name=AgentName(value="my-agent"),
            agent_type=AgentType.LLM,
            model="gpt-4",
            provider="openai",
        )
        events = agent.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], AgentDefinitionCreated)
        assert events[0].project_id == "proj-001"
        assert events[0].name == "my-agent"

    def test_create_agent_missing_model_raises(self) -> None:
        with pytest.raises(ValidationError, match="Model is required"):
            AgentDefinition.create(
                project_id="proj-001",
                name=AgentName(value="my-agent"),
                agent_type=AgentType.LLM,
                model="",
                provider="openai",
            )

    def test_create_agent_missing_provider_raises(self) -> None:
        with pytest.raises(ValidationError, match="Provider is required"):
            AgentDefinition.create(
                project_id="proj-001",
                name=AgentName(value="my-agent"),
                agent_type=AgentType.LLM,
                model="gpt-4",
                provider="",
            )

    def test_create_agent_with_optional_fields(self) -> None:
        agent = AgentDefinition.create(
            project_id="proj-001",
            name=AgentName(value="my-agent"),
            description=AgentDescription(value="A test agent"),
            agent_type=AgentType.HYBRID,
            model="gpt-4",
            provider="openai",
            capabilities=("reasoning", "code"),
            config={"temperature": 0.7},
            endpoint=AgentEndpoint(value="https://custom.api/agent"),
            created_by="user-001",
        )
        assert agent.description is not None
        assert agent.description.value == "A test agent"
        assert agent.capabilities == ("reasoning", "code")
        assert agent.config["temperature"] == 0.7
        assert agent.endpoint is not None
        assert agent.created_by == "user-001"


class TestAgentDefinitionUpdate:
    """Tests for agent definition mutations."""

    def test_update_agent_success(self) -> None:
        agent = _make_agent()
        agent.update(name=AgentName(value="updated-agent"))
        assert str(agent.name.value) == "updated-agent"
        assert agent.version == 2

    def test_update_agent_raises_event(self) -> None:
        agent = _make_agent()
        agent.update(name=AgentName(value="updated-agent"))
        events = agent.collect_events()
        assert any(isinstance(e, AgentDefinitionUpdated) for e in events)

    def test_update_archived_agent_raises(self) -> None:
        agent = _make_agent()
        agent.archive()
        with pytest.raises(ConflictError, match="Archived agents cannot be updated"):
            agent.update(name=AgentName(value="fail"))

    def test_update_inherited_agent_raises(self) -> None:
        agent = _make_agent(status=AgentStatus.ERROR)
        with pytest.raises(ConflictError, match="Archived agents cannot be updated"):
            agent.update(name=AgentName(value="fail"))


class TestAgentDefinitionLifecycle:
    """Tests for agent definition lifecycle transitions."""

    def test_activate_from_inactive(self) -> None:
        agent = _make_agent(status=AgentStatus.INACTIVE)
        agent.activate()
        assert agent.status == AgentStatus.ACTIVE
        assert agent.version == 2

    def test_activate_from_active_raises(self) -> None:
        agent = _make_agent()
        with pytest.raises(ConflictError, match="Only inactive agents can be activated"):
            agent.activate()

    def test_activate_raises_event(self) -> None:
        agent = _make_agent(status=AgentStatus.INACTIVE)
        agent.activate()
        events = agent.collect_events()
        assert any(isinstance(e, AgentDefinitionActivated) for e in events)

    def test_deactivate_from_active(self) -> None:
        agent = _make_agent()
        agent.deactivate()
        assert agent.status == AgentStatus.INACTIVE
        assert agent.version == 2

    def test_deactivate_from_inactive_raises(self) -> None:
        agent = _make_agent(status=AgentStatus.INACTIVE)
        with pytest.raises(ConflictError, match="Only active agents can be deactivated"):
            agent.deactivate()

    def test_deactivate_raises_event(self) -> None:
        agent = _make_agent()
        agent.deactivate()
        events = agent.collect_events()
        assert any(isinstance(e, AgentDefinitionDeactivated) for e in events)

    def test_mark_error_from_active(self) -> None:
        agent = _make_agent()
        agent.mark_error()
        assert agent.status == AgentStatus.ERROR
        assert agent.version == 2

    def test_mark_error_from_archived_raises(self) -> None:
        agent = _make_agent()
        agent.archive()
        with pytest.raises(ConflictError, match="Archived agents cannot be marked as error"):
            agent.mark_error()

    def test_archive_from_active(self) -> None:
        agent = _make_agent()
        agent.archive()
        assert agent.status == AgentStatus.ARCHIVED
        assert agent.version == 2

    def test_archive_from_inactive(self) -> None:
        agent = _make_agent(status=AgentStatus.INACTIVE)
        agent.archive()
        assert agent.status == AgentStatus.ARCHIVED

    def test_archive_from_error(self) -> None:
        agent = _make_agent(status=AgentStatus.ERROR)
        agent.archive()
        assert agent.status == AgentStatus.ARCHIVED

    def test_archive_already_archived_raises(self) -> None:
        agent = _make_agent()
        agent.archive()
        with pytest.raises(ConflictError, match="Agent is already archived"):
            agent.archive()

    def test_archive_raises_event(self) -> None:
        agent = _make_agent()
        agent.archive()
        events = agent.collect_events()
        assert any(isinstance(e, AgentDefinitionArchived) for e in events)

    def test_delete_success(self) -> None:
        agent = _make_agent()
        agent.delete()
        events = agent.collect_events()
        assert any(isinstance(e, AgentDefinitionDeleted) for e in events)

    def test_delete_archived_raises(self) -> None:
        agent = _make_agent()
        agent.archive()
        with pytest.raises(ConflictError, match="Archived agents cannot be deleted"):
            agent.delete()


class TestAgentDefinitionValueObjects:
    """Tests for agent value objects."""

    def test_agent_name_valid(self) -> None:
        name = AgentName(value="test-agent")
        assert name.value == "test-agent"

    def test_agent_name_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            AgentName(value="")

    def test_agent_name_whitespace_raises(self) -> None:
        with pytest.raises(ValueError, match="Agent name cannot be empty"):
            AgentName(value="   ")

    def test_agent_name_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="Agent name cannot exceed 255"):
            AgentName(value="x" * 256)

    def test_agent_description_valid(self) -> None:
        desc = AgentDescription(value="A test agent")
        assert desc.value == "A test agent"

    def test_agent_description_too_long_raises(self) -> None:
        with pytest.raises(ValueError, match="Agent description cannot exceed 2000"):
            AgentDescription(value="x" * 2001)

    def test_agent_endpoint_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Agent endpoint cannot be empty string"):
            AgentEndpoint(value="   ")
