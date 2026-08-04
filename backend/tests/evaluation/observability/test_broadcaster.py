"""Tests for the EventBroadcaster (SSE pub/sub)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.evaluation.observability.broadcaster import EventBroadcaster


@pytest.mark.asyncio
class TestEventBroadcaster:
    async def test_subscribe_and_publish(self) -> None:
        bc = EventBroadcaster()
        queue = await bc.subscribe("run-1")

        await bc.publish("run-1", {"event_type": "test", "data": "hello"})

        result = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert result == {"event_type": "test", "data": "hello"}

    async def test_multiple_subscribers(self) -> None:
        bc = EventBroadcaster()
        q1 = await bc.subscribe("run-1")
        q2 = await bc.subscribe("run-1")

        await bc.publish("run-1", {"event_type": "test"})

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r1 == r2 == {"event_type": "test"}

    async def test_different_runs_isolated(self) -> None:
        bc = EventBroadcaster()
        q1 = await bc.subscribe("run-1")
        q2 = await bc.subscribe("run-2")

        await bc.publish("run-1", {"event_type": "run1"})
        await bc.publish("run-2", {"event_type": "run2"})

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r1["event_type"] == "run1"
        assert r2["event_type"] == "run2"

    async def test_unsubscribe(self) -> None:
        bc = EventBroadcaster()
        queue = await bc.subscribe("run-1")
        await bc.unsubscribe("run-1", queue)

        await bc.publish("run-1", {"event_type": "test"})

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)

    async def test_cleanup_empty_run(self) -> None:
        bc = EventBroadcaster()
        q1 = await bc.subscribe("run-1")
        await bc.unsubscribe("run-1", q1)

        assert bc._subscribers.get("run-1") is None or bc._subscribers["run-1"] == []

    async def test_stream_generator(self) -> None:
        bc = EventBroadcaster()

        async def publish_after_delay() -> None:
            await asyncio.sleep(0.05)
            await bc.publish("run-1", {"event_type": "stream_test"})

        async def consume() -> list[dict[str, Any]]:
            results = []
            async for event in bc.stream("run-1"):
                results.append(event)
                break
            return results

        results = await asyncio.gather(publish_after_delay(), consume())
        assert results[1] == [{"event_type": "stream_test"}]

    async def test_get_broadcaster_singleton(self) -> None:
        from app.evaluation.observability.broadcaster import get_broadcaster, set_broadcaster

        bc = EventBroadcaster()
        set_broadcaster(bc)
        assert get_broadcaster() is bc
