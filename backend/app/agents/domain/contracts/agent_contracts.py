"""Domain contracts for the Agent Runtime engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.domain.entities.agent_entities import AgentRun
    from app.agents.domain.enums.agent_enums import AgentRunStatus
    from app.agents.domain.value_objects.agent_value_objects import AgentCheckpoint
    from app.kernel.entities.base import UUIDv7


@dataclass
class AgentRunQuery:
    """Query parameters for listing agent runs."""

    agent_name: str | None = None
    status: AgentRunStatus | None = None
    provider: str | None = None
    model: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PaginatedAgentRuns:
    """Paginated result for agent run listing."""

    items: list[AgentRun] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)


class AgentRunRepository(ABC):
    """Repository for agent run persistence."""

    @abstractmethod
    async def save(self, run: AgentRun) -> None:
        """Save an agent run."""
        ...

    @abstractmethod
    async def find_by_id(self, run_id: UUIDv7) -> AgentRun | None:
        """Find a run by its ID."""
        ...

    @abstractmethod
    async def find_by_status(
        self,
        status: AgentRunStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentRun]:
        """Find runs by status."""
        ...

    @abstractmethod
    async def list(self, query: AgentRunQuery) -> PaginatedAgentRuns:
        """List runs with filtering, sorting, and pagination."""
        ...

    @abstractmethod
    async def exists(self, run_id: UUIDv7) -> bool:
        """Check whether a run exists."""
        ...

    @abstractmethod
    async def delete(self, run_id: UUIDv7) -> bool:
        """Delete a run by ID."""
        ...

    @abstractmethod
    async def persist_progress(self, run: AgentRun) -> None:
        """Persist progress-only updates (counters, tokens, cost)."""
        ...


class AgentCheckpointRepository(ABC):
    """Repository for agent checkpoint persistence."""

    @abstractmethod
    async def save(self, checkpoint: AgentCheckpoint) -> None:
        """Save a checkpoint."""
        ...

    @abstractmethod
    async def find_latest(self, run_id: UUIDv7) -> AgentCheckpoint | None:
        """Find the latest checkpoint for a run."""
        ...

    @abstractmethod
    async def find_by_number(
        self,
        run_id: UUIDv7,
        checkpoint_number: int,
    ) -> AgentCheckpoint | None:
        """Find a specific checkpoint by number."""
        ...

    @abstractmethod
    async def prune(self, run_id: UUIDv7, keep_latest: int = 5) -> int:
        """Prune old checkpoints for a run."""
        ...


class AgentEventPublisher(ABC):
    """Publisher for agent domain events."""

    @abstractmethod
    async def publish(self, event: object) -> None:
        """Publish a domain event."""
        ...

    @abstractmethod
    async def publish_many(self, events: list[object]) -> None:
        """Publish multiple domain events."""
        ...
