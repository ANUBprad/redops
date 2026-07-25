"""Tests for JsonEventSerializer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.infrastructure.event_bus.serialization import JsonEventSerializer
from app.kernel.entities.base import UUIDv7


@dataclass
class _TestEvent:
    event_type: str = "test.event.occurred"
    event_id: UUIDv7 = field(default_factory=lambda: UUIDv7())
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: str = "hello"


class TestJsonEventSerializer:
    def test_serialize_deserialize_roundtrip(self) -> None:
        serializer = JsonEventSerializer()
        serializer.register_event_type("test.event.occurred", _TestEvent)

        event = _TestEvent(data="world")
        payload = serializer.serialize(event)
        deserialized = serializer.deserialize(payload, "test.event.occurred")

        assert deserialized.event_type == event.event_type
        assert str(deserialized.event_id) == str(event.event_id)
        assert deserialized.data == event.data

    def test_deserialize_unregistered_type_raises(self) -> None:
        serializer = JsonEventSerializer()
        payload = '{"event_type": "unknown.type", "data": "test"}'

        with __import__("pytest").raises(ValueError):
            serializer.deserialize(payload, "unknown.type")

    def test_serialize_with_uuidv7_value(self) -> None:
        serializer = JsonEventSerializer()
        entity_id = UUIDv7()
        event = _TestEvent(data=str(entity_id))
        payload = serializer.serialize(event)
        assert str(entity_id) in payload

    def test_serialize_nested_dict(self) -> None:
        serializer = JsonEventSerializer()
        event = _TestEvent(data='{"nested": "value"}')
        payload = serializer.serialize(event)
        assert "nested" in payload
