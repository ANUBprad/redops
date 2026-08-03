"""Repository contract for Schedules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.kernel.entities.base import UUIDv7
    from app.scheduling.domain import Schedule, ScheduleStatus


class ScheduleRepository(ABC):
    """Abstract repository for Schedule aggregates."""

    @abstractmethod
    async def save(self, schedule: Schedule) -> None:
        """Persist a schedule."""

    @abstractmethod
    async def find_by_id(self, schedule_id: UUIDv7) -> Schedule | None:
        """Find a schedule by ID."""

    @abstractmethod
    async def list_by_status(
        self,
        status: ScheduleStatus,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Schedule]:
        """List schedules by status."""

    @abstractmethod
    async def list_by_organization(self, org_id: str) -> list[Schedule]:
        """List schedules for an organization."""

    @abstractmethod
    async def delete(self, schedule_id: UUIDv7) -> bool:
        """Delete a schedule."""
