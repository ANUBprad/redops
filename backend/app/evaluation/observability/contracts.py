"""Repository contracts for run observability."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.observability.domain import RunLogEntry, TimelineEntry
    from app.kernel.entities.base import UUIDv7


class TimelineRepository(ABC):
    @abstractmethod
    async def save(self, entry: TimelineEntry) -> None: ...

    @abstractmethod
    async def find_by_run_id(
        self,
        run_id: UUIDv7,
        *,
        event_type: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[TimelineEntry]: ...

    @abstractmethod
    async def count_by_run_id(self, run_id: UUIDv7) -> int: ...


class RunLogRepository(ABC):
    @abstractmethod
    async def save(self, entry: RunLogEntry) -> None: ...

    @abstractmethod
    async def find_by_run_id(
        self,
        run_id: UUIDv7,
        *,
        level: str | None = None,
        source: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[RunLogEntry]: ...

    @abstractmethod
    async def count_by_run_id(
        self,
        run_id: UUIDv7,
        *,
        level: str | None = None,
    ) -> int: ...
