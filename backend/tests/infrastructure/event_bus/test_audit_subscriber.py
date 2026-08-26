"""Tests for AuditEventSubscriber."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.event_bus.subscribers.audit_subscriber import AuditEventSubscriber
from app.kernel.entities.base import UUIDv7


@dataclass(frozen=True, slots=True)
class _FakeEvaluationCompletedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = "corr-123"
    run_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    items_completed: int = 10
    items_total: int = 10
    duration_ms: int = 5000

    @property
    def event_type(self) -> str:
        return "evaluation.completed"


@dataclass(frozen=True, slots=True)
class _FakeFindingDetectedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    finding_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    campaign_id: str = "camp-1"
    attack_category: str = "prompt_injection"
    severity: str = "high"
    verdict: str = "fail"

    @property
    def event_type(self) -> str:
        return "safety.finding.detected"


@dataclass(frozen=True, slots=True)
class _FakeUnmappedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None

    @property
    def event_type(self) -> str:
        return "evaluation.item.started"


def _make_mock_session_factory(saved_entries: list) -> MagicMock:
    """Create a mock session factory that captures saved audit entries."""
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    def capture_add(model):
        saved_entries.append(model)

    mock_session.add = capture_add

    factory = MagicMock(return_value=mock_session)
    return factory


class TestAuditEventSubscriber:
    def test_records_audit_for_mapped_event(self) -> None:
        saved_entries: list = []
        session_factory = _make_mock_session_factory(saved_entries)
        subscriber = AuditEventSubscriber(session_factory)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        assert len(saved_entries) == 1
        model = saved_entries[0]
        assert model.action == "execute"
        assert model.resource_type == "evaluation_run"
        assert model.resource_id == str(event.run_id)
        assert model.request_id == "corr-123"

    def test_records_audit_for_finding_detected(self) -> None:
        saved_entries: list = []
        session_factory = _make_mock_session_factory(saved_entries)
        subscriber = AuditEventSubscriber(session_factory)
        event = _FakeFindingDetectedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        assert len(saved_entries) == 1
        model = saved_entries[0]
        assert model.action == "create"
        assert model.resource_type == "red_team"
        assert model.resource_id == str(event.finding_id)

    def test_skips_unmapped_event(self) -> None:
        saved_entries: list = []
        session_factory = _make_mock_session_factory(saved_entries)
        subscriber = AuditEventSubscriber(session_factory)
        event = _FakeUnmappedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        assert len(saved_entries) == 0

    def test_skips_event_without_event_type(self) -> None:
        saved_entries: list = []
        session_factory = _make_mock_session_factory(saved_entries)
        subscriber = AuditEventSubscriber(session_factory)

        import asyncio

        asyncio.run(subscriber.handle("not_an_event"))

        assert len(saved_entries) == 0

    def test_commits_session_on_success(self) -> None:
        saved_entries: list = []
        session_factory = _make_mock_session_factory(saved_entries)
        subscriber = AuditEventSubscriber(session_factory)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_session = session_factory.return_value
        mock_session.commit.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    def test_rolls_back_on_failure(self) -> None:
        session_factory = MagicMock()
        mock_session = MagicMock()
        mock_session.add = MagicMock(side_effect=RuntimeError("db error"))
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        session_factory.return_value = mock_session

        subscriber = AuditEventSubscriber(session_factory)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
