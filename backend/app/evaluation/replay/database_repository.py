"""Database-backed trace repository for evaluation runs.

Reads trace data from the evaluation_runs.trace_data JSON column,
closing the gap between the evaluation workflow's trace persistence
and the replay API's trace loading.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.evaluation.replay.contracts import TraceRepository
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)


class DatabaseTraceRepository(TraceRepository):
    """SQLAlchemy-backed execution trace storage.

    Reads from the evaluation_runs.trace_data JSON column.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        stmt = select(EvaluationRunModel.trace_data).where(
            EvaluationRunModel.id == run_id,
        )
        result = await self._session.execute(stmt)
        trace_data = result.scalar_one_or_none()
        if trace_data is None:
            return None
        if not isinstance(trace_data, dict):
            logger.warning("Trace data for run %s is not a dict", run_id)
            return None
        return trace_data

    async def save(self, run_id: str, trace_data: dict[str, Any]) -> None:
        stmt = select(EvaluationRunModel).where(
            EvaluationRunModel.id == run_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            logger.warning("Cannot save trace: run %s not found", run_id)
            return
        model.trace_data = trace_data
        await self._session.flush()

    async def delete(self, run_id: str) -> bool:
        stmt = select(EvaluationRunModel).where(
            EvaluationRunModel.id == run_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        model.trace_data = None
        await self._session.flush()
        return True

    async def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        stmt = (
            select(EvaluationRunModel.id, EvaluationRunModel.trace_data)
            .where(EvaluationRunModel.trace_data.isnot(None))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        return [row.trace_data for row in rows if isinstance(row.trace_data, dict)]
