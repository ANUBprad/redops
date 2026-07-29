from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from app.kernel.entities.base import UUIDv7

EventHandler = Callable[[Any], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class EventMetadata:
    event_id: str
    event_type: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    causation_id: str | None = None
    publisher: str = ""


@runtime_checkable
class BaseEvent(Protocol):
    event_type: str
    event_id: UUIDv7
    occurred_at: datetime


class EventPublisher(ABC):
    @abstractmethod
    async def publish(self, event: BaseEvent, correlation_id: str | None = None) -> None: ...

    @abstractmethod
    async def publish_many(
        self,
        events: list[BaseEvent],
        correlation_id: str | None = None,
    ) -> None: ...


class EventSubscriber(ABC):
    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        *,
        group: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def unsubscribe(self, event_type: str, handler: EventHandler | None = None) -> None: ...


class EventBus(EventPublisher, EventSubscriber, ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def health(self) -> bool: ...


class EventSerializer(ABC):
    @abstractmethod
    def serialize(self, event: BaseEvent) -> str: ...

    @abstractmethod
    def deserialize(self, payload: str, event_type: str) -> BaseEvent: ...
