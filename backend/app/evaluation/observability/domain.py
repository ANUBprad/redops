"""Value objects for run observability (timeline events & logs)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.kernel.entities.base import UUIDv7


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    entry_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    event_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class RunLogEntry:
    log_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    level: str = "INFO"
    source: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
