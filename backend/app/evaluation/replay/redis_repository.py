"""Redis-based trace repository implementation."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.evaluation.replay.contracts import TraceRepository

logger = logging.getLogger(__name__)

TRACE_KEY_PREFIX = "redops:trace:"
TRACE_INDEX_KEY = "redops:traces:index"


class RedisTraceRepository(TraceRepository):
    """Redis-backed execution trace storage."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def find_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        key = f"{TRACE_KEY_PREFIX}{run_id}"
        data = await self._redis.get(key)
        if data:
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to decode trace for run %s", run_id)
        return None

    async def save(self, run_id: str, trace_data: dict[str, Any]) -> None:
        key = f"{TRACE_KEY_PREFIX}{run_id}"
        data = json.dumps(trace_data, default=str)
        await self._redis.set(key, data)
        await self._redis.sadd(TRACE_INDEX_KEY, run_id)

    async def delete(self, run_id: str) -> bool:
        key = f"{TRACE_KEY_PREFIX}{run_id}"
        deleted = await self._redis.delete(key)
        await self._redis.srem(TRACE_INDEX_KEY, run_id)
        return deleted > 0

    async def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        run_ids = await self._redis.smembers(TRACE_INDEX_KEY)
        if not run_ids:
            return []

        results = []
        for run_id_bytes in run_ids[offset : offset + limit]:
            run_id = run_id_bytes.decode() if isinstance(run_id_bytes, bytes) else str(run_id_bytes)
            trace = await self.find_by_run_id(run_id)
            if trace:
                results.append(trace)
        return results
