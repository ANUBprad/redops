"""SQLAlchemy repository implementation for Schedules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.infrastructure.database.models.schedule import ScheduleModel
from app.kernel.entities.base import UUIDv7
from app.scheduling.contracts import ScheduleRepository
from app.scheduling.domain import (
    ConcurrencyConfig,
    RetryPolicy,
    RetryStrategy,
    Schedule,
    ScheduleStatus,
    ScheduleType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyScheduleRepository(ScheduleRepository):
    """SQLAlchemy implementation of ScheduleRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, schedule: Schedule) -> None:
        model = ScheduleModel(
            id=str(schedule.id),
            name=schedule.name,
            schedule_type=schedule.schedule_type.value,
            cron_expression=schedule.cron_expression,
            task_config=schedule.task_config,
            organization_id=schedule.organization_id,
            project_id=schedule.project_id,
            created_by=schedule.created_by,
            retry_policy={
                "max_retries": schedule.retry_policy.max_retries,
                "strategy": schedule.retry_policy.strategy.value,
                "base_delay_seconds": schedule.retry_policy.base_delay_seconds,
                "max_delay_seconds": schedule.retry_policy.max_delay_seconds,
            },
            concurrency={
                "max_concurrent": schedule.concurrency.max_concurrent,
                "queue_size": schedule.concurrency.queue_size,
                "timeout_seconds": schedule.concurrency.timeout_seconds,
            },
            timezone=schedule.timezone,
            status=schedule.status.value,
            last_run_at=schedule.last_run_at,
            next_run_at=schedule.next_run_at,
            run_count=schedule.run_count,
            failure_count=schedule.failure_count,
            version=schedule.version,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )
        self._session.add(model)

    async def find_by_id(self, schedule_id: UUIDv7) -> Schedule | None:
        stmt = select(ScheduleModel).where(ScheduleModel.id == str(schedule_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_status(
        self,
        status: ScheduleStatus,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Schedule]:
        stmt = (
            select(ScheduleModel)
            .where(ScheduleModel.status == status.value)
            .order_by(ScheduleModel.next_run_at.asc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def list_by_organization(self, org_id: str) -> list[Schedule]:
        stmt = (
            select(ScheduleModel)
            .where(ScheduleModel.organization_id == org_id)
            .order_by(ScheduleModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def delete(self, schedule_id: UUIDv7) -> bool:
        stmt = select(ScheduleModel).where(ScheduleModel.id == str(schedule_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    @staticmethod
    def _to_domain(model: ScheduleModel) -> Schedule:
        rp = model.retry_policy
        cc = model.concurrency
        max_retries = int(rp.get("max_retries", 3))  # type: ignore[call-overload]
        strategy_str = str(rp.get("strategy", "exponential"))
        base_delay = int(rp.get("base_delay_seconds", 60))  # type: ignore[call-overload]
        max_delay = int(rp.get("max_delay_seconds", 3600))  # type: ignore[call-overload]
        max_concurrent = int(cc.get("max_concurrent", 1))  # type: ignore[call-overload]
        queue_size = int(cc.get("queue_size", 10))  # type: ignore[call-overload]
        timeout = int(cc.get("timeout_seconds", 3600))  # type: ignore[call-overload]
        return Schedule(
            entity_id=UUIDv7.from_string(model.id),
            name=model.name,
            schedule_type=ScheduleType(model.schedule_type),
            cron_expression=model.cron_expression,
            task_config=model.task_config,
            organization_id=model.organization_id,
            project_id=model.project_id,
            created_by=model.created_by,
            retry_policy=RetryPolicy(
                max_retries=max_retries,
                strategy=RetryStrategy(strategy_str),
                base_delay_seconds=base_delay,
                max_delay_seconds=max_delay,
            ),
            concurrency=ConcurrencyConfig(
                max_concurrent=max_concurrent,
                queue_size=queue_size,
                timeout_seconds=timeout,
            ),
            timezone=model.timezone,
            status=ScheduleStatus(model.status),
            last_run_at=model.last_run_at,
            next_run_at=model.next_run_at,
            run_count=model.run_count,
            failure_count=model.failure_count,
        )
