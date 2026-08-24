"""Composite trace repository with database-first, Redis-fallback strategy.

Tries the database (evaluation_runs.trace_data) first for traces
produced by the evaluation workflow. Falls back to Redis for traces
written directly by external consumers.
"""

from __future__ import annotations

import logging
from typing import Any

from app.evaluation.replay.contracts import TraceRepository

logger = logging.getLogger(__name__)


class CompositeTraceRepository(TraceRepository):
    """Trace repository that reads from database first, then Redis.

    The database is the authoritative source for traces produced by
    the evaluation workflow. Redis is retained as a fallback for
    traces written directly by external consumers.
    """

    def __init__(
        self,
        primary: TraceRepository,
        fallback: TraceRepository | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    async def find_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        # Try database first
        data = await self._primary.find_by_run_id(run_id)
        if data is not None:
            return data

        # Fall back to Redis if available
        if self._fallback is not None:
            data = await self._fallback.find_by_run_id(run_id)
            if data is not None:
                logger.debug("Trace loaded from fallback for run %s", run_id)
                return data

        return None

    async def save(self, run_id: str, trace_data: dict[str, Any]) -> None:
        # Save to primary (database)
        await self._primary.save(run_id, trace_data)

        # Also save to fallback (Redis) if available, for backward compatibility
        if self._fallback is not None:
            try:
                await self._fallback.save(run_id, trace_data)
            except Exception:
                logger.warning("Failed to save trace to fallback for run %s", run_id)

    async def delete(self, run_id: str) -> bool:
        deleted = await self._primary.delete(run_id)
        if self._fallback is not None:
            try:
                await self._fallback.delete(run_id)
            except Exception:
                logger.warning("Failed to delete trace from fallback for run %s", run_id)
        return deleted

    async def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return await self._primary.list_runs(limit=limit, offset=offset)
