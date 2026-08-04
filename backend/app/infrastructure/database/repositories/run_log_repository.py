"""SQLAlchemy repository for structured run logs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.evaluation.observability.contracts import RunLogRepository
from app.evaluation.observability.domain import RunLogEntry
from app.infrastructure.database.models.run_log import RunLogModel
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyRunLogRepository(RunLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entry: RunLogEntry) -> None:
        model = RunLogModel(
            run_id=str(entry.run_id),
            log_id=str(entry.log_id),
            level=entry.level,
            source=entry.source,
            message=entry.message,
            metadata=entry.metadata,
            correlation_id=entry.correlation_id,
            timestamp=entry.timestamp,
        )
        self._session.add(model)

    async def find_by_run_id(
        self,
        run_id: UUIDv7,
        *,
        level: str | None = None,
        source: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[RunLogEntry]:
        stmt = (
            select(RunLogModel)
            .where(RunLogModel.run_id == str(run_id))
            .order_by(RunLogModel.timestamp)
            .offset(offset)
            .limit(limit)
        )
        if level:
            stmt = stmt.where(RunLogModel.level == level.upper())
        if source:
            stmt = stmt.where(RunLogModel.source == source)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def count_by_run_id(
        self,
        run_id: UUIDv7,
        *,
        level: str | None = None,
    ) -> int:
        stmt = (
            select(func.count()).select_from(RunLogModel).where(RunLogModel.run_id == str(run_id))
        )
        if level:
            stmt = stmt.where(RunLogModel.level == level.upper())

        result = await self._session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    def _to_domain(model: RunLogModel) -> RunLogEntry:
        return RunLogEntry(
            log_id=UUIDv7.from_string(model.log_id),
            run_id=UUIDv7.from_string(model.run_id),
            level=model.level,
            source=model.source,
            message=model.message,
            metadata=dict(model.metadata_json or {}),
            correlation_id=model.correlation_id,
            timestamp=model.timestamp,
        )
