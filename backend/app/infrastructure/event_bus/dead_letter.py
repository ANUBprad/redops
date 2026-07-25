"""Dead-letter queue support for the Redis Streams event bus.

Events that exceed maximum delivery attempts are moved to a
dead-letter stream for manual inspection and replay.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

    from app.infrastructure.config.redis import RedisConfiguration
    from app.kernel.events.event_bus import BaseEvent, EventSerializer


class DeadLetterQueue:
    """Dead-letter queue for events that failed processing.

    Events are stored in a Redis stream prefixed with the configured
    dead-letter prefix. Each entry records the original event data,
    the number of delivery attempts, the last error, and the timestamp
    of failure.
    """

    def __init__(
        self,
        redis: AsyncRedis,
        config: RedisConfiguration,
        serializer: EventSerializer,
    ) -> None:
        """Initialize with Redis client, config, and serializer."""
        self._redis = redis
        self._config = config
        self._serializer = serializer

    def _stream_name(self, event_type: str) -> str:
        """Build the dead-letter stream name for an event type.

        Args:
            event_type: The event type string.

        Returns:
            The Redis stream key for dead-letter events.

        """
        return f"{self._config.dead_letter_prefix}:{event_type}"

    async def send_to_dead_letter(
        self,
        event: BaseEvent,
        delivery_count: int,
        last_error: str,
    ) -> str:
        """Send an event to the dead-letter queue.

        Args:
            event: The event that failed processing.
            delivery_count: The number of times delivery was attempted.
            last_error: A description of the last error encountered.

        Returns:
            The ID of the dead-letter stream entry.

        """
        payload: dict[str, str] = {
            "event": self._serializer.serialize(event),
            "event_type": event.event_type,
            "event_id": str(event.event_id),
            "delivery_count": str(delivery_count),
            "last_error": last_error,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        stream = self._stream_name(event.event_type)
        entry_id: str = await self._redis.xadd(stream, payload)  # type: ignore[arg-type]
        return entry_id

    async def replay_event(self, event_type: str, entry_id: str) -> dict[str, Any] | None:
        """Retrieve a dead-lettered event for replay.

        Args:
            event_type: The event type to replay.
            entry_id: The stream entry ID to retrieve.

        Returns:
            The event data as a dictionary, or None if not found.

        """
        stream = self._stream_name(event_type)
        results = await self._redis.xrange(stream, min=entry_id, max=entry_id)
        if not results:
            return None
        _entry_id, data = results[0]
        return data  # type: ignore[no-any-return]

    async def remove_event(self, event_type: str, entry_id: str) -> None:
        """Remove a dead-lettered event after successful replay.

        Args:
            event_type: The event type of the entry to remove.
            entry_id: The stream entry ID to remove.

        """
        stream = self._stream_name(event_type)
        await self._redis.xdel(stream, entry_id)

    async def list_events(
        self,
        event_type: str,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """List dead-lettered events for an event type.

        Args:
            event_type: The event type to list.
            count: The maximum number of events to return.

        Returns:
            A list of event data dictionaries.

        """
        stream = self._stream_name(event_type)
        results = await self._redis.xrevrange(stream, max="+", min="-", count=count)
        events: list[dict[str, Any]] = []
        for entry_id, data in results:
            events.append({"id": entry_id, **data})
        return events

    async def count_events(self, event_type: str) -> int:
        """Count dead-lettered events for an event type.

        Args:
            event_type: The event type to count.

        Returns:
            The number of dead-lettered entries.

        """
        stream = self._stream_name(event_type)
        return await self._redis.xlen(stream)  # type: ignore[no-any-return]
