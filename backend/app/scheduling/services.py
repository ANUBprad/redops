"""Scheduling service."""

from __future__ import annotations

from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import NotFoundError
from app.scheduling.contracts import ScheduleRepository
from app.scheduling.domain import Schedule, ScheduleStatus


class ScheduleService:
    """Service for schedule operations."""

    def __init__(self, repo: ScheduleRepository) -> None:
        self._repo = repo

    async def create_schedule(
        self,
        *,
        name: str,
        schedule_type: str,
        cron_expression: str,
        task_config: dict[str, object] | None = None,
        organization_id: str | None = None,
        project_id: str | None = None,
        created_by: str | None = None,
        timezone: str = "UTC",
    ) -> Schedule:
        from app.scheduling.domain import ScheduleType

        schedule = Schedule.create(
            name=name,
            schedule_type=ScheduleType(schedule_type),
            cron_expression=cron_expression,
            task_config=task_config,
            organization_id=organization_id,
            project_id=project_id,
            created_by=created_by,
            timezone=timezone,
        )
        await self._repo.save(schedule)
        return schedule

    async def get_schedule(self, schedule_id: str) -> Schedule:
        schedule = await self._repo.find_by_id(UUIDv7.from_string(schedule_id))
        if schedule is None:
            raise NotFoundError(
                message="Schedule not found",
                resource_type="Schedule",
                resource_id=schedule_id,
            )
        return schedule

    async def pause_schedule(self, schedule_id: str) -> Schedule:
        schedule = await self.get_schedule(schedule_id)
        schedule.pause()
        await self._repo.save(schedule)
        return schedule

    async def resume_schedule(self, schedule_id: str) -> Schedule:
        schedule = await self.get_schedule(schedule_id)
        schedule.resume()
        await self._repo.save(schedule)
        return schedule

    async def record_run(self, schedule_id: str, success: bool) -> Schedule:
        schedule = await self.get_schedule(schedule_id)
        schedule.record_run(success)
        await self._repo.save(schedule)
        return schedule

    async def list_active_schedules(self) -> list[Schedule]:
        return await self._repo.list_by_status(ScheduleStatus.ACTIVE)

    async def list_schedules_by_org(self, org_id: str) -> list[Schedule]:
        return await self._repo.list_by_organization(org_id)

    async def delete_schedule(self, schedule_id: str) -> bool:
        schedule_id_uuid = UUIDv7.from_string(schedule_id)
        schedule = await self._repo.find_by_id(schedule_id_uuid)
        if schedule is None:
            raise NotFoundError(
                message="Schedule not found",
                resource_type="Schedule",
                resource_id=schedule_id,
            )
        return await self._repo.delete(schedule_id_uuid)
