"""Tests for agent command and query handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.application.commands import (
    ActivateAgentCommand,
    ArchiveAgentCommand,
    CreateAgentCommand,
    DeactivateAgentCommand,
    DeleteAgentCommand,
    GetAgentQuery,
    ListAgentsQuery,
    UpdateAgentCommand,
)
from app.agent.application.handlers import (
    ActivateAgentHandler,
    ArchiveAgentHandler,
    CreateAgentHandler,
    DeactivateAgentHandler,
    DeleteAgentHandler,
    GetAgentHandler,
    ListAgentsHandler,
    UpdateAgentHandler,
)
from app.agent.domain.contracts.agent_contracts import PaginatedAgents
from app.agent.domain.entities.agent_definition import AgentDefinition
from app.agent.domain.enums.agent_enums import AgentStatus, AgentType
from app.agent.domain.value_objects.agent_vos import AgentName
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, ValidationError


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


def _mock_repository() -> AsyncMock:
    """Create a mock repository with default behaviors."""
    repo = AsyncMock()
    repo.exists_by_name_in_project.return_value = False
    repo.create.return_value = None
    repo.update.return_value = None
    repo.delete.return_value = True
    repo.exists.return_value = True
    return repo


class TestCreateAgentHandler:
    """Tests for CreateAgentHandler."""

    @pytest.mark.asyncio
    async def test_create_agent_success(self) -> None:
        repo = _mock_repository()
        handler = CreateAgentHandler(repo)
        command = CreateAgentCommand(
            project_id="proj-001",
            name="my-agent",
            agent_type="llm",
            model="gpt-4",
            provider="openai",
        )
        agent = await handler.handle(command)
        assert agent.project_id == "proj-001"
        assert str(agent.name.value) == "my-agent"
        assert agent.status == AgentStatus.ACTIVE
        repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_agent_duplicate_name_raises(self) -> None:
        repo = _mock_repository()
        repo.exists_by_name_in_project.return_value = True
        handler = CreateAgentHandler(repo)
        command = CreateAgentCommand(
            project_id="proj-001",
            name="existing-agent",
            agent_type="llm",
            model="gpt-4",
            provider="openai",
        )
        with pytest.raises(ConflictError, match="already exists"):
            await handler.handle(command)

    @pytest.mark.asyncio
    async def test_create_agent_missing_model_raises(self) -> None:
        repo = _mock_repository()
        handler = CreateAgentHandler(repo)
        command = CreateAgentCommand(
            project_id="proj-001",
            name="my-agent",
            agent_type="llm",
            model="",
            provider="openai",
        )
        with pytest.raises(ValidationError, match="Model is required"):
            await handler.handle(command)

    @pytest.mark.asyncio
    async def test_create_agent_missing_provider_raises(self) -> None:
        repo = _mock_repository()
        handler = CreateAgentHandler(repo)
        command = CreateAgentCommand(
            project_id="proj-001",
            name="my-agent",
            agent_type="llm",
            model="gpt-4",
            provider="",
        )
        with pytest.raises(ValidationError, match="Provider is required"):
            await handler.handle(command)


class TestUpdateAgentHandler:
    """Tests for UpdateAgentHandler."""

    @pytest.mark.asyncio
    async def test_update_agent_success(self) -> None:
        repo = _mock_repository()
        agent = _make_agent()
        repo.get_by_id.return_value = agent
        handler = UpdateAgentHandler(repo)
        command = UpdateAgentCommand(agent_id=str(agent.id), name="updated-agent")
        result = await handler.handle(command)
        assert str(result.name.value) == "updated-agent"
        repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_agent_not_found_raises(self) -> None:
        repo = _mock_repository()
        repo.get_by_id.return_value = None
        handler = UpdateAgentHandler(repo)
        command = UpdateAgentCommand(agent_id=str(UUIDv7()), name="fail")
        with pytest.raises(NotFoundError, match="Agent not found"):
            await handler.handle(command)

    @pytest.mark.asyncio
    async def test_update_agent_duplicate_name_raises(self) -> None:
        repo = _mock_repository()
        agent = _make_agent()
        repo.get_by_id.return_value = agent
        repo.exists_by_name_in_project.return_value = True
        handler = UpdateAgentHandler(repo)
        command = UpdateAgentCommand(agent_id=str(agent.id), name="existing")
        with pytest.raises(ConflictError, match="already exists"):
            await handler.handle(command)


class TestDeleteAgentHandler:
    """Tests for DeleteAgentHandler."""

    @pytest.mark.asyncio
    async def test_delete_agent_success(self) -> None:
        repo = _mock_repository()
        agent = _make_agent()
        repo.get_by_id.return_value = agent
        handler = DeleteAgentHandler(repo)
        command = DeleteAgentCommand(agent_id=str(agent.id))
        await handler.handle(command)
        repo.delete.assert_awaited_once_with(agent.id)

    @pytest.mark.asyncio
    async def test_delete_agent_not_found_raises(self) -> None:
        repo = _mock_repository()
        repo.get_by_id.return_value = None
        handler = DeleteAgentHandler(repo)
        command = DeleteAgentCommand(agent_id=str(UUIDv7()))
        with pytest.raises(NotFoundError, match="Agent not found"):
            await handler.handle(command)


class TestActivateAgentHandler:
    """Tests for ActivateAgentHandler."""

    @pytest.mark.asyncio
    async def test_activate_agent_success(self) -> None:
        repo = _mock_repository()
        agent = _make_agent(status=AgentStatus.INACTIVE)
        repo.get_by_id.return_value = agent
        handler = ActivateAgentHandler(repo)
        command = ActivateAgentCommand(agent_id=str(agent.id))
        result = await handler.handle(command)
        assert result.status == AgentStatus.ACTIVE
        repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_activate_agent_not_found_raises(self) -> None:
        repo = _mock_repository()
        repo.get_by_id.return_value = None
        handler = ActivateAgentHandler(repo)
        command = ActivateAgentCommand(agent_id=str(UUIDv7()))
        with pytest.raises(NotFoundError, match="Agent not found"):
            await handler.handle(command)


class TestDeactivateAgentHandler:
    """Tests for DeactivateAgentHandler."""

    @pytest.mark.asyncio
    async def test_deactivate_agent_success(self) -> None:
        repo = _mock_repository()
        agent = _make_agent()
        repo.get_by_id.return_value = agent
        handler = DeactivateAgentHandler(repo)
        command = DeactivateAgentCommand(agent_id=str(agent.id))
        result = await handler.handle(command)
        assert result.status == AgentStatus.INACTIVE
        repo.update.assert_awaited_once()


class TestArchiveAgentHandler:
    """Tests for ArchiveAgentHandler."""

    @pytest.mark.asyncio
    async def test_archive_agent_success(self) -> None:
        repo = _mock_repository()
        agent = _make_agent()
        repo.get_by_id.return_value = agent
        handler = ArchiveAgentHandler(repo)
        command = ArchiveAgentCommand(agent_id=str(agent.id))
        result = await handler.handle(command)
        assert result.status == AgentStatus.ARCHIVED
        repo.update.assert_awaited_once()


class TestGetAgentHandler:
    """Tests for GetAgentHandler."""

    @pytest.mark.asyncio
    async def test_get_agent_success(self) -> None:
        repo = _mock_repository()
        agent = _make_agent()
        repo.get_by_id.return_value = agent
        handler = GetAgentHandler(repo)
        query = GetAgentQuery(agent_id=str(agent.id))
        result = await handler.handle(query)
        assert result.id == agent.id

    @pytest.mark.asyncio
    async def test_get_agent_not_found_raises(self) -> None:
        repo = _mock_repository()
        repo.get_by_id.return_value = None
        handler = GetAgentHandler(repo)
        query = GetAgentQuery(agent_id=str(UUIDv7()))
        with pytest.raises(NotFoundError, match="Agent not found"):
            await handler.handle(query)


class TestListAgentsHandler:
    """Tests for ListAgentsHandler."""

    @pytest.mark.asyncio
    async def test_list_agents_success(self) -> None:
        repo = _mock_repository()
        paginated = PaginatedAgents(
            items=[_make_agent()],
            total=1,
            page=1,
            page_size=20,
        )
        repo.list.return_value = paginated
        handler = ListAgentsHandler(repo)
        query = ListAgentsQuery(project_id="proj-001")
        result = await handler.handle(query)
        assert result.total == 1
        assert len(result.items) == 1
        repo.list.assert_awaited_once()
