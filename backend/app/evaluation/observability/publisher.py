"""Event publisher decorator that persists timeline entries and broadcasts via SSE."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.evaluation.observability.broadcaster import get_broadcaster
from app.evaluation.observability.domain import TimelineEntry
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.domain.contracts.evaluation_contracts import EventPublisher
    from app.evaluation.observability.contracts import TimelineRepository


class ObservabilityEventPublisher:
    """Wraps an EventPublisher to persist events and broadcast via SSE.

    Every published event is:
    1. Persisted as a TimelineEntry in the database
    2. Broadcast to SSE subscribers
    3. Forwarded to the wrapped EventPublisher (Redis)
    """

    def __init__(
        self,
        inner: EventPublisher,
        timeline_repo: TimelineRepository,
    ) -> None:
        self._inner = inner
        self._timeline_repo = timeline_repo
        self._broadcaster = get_broadcaster()

    async def publish(self, event: object) -> None:
        await self._persist_and_broadcast(event)
        await self._inner.publish(event)

    async def publish_many(self, events: Sequence[object]) -> None:
        for event in events:
            await self._persist_and_broadcast(event)
        await self._inner.publish_many(events)

    async def _persist_and_broadcast(self, event: object) -> None:
        entry = self._to_timeline_entry(event)
        if entry is None:
            return
        try:
            await self._timeline_repo.save(entry)
        except Exception:
            pass
        try:
            broadcast_data = {
                "event_type": entry.event_type,
                "occurred_at": entry.occurred_at.isoformat(),
                "data": entry.data,
                "correlation_id": entry.correlation_id,
            }
            await self._broadcaster.publish(str(entry.run_id), broadcast_data)
        except Exception:
            pass

    def _to_timeline_entry(self, event: object) -> TimelineEntry | None:
        event_type = getattr(event, "event_type", None)
        if event_type is None:
            return None

        run_id = getattr(event, "run_id", None)
        if run_id is None:
            return None

        if isinstance(run_id, UUIDv7):
            pass
        elif isinstance(run_id, str):
            run_id = UUIDv7.from_string(run_id)
        else:
            return None

        correlation_id = getattr(event, "correlation_id", None)
        occurred_at = getattr(event, "occurred_at", None)
        if not isinstance(occurred_at, datetime):
            occurred_at = datetime.now(UTC)

        data: dict[str, Any] = {}
        for attr in (
            "item_id", "item_index", "metric_name", "score",
            "aggregated_score", "error_code", "error_message",
            "reason", "failure_reason", "retry_count",
            "tokens_used", "cost_usd", "duration_ms",
            "timeout_seconds", "checkpoint_number", "items_completed",
            "items_total", "force",
        ):
            val = getattr(event, attr, None)
            if val is not None:
                data[attr] = str(val) if not isinstance(val, (int, float, bool)) else val

        return TimelineEntry(
            run_id=run_id,
            event_type=event_type,
            data=data,
            correlation_id=str(correlation_id) if correlation_id else None,
            occurred_at=occurred_at,
        )
