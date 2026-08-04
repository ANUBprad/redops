"""Command and query handlers for agent management."""

from __future__ import annotations

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
from app.agent.domain.contracts.agent_contracts import (
    AgentDefinitionRepository,
    AgentQuery,
    PaginatedAgents,
)
from app.agent.domain.entities.agent_definition import AgentDefinition
from app.agent.domain.enums.agent_enums import AgentStatus, AgentType
from app.agent.domain.value_objects.agent_vos import (
    AgentDescription,
    AgentEndpoint,
    AgentName,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, ValidationError


class CreateAgentHandler:
    """Handler for creating agent definitions."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: CreateAgentCommand) -> AgentDefinition:
        """Execute the create agent command.

        Args:
            command: The create command.

        Returns:
            The created AgentDefinition aggregate.

        Raises:
            ValidationError: If required fields are missing.
            ConflictError: If name already exists in the project.

        """
        name = AgentName(value=command.name)

        if not command.model:
            raise ValidationError(message="Model is required", field="model")
        if not command.provider:
            raise ValidationError(message="Provider is required", field="provider")

        # Check name uniqueness within project
        exists = await self._repository.exists_by_name_in_project(
            project_id=command.project_id,
            name=str(name.value),
        )
        if exists:
            raise ConflictError(
                message=f"Agent with name '{name.value}' already exists in project",
                details={"project_id": command.project_id, "name": str(name.value)},
            )

        agent = AgentDefinition.create(
            project_id=command.project_id,
            name=name,
            description=AgentDescription(value=command.description)
            if command.description is not None
            else None,
            agent_type=AgentType(command.agent_type),
            model=command.model,
            provider=command.provider,
            capabilities=command.capabilities,
            config=command.config,
            endpoint=AgentEndpoint(value=command.endpoint)
            if command.endpoint is not None
            else None,
            created_by=command.created_by,
        )

        await self._repository.create(agent)
        return agent


class UpdateAgentHandler:
    """Handler for updating agent definitions."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: UpdateAgentCommand) -> AgentDefinition:
        """Execute the update agent command.

        Args:
            command: The update command.

        Returns:
            The updated AgentDefinition aggregate.

        Raises:
            NotFoundError: If agent not found.
            ConflictError: If name conflicts with another in the project.

        """
        agent = await self._get_agent(command.agent_id)

        # Check name uniqueness if name is being changed
        if command.name is not None:
            new_name = AgentName(value=command.name)
            exists = await self._repository.exists_by_name_in_project(
                project_id=agent.project_id,
                name=str(new_name.value),
                exclude_id=agent.id,
            )
            if exists:
                raise ConflictError(
                    message=f"Agent with name '{new_name.value}' already exists",
                    details={"name": str(new_name.value)},
                )

        agent.update(
            name=AgentName(value=command.name) if command.name is not None else None,
            description=AgentDescription(value=command.description)
            if command.description is not None
            else None,
            agent_type=AgentType(command.agent_type) if command.agent_type is not None else None,
            model=command.model,
            provider=command.provider,
            capabilities=command.capabilities,
            config=command.config,
            endpoint=AgentEndpoint(value=command.endpoint)
            if command.endpoint is not None
            else None,
        )

        await self._repository.update(agent)
        return agent

    async def _get_agent(self, agent_id: str) -> AgentDefinition:
        """Retrieve agent or raise NotFoundError."""
        a_id = UUIDv7.from_string(agent_id)
        agent = await self._repository.get_by_id(a_id)
        if agent is None:
            raise NotFoundError(
                message=f"Agent not found: {agent_id}",
                resource_type="Agent",
                resource_id=agent_id,
            )
        return agent


class DeleteAgentHandler:
    """Handler for deleting agent definitions."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: DeleteAgentCommand) -> None:
        """Execute the delete agent command.

        Args:
            command: The delete command.

        Raises:
            NotFoundError: If agent not found.

        """
        a_id = UUIDv7.from_string(command.agent_id)
        agent = await self._repository.get_by_id(a_id)
        if agent is None:
            raise NotFoundError(
                message=f"Agent not found: {command.agent_id}",
                resource_type="Agent",
                resource_id=command.agent_id,
            )
        agent.delete()
        await self._repository.delete(a_id)


class ActivateAgentHandler:
    """Handler for activating agent definitions."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: ActivateAgentCommand) -> AgentDefinition:
        """Execute the activate agent command.

        Args:
            command: The activate command.

        Returns:
            The activated AgentDefinition aggregate.

        Raises:
            NotFoundError: If agent not found.

        """
        a_id = UUIDv7.from_string(command.agent_id)
        agent = await self._repository.get_by_id(a_id)
        if agent is None:
            raise NotFoundError(
                message=f"Agent not found: {command.agent_id}",
                resource_type="Agent",
                resource_id=command.agent_id,
            )
        agent.activate()
        await self._repository.update(agent)
        return agent


class DeactivateAgentHandler:
    """Handler for deactivating agent definitions."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: DeactivateAgentCommand) -> AgentDefinition:
        """Execute the deactivate agent command.

        Args:
            command: The deactivate command.

        Returns:
            The deactivated AgentDefinition aggregate.

        Raises:
            NotFoundError: If agent not found.

        """
        a_id = UUIDv7.from_string(command.agent_id)
        agent = await self._repository.get_by_id(a_id)
        if agent is None:
            raise NotFoundError(
                message=f"Agent not found: {command.agent_id}",
                resource_type="Agent",
                resource_id=command.agent_id,
            )
        agent.deactivate()
        await self._repository.update(agent)
        return agent


class ArchiveAgentHandler:
    """Handler for archiving agent definitions."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: ArchiveAgentCommand) -> AgentDefinition:
        """Execute the archive agent command.

        Args:
            command: The archive command.

        Returns:
            The archived AgentDefinition aggregate.

        Raises:
            NotFoundError: If agent not found.

        """
        a_id = UUIDv7.from_string(command.agent_id)
        agent = await self._repository.get_by_id(a_id)
        if agent is None:
            raise NotFoundError(
                message=f"Agent not found: {command.agent_id}",
                resource_type="Agent",
                resource_id=command.agent_id,
            )
        agent.archive()
        await self._repository.update(agent)
        return agent


class GetAgentHandler:
    """Handler for getting a single agent."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, query: GetAgentQuery) -> AgentDefinition:
        """Execute the get agent query.

        Args:
            query: The get query.

        Returns:
            The AgentDefinition aggregate.

        Raises:
            NotFoundError: If agent not found.

        """
        a_id = UUIDv7.from_string(query.agent_id)
        agent = await self._repository.get_by_id(a_id)
        if agent is None:
            raise NotFoundError(
                message=f"Agent not found: {query.agent_id}",
                resource_type="Agent",
                resource_id=query.agent_id,
            )
        return agent


class ListAgentsHandler:
    """Handler for listing agents."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, query: ListAgentsQuery) -> PaginatedAgents:
        """Execute the list agents query.

        Args:
            query: The list query.

        Returns:
            Paginated list of agents.

        """
        status = None
        if query.status is not None:
            status = AgentStatus(query.status)

        agent_type = None
        if query.agent_type is not None:
            agent_type = AgentType(query.agent_type)

        repo_query = AgentQuery(
            project_id=query.project_id,
            agent_type=agent_type,
            status=status,
            search=query.search,
            sort_by=query.sort_by,
            sort_order=query.sort_order,
            page=query.page,
            page_size=query.page_size,
        )
        return await self._repository.list(repo_query)
