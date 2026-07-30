"""Tests for observability domain value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from app.evaluation.observability.domain import RunLogEntry, TimelineEntry
from app.kernel.entities.base import UUIDv7


class TestTimelineEntry:
    def test_default_fields(self) -> None:
        entry = TimelineEntry()
        assert isinstance(entry.entry_id, UUIDv7)
        assert isinstance(entry.run_id, UUIDv7)
        assert entry.event_type == ""
        assert entry.data == {}
        assert entry.correlation_id is None
        assert isinstance(entry.occurred_at, datetime)

    def test_frozen(self) -> None:
        entry = TimelineEntry(event_type="test")
        try:
            entry.event_type = "changed"
            assert False, "Should be frozen"
        except Exception:
            pass

    def test_custom_fields(self) -> None:
        run_id = UUIDv7()
        now = datetime.now(UTC)
        entry = TimelineEntry(
            run_id=run_id,
            event_type="evaluation.started",
            data={"items_total": 10},
            correlation_id="corr-123",
            occurred_at=now,
        )
        assert entry.run_id == run_id
        assert entry.event_type == "evaluation.started"
        assert entry.data == {"items_total": 10}
        assert entry.correlation_id == "corr-123"
        assert entry.occurred_at == now


class TestRunLogEntry:
    def test_default_fields(self) -> None:
        entry = RunLogEntry()
        assert isinstance(entry.log_id, UUIDv7)
        assert isinstance(entry.run_id, UUIDv7)
        assert entry.level == "INFO"
        assert entry.source == ""
        assert entry.message == ""
        assert entry.metadata == {}

    def test_frozen(self) -> None:
        entry = RunLogEntry()
        try:
            entry.level = "ERROR"
            assert False, "Should be frozen"
        except Exception:
            pass

    def test_custom_fields(self) -> None:
        run_id = UUIDv7()
        entry = RunLogEntry(
            run_id=run_id,
            level="ERROR",
            source="test.component",
            message="Something went wrong",
            metadata={"retry_count": 3},
        )
        assert entry.run_id == run_id
        assert entry.level == "ERROR"
        assert entry.message == "Something went wrong"
        assert entry.metadata == {"retry_count": 3}
