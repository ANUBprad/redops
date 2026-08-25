"""Redis-based trace repository implementation."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis import asyncio as aioredis

from app.evaluation.replay.contracts import TraceRepository

logger = logging.getLogger(__name__)

TRACE_KEY_PREFIX = "redops:trace:"
TRACE_INDEX_KEY = "redops:traces:index"


class RedisTraceRepository(TraceRepository):
    """Redis-backed execution trace storage."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def find_by_run_id(self, run_id: str) -> dict[str, Any] | None:
        key = f"{TRACE_KEY_PREFIX}{run_id}"
        data = await self._redis.get(key)
        if data:
            try:
                parsed = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to decode trace for run %s", run_id)
            else:
                if isinstance(parsed, dict):
                    return parsed
                logger.warning("Trace for run %s is not a JSON object", run_id)
        return None

    async def save(self, run_id: str, trace_data: dict[str, Any]) -> None:
        key = f"{TRACE_KEY_PREFIX}{run_id}"
        data = json.dumps(trace_data, default=str)
        await self._redis.set(key, data)
        await self._redis.sadd(TRACE_INDEX_KEY, run_id)  # type: ignore[misc]

    async def delete(self, run_id: str) -> bool:
        key = f"{TRACE_KEY_PREFIX}{run_id}"
        deleted_count = await self._redis.delete(key)
        await self._redis.srem(TRACE_INDEX_KEY, run_id)  # type: ignore[misc]
        return bool(deleted_count)

    async def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        run_ids = await self._redis.smembers(TRACE_INDEX_KEY)  # type: ignore[misc]
        if not run_ids:
            return []

        ordered_ids = sorted(
            member.decode() if isinstance(member, bytes) else str(member) for member in run_ids
        )
        results = []
        for run_id in ordered_ids[offset : offset + limit]:
            trace = await self.find_by_run_id(run_id)
            if trace:
                results.append(trace)
        return results
