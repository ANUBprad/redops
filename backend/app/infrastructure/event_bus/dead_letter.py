"""Dead-letter queue support for the Redis Streams event bus.

Events that exceed maximum delivery attempts are moved to a
dead-letter stream for manual inspection and replay.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

    from app.infrastructure.config.redis import RedisConfiguration
    from app.kernel.events.event_bus import BaseEvent, EventSerializer

# Type alias matching redis-py stubs exactly.
RedisFieldValue = bytes | bytearray | memoryview | str | int | float
RedisFields = dict[RedisFieldValue, RedisFieldValue]

# What redis-py stubs actually accept for xadd fields.
_XaddFields = dict[bytes | memoryview | str | int | float, bytes | memoryview | str | int | float]

# Each stream reply is (stream_name, entries) where entries is
# list[tuple[entry_id, field_dict]].
_StreamReply = list[tuple[bytes, list[tuple[bytes, dict[bytes, bytes]]]]]


def decode_field(value: RedisFieldValue) -> str:
    """Decode a single Redis field value to str.

    Args:
        value: A raw Redis field value.

    Returns:
        The decoded string representation.

    """
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, bytearray):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, memoryview):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


def normalize_stream_fields(raw: dict[RedisFieldValue, RedisFieldValue]) -> dict[str, Any]:
    """Normalize a raw Redis stream field dict to str keys and decoded values.

    Args:
        raw: The raw dictionary returned by Redis stream commands.

    Returns:
        A dictionary with string keys and decoded values.

    """
    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        str_key = decode_field(key)
        if isinstance(value, bytes | bytearray | memoryview):
            normalized[str_key] = decode_field(value)
        else:
            normalized[str_key] = value
    return normalized


def normalize_stream_entry(
    entry_id: RedisFieldValue,
    data: dict[RedisFieldValue, RedisFieldValue] | None,
) -> tuple[str, dict[str, Any]]:
    """Normalize a single Redis stream entry (id + fields).

    Args:
        entry_id: The stream entry ID.
        data: The raw field dictionary from Redis, or None.

    Returns:
        A tuple of (decoded entry ID, normalized fields dict).
        When data is None the normalized dict is empty.

    """
    decoded_id = decode_field(entry_id)
    if data is None:
        return decoded_id, {}
    normalized_data = normalize_stream_fields(data)
    return decoded_id, normalized_data


def coerce_fields(source: dict[str, str]) -> RedisFields:
    """Convert a str→str dict into a RedisFields dict via explicit loop.

    Args:
        source: A dictionary whose keys and values are plain strings.

    Returns:
        A new dict matching the RedisFields type alias.

    """
    fields: RedisFields = {}
    for k, v in source.items():
        fields[k] = v
    return fields


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
            The decoded ID of the dead-letter stream entry.

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
        fields = coerce_fields(payload)
        xadd_fields = cast("_XaddFields", fields)
        raw_entry_id = await self._redis.xadd(stream, xadd_fields)
        return decode_field(raw_entry_id)

    async def replay_event(self, event_type: str, entry_id: str) -> dict[str, Any] | None:
        """Retrieve a dead-lettered event for replay.

        Args:
            event_type: The event type to replay.
            entry_id: The stream entry ID to retrieve.

        Returns:
            The event data as a dictionary, or None if not found.

        """
        stream = self._stream_name(event_type)
        raw_results: _StreamReply = cast(
            "_StreamReply",
            await self._redis.xrange(stream, min=entry_id, max=entry_id),
        )
        if not raw_results:
            return None
        first_raw = raw_results[0]
        raw_entry_id = first_raw[0]
        raw_data = first_raw[1]
        cast_data = cast("dict[RedisFieldValue, RedisFieldValue]", raw_data)
        _decoded_id, normalized = normalize_stream_entry(raw_entry_id, cast_data)
        return normalized

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
        raw_results: _StreamReply = cast(
            "_StreamReply",
            await self._redis.xrevrange(stream, max="+", min="-", count=count),
        )
        events: list[dict[str, Any]] = []
        if raw_results is None:
            return events
        for first_raw in raw_results:
            raw_entry_id = first_raw[0]
            raw_data = first_raw[1]
            cast_data = cast("dict[RedisFieldValue, RedisFieldValue]", raw_data)
            entry_id_str, normalized = normalize_stream_entry(raw_entry_id, cast_data)
            events.append({"id": entry_id_str, **normalized})
        return events

    async def count_events(self, event_type: str) -> int:
        """Count dead-lettered events for an event type.

        Args:
            event_type: The event type to count.

        Returns:
            The number of dead-lettered entries.

        """
        stream = self._stream_name(event_type)
        count_result: int = await self._redis.xlen(stream)
        return count_result
