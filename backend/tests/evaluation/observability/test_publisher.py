"""Tests for ObservabilityEventPublisher."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.evaluation.observability.domain import TimelineEntry
from app.evaluation.observability.publisher import ObservabilityEventPublisher
from app.kernel.entities.base import UUIDv7


@pytest.mark.asyncio
class TestObservabilityEventPublisher:
    async def test_publish_persists_and_broadcasts(self) -> None:
        mock_inner = AsyncMock()
        mock_timeline = AsyncMock()

        publisher = ObservabilityEventPublisher(mock_inner, mock_timeline)

        class FakeEvent:
            event_type = "evaluation.queued"
            run_id = UUIDv7()
            correlation_id = "corr-1"
            occurred_at = None
            items_total = 10

        event = FakeEvent()
        await publisher.publish(event)

        mock_timeline.save.assert_awaited_once()
        saved: TimelineEntry = mock_timeline.save.call_args[0][0]
        assert saved.event_type == "evaluation.queued"
        assert saved.run_id == event.run_id
        assert saved.data.get("items_total") == 10

        mock_inner.publish.assert_awaited_once_with(event)

    async def test_publish_many(self) -> None:
        mock_inner = AsyncMock()
        mock_timeline = AsyncMock()

        publisher = ObservabilityEventPublisher(mock_inner, mock_timeline)

        class FakeEvent:
            event_type = "evaluation.item.completed"
            run_id = UUIDv7()
            correlation_id = None
            occurred_at = None
            item_id = UUIDv7()
            item_index = 5

        events = [FakeEvent(), FakeEvent()]
        await publisher.publish_many(events)

        assert mock_timeline.save.await_count == 2
        mock_inner.publish_many.assert_awaited_once_with(events)

    async def test_publish_non_domain_event(self) -> None:
        mock_inner = AsyncMock()
        mock_timeline = AsyncMock()

        publisher = ObservabilityEventPublisher(mock_inner, mock_timeline)

        await publisher.publish("not an event")

        mock_timeline.save.assert_not_called()
        mock_inner.publish.assert_awaited_once_with("not an event")
