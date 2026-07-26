"""Domain contracts for the Evaluation engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.domain.entities.evaluation_entities import (
        EvaluationItem,
        EvaluationRun,
        RunCheckpoint,
    )
    from app.evaluation.domain.enums.evaluation_enums import RunStatus
    from app.kernel.entities.base import UUIDv7


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
