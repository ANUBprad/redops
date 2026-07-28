"""In-memory repository implementations for testing.

Provides lightweight, non-persistent implementations of the
domain repository contracts for unit and integration testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.domain.contracts.evaluation_contracts import (
    CheckpointRepository,
    EventPublisher,
    ItemRepository,
    RunRepository,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.domain.entities.evaluation_entities import (
        EvaluationItem,
        EvaluationRun,
        RunCheckpoint,
    )
    from app.evaluation.domain.enums.evaluation_enums import RunStatus
    from app.kernel.entities.base import UUIDv7


class InMemoryRunRepository(RunRepository):
    """In-memory implementation of RunRepository for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._runs: dict[str, EvaluationRun] = {}

    async def save(self, run: EvaluationRun) -> None:
        """Save a run to in-memory storage."""
        self._runs[str(run.id)] = run

    async def find_by_id(self, run_id: UUIDv7) -> EvaluationRun | None:
        """Find a run by ID."""
        return self._runs.get(str(run_id))

    async def find_by_status(
        self,
        status: RunStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvaluationRun]:
        """Find runs by status with pagination."""
        matching = [r for r in self._runs.values() if r.status == status]
        return matching[offset : offset + limit]

    async def delete(self, run_id: UUIDv7) -> bool:
        """Delete a run by ID."""
        key = str(run_id)
        if key in self._runs:
            del self._runs[key]
            return True
        return False


class InMemoryItemRepository(ItemRepository):
    """In-memory implementation of ItemRepository for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._items: dict[str, EvaluationItem] = {}

    async def save_many(self, items: Sequence[EvaluationItem]) -> None:
        """Save multiple items to in-memory storage."""
        for item in items:
            self._items[str(item.id)] = item

    async def find_by_run_id(
        self,
        run_id: UUIDv7,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[EvaluationItem]:
        """Find items by run ID."""
        matching = [i for i in self._items.values() if i.run_id == run_id]
        return matching[offset : offset + limit]

    async def find_pending_by_run_id(self, run_id: UUIDv7) -> list[EvaluationItem]:
        """Find pending items for a run."""
        return [
            i for i in self._items.values() if i.run_id == run_id and i.status.value == "pending"
        ]


class InMemoryCheckpointRepository(CheckpointRepository):
    """In-memory implementation of CheckpointRepository for testing."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._checkpoints: dict[str, list[RunCheckpoint]] = {}

    async def save(self, checkpoint: RunCheckpoint) -> None:
        """Save a checkpoint to in-memory storage."""
        key = str(checkpoint.run_id)
        if key not in self._checkpoints:
            self._checkpoints[key] = []
        self._checkpoints[key].append(checkpoint)

    async def find_latest(self, run_id: UUIDv7) -> RunCheckpoint | None:
        """Find the latest checkpoint for a run."""
        key = str(run_id)
        checkpoints = self._checkpoints.get(key, [])
        if not checkpoints:
            return None
        return max(checkpoints, key=lambda c: c.checkpoint_number)

    async def find_by_number(
        self,
        run_id: UUIDv7,
        checkpoint_number: int,
    ) -> RunCheckpoint | None:
        """Find a specific checkpoint by number."""
        key = str(run_id)
        for cp in self._checkpoints.get(key, []):
            if cp.checkpoint_number == checkpoint_number:
                return cp
        return None

    async def prune(self, run_id: UUIDv7, keep_latest: int = 5) -> int:
        """Prune old checkpoints for a run."""
        key = str(run_id)
        checkpoints = self._checkpoints.get(key, [])
        if len(checkpoints) <= keep_latest:
            return 0

        sorted_cps = sorted(checkpoints, key=lambda c: c.checkpoint_number)
        to_remove = sorted_cps[:-keep_latest]
        self._checkpoints[key] = sorted_cps[-keep_latest:]
        return len(to_remove)


class InMemoryEventPublisher(EventPublisher):
    """In-memory implementation of EventPublisher for testing."""

    def __init__(self) -> None:
        """Initialize with empty event list."""
        self._events: list[object] = []

    async def publish(self, event: object) -> None:
        """Store a published event."""
        self._events.append(event)

    async def publish_many(self, events: Sequence[object]) -> None:
        """Store multiple published events."""
        self._events.extend(events)

    def get_events(self) -> list[object]:
        """Return all published events."""
        return list(self._events)

    def clear_events(self) -> None:
        """Clear all stored events."""
        self._events.clear()
