"""Domain contracts for the Agent Registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.domain.entities.agent_definition import AgentDefinition
    from app.agent.domain.enums.agent_enums import AgentStatus, AgentType
    from app.kernel.entities.base import UUIDv7


@dataclass
class AgentQuery:
    """Query parameters for listing agent definitions."""

    project_id: str | None = None
    agent_type: AgentType | None = None
    status: AgentStatus | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PaginatedAgents:
    """Paginated result for agent definition listing."""

    items: list[AgentDefinition] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)


class AgentDefinitionRepository(ABC):
    """Repository for agent definition persistence."""

    @abstractmethod
    async def create(self, agent: AgentDefinition) -> None:
        """Persist a new agent definition."""
        ...

    @abstractmethod
    async def update(self, agent: AgentDefinition) -> None:
        """Update an existing agent definition."""
        ...

    @abstractmethod
    async def delete(self, agent_id: UUIDv7) -> bool:
        """Delete an agent definition by ID."""
        ...

    @abstractmethod
    async def get_by_id(self, agent_id: UUIDv7) -> AgentDefinition | None:
        """Find an agent by its ID."""
        ...

    @abstractmethod
    async def list(self, query: AgentQuery) -> PaginatedAgents:
        """List agents with filtering, sorting, and pagination."""
        ...

    @abstractmethod
    async def exists(self, agent_id: UUIDv7) -> bool:
        """Check whether an agent exists."""
        ...

    @abstractmethod
    async def exists_by_name_in_project(
        self,
        project_id: str,
        name: str,
        exclude_id: UUIDv7 | None = None,
    ) -> bool:
        """Check whether an agent with the given name exists in a project."""
        ...
