"""SQLAlchemy repository for run timeline events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.evaluation.observability.contracts import TimelineRepository
from app.evaluation.observability.domain import TimelineEntry
from app.infrastructure.database.models.run_event import RunEventModel
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyRunEventRepository(TimelineRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entry: TimelineEntry) -> None:
        model = RunEventModel(
            id=str(entry.entry_id),
            run_id=str(entry.run_id),
            event_type=entry.event_type,
            data=entry.data,
            correlation_id=entry.correlation_id,
            occurred_at=entry.occurred_at,
        )
        self._session.add(model)

    async def find_by_run_id(
        self,
        run_id: UUIDv7,
        *,
        event_type: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[TimelineEntry]:
        stmt = (
            select(RunEventModel)
            .where(RunEventModel.run_id == str(run_id))
            .order_by(RunEventModel.occurred_at)
            .offset(offset)
            .limit(limit)
        )
        if event_type:
            stmt = stmt.where(RunEventModel.event_type == event_type)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def count_by_run_id(self, run_id: UUIDv7) -> int:
        stmt = (
            select(func.count())
            .select_from(RunEventModel)
            .where(RunEventModel.run_id == str(run_id))
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    def _to_domain(model: RunEventModel) -> TimelineEntry:
        return TimelineEntry(
            entry_id=UUIDv7.from_string(model.id),
            run_id=UUIDv7.from_string(model.run_id),
            event_type=model.event_type,
            data=dict(model.data or {}),
            correlation_id=model.correlation_id,
            occurred_at=model.occurred_at,
        )
