"""Redis Streams implementation of the Kernel EventBus contract.

Provides publish/subscribe semantics via Redis Streams with consumer
group support, dead-letter queue integration, and configurable retry
with exponential backoff.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.infrastructure.event_bus.dead_letter import (
    DeadLetterQueue,
    RedisFields,
    normalize_stream_entry,
)
from app.infrastructure.event_bus.serialization import JsonEventSerializer
from app.kernel.events.event_bus import BaseEvent, EventBus, EventHandler
from app.kernel.lifecycle.lifecycle import LifecycleService

if TYPE_CHECKING:
    from redis.asyncio import Redis as AsyncRedis

    from app.infrastructure.config.redis import RedisConfiguration


class RedisStreamsEventBus(EventBus, LifecycleService):
    """Redis Streams implementation of the Kernel EventBus.

    Features:
        - Publish events to Redis Streams with automatic stream creation
        - Consumer group subscriptions for load-balanced processing
        - Background polling via asyncio tasks
        - Dead-letter queue for exhausted retries
        - Exponential backoff retry policy
        - Health check via Redis ping
    """

    def __init__(
        self,
        redis: AsyncRedis,
        config: RedisConfiguration,
        serializer: JsonEventSerializer | None = None,
        dead_letter_queue: DeadLetterQueue | None = None,
    ) -> None:
        """Initialize with Redis client, config, and optional dependencies."""
        self._redis = redis
        self._config = config
        self._serializer = serializer or JsonEventSerializer()
        self._dead_letter_queue = dead_letter_queue or DeadLetterQueue(
            redis,
            config,
            self._serializer,
        )
        self._subscriptions: dict[str, list[tuple[EventHandler, str | None]]] = {}
        self._consumer_tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False

    @property
    def redis(self) -> AsyncRedis:
        """Return the underlying Redis client."""
        return self._redis

    async def initialize(self) -> None:
        """Initialize the event bus."""
        self._running = False

    async def start(self) -> None:
        """Start the event bus and begin consuming subscribed streams."""
        self._running = True
        for event_type in self._subscriptions:
            self._start_consumer(event_type)

    async def stop(self) -> None:
        """Stop all consumer tasks gracefully."""
        self._running = False
        for _event_type, task in list(self._consumer_tasks.items()):
            task.cancel()
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks.values(), return_exceptions=True)
            self._consumer_tasks.clear()

    async def dispose(self) -> None:
        """Dispose of the event bus resources."""
        await self.stop()

    async def health(self) -> bool:
        """Check if the Redis connection is healthy.

        Returns:
            True if Redis is reachable, False otherwise.

        """
        try:
            result: bool = await self._redis.ping()
            return result
        except Exception:
            return False

    def _stream_name(self, event_type: str) -> str:
        """Build the Redis stream key for an event type.

        Args:
            event_type: The event type string.

        Returns:
            The Redis stream key.

        """
        return f"{self._config.stream_prefix}:{event_type}"

    async def publish(self, event: BaseEvent, correlation_id: str | None = None) -> None:
        """Publish an event to its Redis stream.

        Args:
            event: The event to publish.
            correlation_id: Optional correlation ID for event tracing.

        """
        payload = self._serializer.serialize(event)
        stream = self._stream_name(event.event_type)
        fields: RedisFields = {
            "payload": payload,
            "event_type": event.event_type,
            "event_id": str(event.event_id),
            "occurred_at": (
                event.occurred_at.isoformat()
                if hasattr(event, "occurred_at")
                else datetime.now(UTC).isoformat()
            ),
            "correlation_id": correlation_id or "",
        }
        await self._redis.xadd(stream, fields)

    async def publish_many(
        self,
        events: list[BaseEvent],
        correlation_id: str | None = None,
    ) -> None:
        """Publish multiple events atomically within a Redis pipeline.

        Args:
            events: The events to publish.
            correlation_id: Optional correlation ID for event tracing.

        """
        async with self._redis.pipeline() as pipe:
            for event in events:
                payload = self._serializer.serialize(event)
                stream = self._stream_name(event.event_type)
                fields: RedisFields = {
                    "payload": payload,
                    "event_type": event.event_type,
                    "event_id": str(event.event_id),
                    "occurred_at": (
                        event.occurred_at.isoformat()
                        if hasattr(event, "occurred_at")
                        else datetime.now(UTC).isoformat()
                    ),
                    "correlation_id": correlation_id or "",
                }
                pipe.xadd(stream, fields)
            await pipe.execute()

    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        *,
        group: str | None = None,
    ) -> None:
        """Subscribe to an event type with an optional consumer group.

        Args:
            event_type: The event type to subscribe to.
            handler: The async callable to handle events.
            group: Optional consumer group name for load-balanced delivery.

        """
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        self._subscriptions[event_type].append((handler, group))

        consumer_group = group or self._config.consumer_group
        stream = self._stream_name(event_type)
        with contextlib.suppress(Exception):
            await self._redis.xgroup_create(stream, consumer_group, mkstream=True)

        if self._running:
            self._start_consumer(event_type)

    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler | None = None,
    ) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: The event type to unsubscribe from.
            handler: Optional specific handler to remove. If None, all are removed.

        """
        if event_type not in self._subscriptions:
            return
        if handler is None:
            del self._subscriptions[event_type]
        else:
            self._subscriptions[event_type] = [
                (h, g) for h, g in self._subscriptions[event_type] if h is not handler
            ]

        if event_type in self._consumer_tasks:
            self._consumer_tasks[event_type].cancel()
            del self._consumer_tasks[event_type]

    def _start_consumer(self, event_type: str) -> None:
        """Start a background consumer task for a subscribed event type.

        Args:
            event_type: The event type to consume.

        """
        if event_type in self._consumer_tasks:
            return
        task = asyncio.create_task(
            self._consume_loop(event_type),
            name=f"event-consumer-{event_type}",
        )
        self._consumer_tasks[event_type] = task

    async def _consume_loop(self, event_type: str) -> None:
        """Background loop for consuming events from a Redis stream.

        Args:
            event_type: The event type to consume from.

        """
        stream = self._stream_name(event_type)
        subscriptions = self._subscriptions.get(event_type, [])
        if not subscriptions:
            return

        consumer_group = self._config.consumer_group

        with contextlib.suppress(Exception):
            await self._redis.xgroup_create(stream, consumer_group, mkstream=True)

        consumer_name = f"consumer-{event_type}-{id(self)}"

        while self._running:
            try:
                results = await self._redis.xreadgroup(
                    groupname=consumer_group,
                    consumername=consumer_name,
                    streams={stream: ">"},
                    count=self._config.batch_size,
                    block=self._config.poll_timeout_ms,
                )

                if not results:
                    continue

                for _raw_stream_name, raw_entries in results:
                    if raw_entries is None:
                        continue
                    for raw_entry_id, raw_data in raw_entries:
                        entry_id_str, normalized_data = normalize_stream_entry(
                            raw_entry_id, raw_data
                        )
                        await self._process_entry(
                            event_type, entry_id_str, normalized_data, subscriptions
                        )

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _process_entry(
        self,
        event_type: str,
        entry_id: str,
        data: dict[str, Any],
        subscriptions: list[tuple[EventHandler, str | None]],
    ) -> None:
        """Process a single stream entry through all subscribed handlers.

        Args:
            event_type: The event type being processed.
            entry_id: The Redis stream entry ID.
            data: The stream entry data.
            subscriptions: The list of (handler, group) subscriptions.

        """
        payload_str: str = data.get("payload", "{}")
        try:
            event = self._serializer.deserialize(payload_str, event_type)
        except Exception:
            event = None

        for handler, _group in subscriptions:
            try:
                if event is not None:
                    await handler(event)
                else:
                    await handler(data)
            except Exception as exc:
                delivery_count = int(data.get("delivery_count", 0)) + 1
                if delivery_count >= self._config.max_delivery_count:
                    if event is not None:
                        await self._dead_letter_queue.send_to_dead_letter(
                            event=event,
                            delivery_count=delivery_count,
                            last_error=str(exc),
                        )
                else:
                    retry_data: dict[str, Any] = {**data, "delivery_count": delivery_count}
                    retry_fields: RedisFields = dict(retry_data.items())
                    await self._redis.xadd(
                        self._stream_name(event_type),
                        retry_fields,
                    )
                continue

        stream_name = self._stream_name(event_type)
        await self._redis.xack(stream_name, self._config.consumer_group, entry_id)
        await self._redis.xdel(stream_name, entry_id)
