"""In-memory event broadcaster for SSE."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class EventBroadcaster:
    _subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]]
    _lock: asyncio.Lock

    def __init__(self) -> None:
        self._subscribers = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            subs = self._subscribers.get(run_id, [])
            if queue in subs:
                subs.remove(queue)
            if not subs:
                self._subscribers.pop(run_id, None)

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(run_id, []))
        for queue in subs:
            await queue.put(event)

    async def stream(self, run_id: str) -> AsyncGenerator[dict[str, Any], None]:
        queue = await self.subscribe(run_id)
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            await self.unsubscribe(run_id, queue)


_broadcaster: EventBroadcaster | None = None


def get_broadcaster() -> EventBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster


def set_broadcaster(broadcaster: EventBroadcaster) -> None:
    global _broadcaster
    _broadcaster = broadcaster
