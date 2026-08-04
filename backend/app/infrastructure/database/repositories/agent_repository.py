"""SQLAlchemy repository for Agent definitions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

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
from app.infrastructure.database.models.agent_definition import AgentDefinitionModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass


class SqlAlchemyAgentDefinitionRepository(AgentDefinitionRepository):
    """SQLAlchemy implementation of the AgentDefinitionRepository contract.

    Maps between the domain AgentDefinition aggregate and the
    AgentDefinitionModel ORM representation.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session."""
        self._session = session

    async def create(self, agent: AgentDefinition) -> None:
        """Persist a new agent definition.

        Args:
            agent: The agent aggregate to persist.

        Raises:
            ConflictError: If a unique constraint is violated.

        """
        model = self._to_model(agent)
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                message=f"Agent with name '{agent.name.value}' already exists in project",
                details={
                    "project_id": agent.project_id,
                    "name": agent.name.value,
                },
            ) from exc

    async def update(self, agent: AgentDefinition) -> None:
        """Update an existing agent definition.

        Args:
            agent: The agent aggregate with updated values.

        """
        model = self._to_model(agent)
        await self._session.merge(model)

    async def delete(self, agent_id: UUIDv7) -> bool:
        """Delete an agent definition by ID.

        Args:
            agent_id: The UUIDv7 identifier of the agent.

        Returns:
            True if deleted, False if not found.

        """
        stmt = select(AgentDefinitionModel).where(
            AgentDefinitionModel.id == str(agent_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    async def get_by_id(self, agent_id: UUIDv7) -> AgentDefinition | None:
        """Find an agent by its ID.

        Args:
            agent_id: The UUIDv7 identifier.

        Returns:
            The AgentDefinition aggregate if found, None otherwise.

        """
        stmt = select(AgentDefinitionModel).where(
            AgentDefinitionModel.id == str(agent_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list(self, query: AgentQuery) -> PaginatedAgents:
        """List agents with filtering, sorting, and pagination.

        Args:
            query: Query parameters for filtering and pagination.

        Returns:
            Paginated list of agents.

        """
        stmt = select(AgentDefinitionModel)
        count_stmt = select(func.count()).select_from(AgentDefinitionModel)

        # Apply filters
        if query.project_id is not None:
            stmt = stmt.where(AgentDefinitionModel.project_id == query.project_id)
            count_stmt = count_stmt.where(
                AgentDefinitionModel.project_id == query.project_id,
            )
        if query.agent_type is not None:
            stmt = stmt.where(AgentDefinitionModel.agent_type == query.agent_type.value)
            count_stmt = count_stmt.where(
                AgentDefinitionModel.agent_type == query.agent_type.value,
            )
        if query.status is not None:
            stmt = stmt.where(AgentDefinitionModel.status == query.status.value)
            count_stmt = count_stmt.where(
                AgentDefinitionModel.status == query.status.value,
            )
        if query.search is not None:
            search_pattern = f"%{query.search}%"
            search_filter = AgentDefinitionModel.name.ilike(
                search_pattern,
            ) | AgentDefinitionModel.description.ilike(search_pattern)
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Get total count
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        # Apply sorting
        sort_column = _get_sort_column(query.sort_by)
        if query.sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        # Apply pagination
        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        # Execute
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        return PaginatedAgents(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def exists(self, agent_id: UUIDv7) -> bool:
        """Check whether an agent exists.

        Args:
            agent_id: The UUIDv7 identifier.

        Returns:
            True if the agent exists, False otherwise.

        """
        stmt = select(AgentDefinitionModel.id).where(
            AgentDefinitionModel.id == str(agent_id),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists_by_name_in_project(
        self,
        project_id: str,
        name: str,
        exclude_id: UUIDv7 | None = None,
    ) -> bool:
        """Check whether an agent with the given name exists in a project.

        Args:
            project_id: The project identifier.
            name: The agent name to check.
            exclude_id: Optional ID to exclude from the check.

        Returns:
            True if a conflicting name exists, False otherwise.

        """
        stmt = select(AgentDefinitionModel.id).where(
            AgentDefinitionModel.project_id == project_id,
            AgentDefinitionModel.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(AgentDefinitionModel.id != str(exclude_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _to_model(agent: AgentDefinition) -> AgentDefinitionModel:
        """Convert a domain AgentDefinition to an ORM model.

        Args:
            agent: The domain aggregate.

        Returns:
            The corresponding ORM model.

        """
        return AgentDefinitionModel(
            id=str(agent.id),
            project_id=agent.project_id,
            name=str(agent.name.value),
            description=agent.description.value if agent.description is not None else None,
            agent_type=agent.agent_type.value,
            model=agent.model,
            provider=agent.provider,
            capabilities=list(agent.capabilities),
            config=dict(agent.config),
            endpoint=agent.endpoint.value if agent.endpoint is not None else None,
            status=agent.status.value,
            created_by=agent.created_by,
            version=agent.version,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )

    @staticmethod
    def _to_domain(model: AgentDefinitionModel) -> AgentDefinition:
        """Convert an ORM model to a domain AgentDefinition.

        Args:
            model: The ORM model.

        Returns:
            The corresponding domain aggregate.

        """
        return AgentDefinition(
            entity_id=UUIDv7.from_string(model.id),
            project_id=model.project_id,
            name=AgentName(value=model.name),
            description=AgentDescription(value=model.description)
            if model.description is not None
            else None,
            agent_type=AgentType(model.agent_type),
            model=model.model,
            provider=model.provider,
            capabilities=tuple(model.capabilities),
            config=model.config,
            endpoint=AgentEndpoint(value=model.endpoint) if model.endpoint is not None else None,
            status=AgentStatus(model.status),
            created_by=model.created_by,
        )


def _get_sort_column(sort_by: str) -> Any:
    """Map a sort field name to the corresponding ORM column.

    Args:
        sort_by: The field name to sort by.

    Returns:
        The corresponding SQLAlchemy column.

    """
    columns: dict[str, Any] = {
        "created_at": AgentDefinitionModel.created_at,
        "updated_at": AgentDefinitionModel.updated_at,
        "name": AgentDefinitionModel.name,
    }
    return columns.get(sort_by, AgentDefinitionModel.created_at)
