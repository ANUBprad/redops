"""Domain contracts for the Evaluation engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.domain.entities.evaluation_definition import Evaluation
    from app.evaluation.domain.entities.evaluation_entities import (
        EvaluationItem,
        EvaluationRun,
        RunCheckpoint,
    )
    from app.evaluation.domain.enums.evaluation_enums import (
        EvaluationStatus,
        RunStatus,
    )
    from app.kernel.entities.base import UUIDv7


@dataclass
class EvaluationQuery:
    """Query parameters for listing evaluations."""

    project_id: str | None = None
    provider: str | None = None
    model: str | None = None
    status: EvaluationStatus | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PaginatedEvaluations:
    """Paginated result for evaluation listing."""

    items: list[Evaluation] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)


class EvaluationRepository(ABC):
    """Repository for evaluation definition persistence."""

    @abstractmethod
    async def create(self, evaluation: Evaluation) -> None:
        """Persist a new evaluation definition."""
        ...

    @abstractmethod
    async def update(self, evaluation: Evaluation) -> None:
        """Update an existing evaluation definition."""
        ...

    @abstractmethod
    async def delete(self, evaluation_id: UUIDv7) -> bool:
        """Delete an evaluation definition by ID."""
        ...

    @abstractmethod
    async def get_by_id(self, evaluation_id: UUIDv7) -> Evaluation | None:
        """Find an evaluation by its ID."""
        ...

    @abstractmethod
    async def list(self, query: EvaluationQuery) -> PaginatedEvaluations:
        """List evaluations with filtering, sorting, and pagination."""
        ...

    @abstractmethod
    async def exists(self, evaluation_id: UUIDv7) -> bool:
        """Check whether an evaluation exists."""
        ...

    @abstractmethod
    async def exists_by_name_in_project(
        self,
        project_id: str,
        name: str,
        exclude_id: UUIDv7 | None = None,
    ) -> bool:
        """Check whether an evaluation with the given name exists in a project."""
        ...


class RunRepository(ABC):
    """Repository for evaluation run persistence."""

    @abstractmethod
    async def save(self, run: EvaluationRun) -> None:
        """Save an evaluation run."""
        ...

    @abstractmethod
    async def find_by_id(self, run_id: UUIDv7) -> EvaluationRun | None:
        """Find a run by its ID."""
        ...

    @abstractmethod
    async def find_by_status(
        self,
        status: RunStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvaluationRun]:
        """Find runs by status."""
        ...

    @abstractmethod
    async def delete(self, run_id: UUIDv7) -> bool:
        """Delete a run by ID."""
        ...


class ItemRepository(ABC):
    """Repository for evaluation item persistence."""

    @abstractmethod
    async def save_many(self, items: Sequence[EvaluationItem]) -> None:
        """Save multiple items in batch."""
        ...

    @abstractmethod
    async def find_by_run_id(
        self,
        run_id: UUIDv7,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[EvaluationItem]:
        """Find items by run ID."""
        ...

    @abstractmethod
    async def find_pending_by_run_id(self, run_id: UUIDv7) -> list[EvaluationItem]:
        """Find pending items for a run."""
        ...


class CheckpointRepository(ABC):
    """Repository for checkpoint persistence."""

    @abstractmethod
    async def save(self, checkpoint: RunCheckpoint) -> None:
        """Save a checkpoint."""
        ...

    @abstractmethod
    async def find_latest(self, run_id: UUIDv7) -> RunCheckpoint | None:
        """Find the latest checkpoint for a run."""
        ...

    @abstractmethod
    async def find_by_number(
        self,
        run_id: UUIDv7,
        checkpoint_number: int,
    ) -> RunCheckpoint | None:
        """Find a specific checkpoint by number."""
        ...

    @abstractmethod
    async def prune(self, run_id: UUIDv7, keep_latest: int = 5) -> int:
        """Prune old checkpoints for a run."""
        ...


class EventPublisher(ABC):
    """Publisher for domain events."""

    @abstractmethod
    async def publish(self, event: object) -> None:
        """Publish a domain event."""
        ...

    @abstractmethod
    async def publish_many(self, events: Sequence[object]) -> None:
        """Publish multiple domain events."""
        ...
