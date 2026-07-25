"""JSON event serialization implementing the Kernel EventSerializer contract."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.kernel.entities.base import UUIDv7
from app.kernel.events.event_bus import BaseEvent, EventSerializer


class JsonEventSerializer(EventSerializer):
    """JSON-based event serializer.

    Serializes events to JSON strings and deserializes them back.
    Uses a registry of event types to reconstruct concrete event classes.
    """

    def __init__(self) -> None:
        """Initialize the serializer with an empty event type registry."""
        self._event_types: dict[str, type[BaseEvent]] = {}

    def register_event_type(self, event_type: str, event_class: type[BaseEvent]) -> None:
        """Register an event class for deserialization.

        Args:
            event_type: The event type string.
            event_class: The event class to instantiate during deserialization.

        """
        self._event_types[event_type] = event_class

    def serialize(self, event: BaseEvent) -> str:
        """Serialize an event to a JSON string.

        Args:
            event: The event to serialize.

        Returns:
            A JSON string representation of the event.

        """
        payload: dict[str, Any] = {
            "event_type": event.event_type,
            "event_id": str(event.event_id),
            "occurred_at": event.occurred_at.isoformat() if hasattr(event, "occurred_at") else "",
        }
        for key, value in event.__dict__.items():
            if key.startswith("_"):
                continue
            if key in ("event_type", "event_id", "occurred_at"):
                continue
            payload[key] = _serialize_value(value)
        return json.dumps(payload, default=str)

    def deserialize(self, payload: str, event_type: str) -> BaseEvent:
        """Deserialize a JSON string back into an event.

        Args:
            payload: The JSON string to deserialize.
            event_type: The expected event type.

        Returns:
            The deserialized event instance.

        Raises:
            ValueError: If the event type is not registered.

        """
        data: dict[str, Any] = json.loads(payload)
        event_class = self._event_types.get(event_type)
        if event_class is None:
            msg = f"No registered event class for type: {event_type}"
            raise ValueError(msg)

        data["event_id"] = UUIDv7.from_string(str(data["event_id"]))
        data["occurred_at"] = datetime.fromisoformat(str(data["occurred_at"]))

        return event_class(**data)


def _serialize_value(value: object) -> object:
    """Recursively serialize a value for JSON encoding.

    Args:
        value: The value to serialize.

    Returns:
        A JSON-serializable representation of the value.

    """
    if isinstance(value, UUIDv7):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    return value
