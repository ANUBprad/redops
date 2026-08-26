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


class TestAuditEventSubscriber:
    def test_records_audit_for_mapped_event(self) -> None:
        mock_service = MagicMock()
        mock_service.record = AsyncMock()
        subscriber = AuditEventSubscriber(mock_service)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.record.assert_called_once()
        call_kwargs = mock_service.record.call_args.kwargs
        assert call_kwargs["action"] == "execute"
        assert call_kwargs["resource_type"] == "evaluation_run"
        assert call_kwargs["resource_id"] == str(event.run_id)
        assert call_kwargs["request_id"] == "corr-123"
        assert call_kwargs["metadata"]["event_type"] == "evaluation.completed"
        assert call_kwargs["metadata"]["items_completed"] == 10

    def test_records_audit_for_finding_detected(self) -> None:
        mock_service = MagicMock()
        mock_service.record = AsyncMock()
        subscriber = AuditEventSubscriber(mock_service)
        event = _FakeFindingDetectedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.record.assert_called_once()
        call_kwargs = mock_service.record.call_args.kwargs
        assert call_kwargs["action"] == "create"
        assert call_kwargs["resource_type"] == "red_team"
        assert call_kwargs["resource_id"] == str(event.finding_id)

    def test_skips_unmapped_event(self) -> None:
        mock_service = MagicMock()
        mock_service.record = AsyncMock()
        subscriber = AuditEventSubscriber(mock_service)
        event = _FakeUnmappedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.record.assert_not_called()

    def test_skips_event_without_event_type(self) -> None:
        mock_service = MagicMock()
        mock_service.record = AsyncMock()
        subscriber = AuditEventSubscriber(mock_service)

        import asyncio

        asyncio.run(subscriber.handle("not_an_event"))

        mock_service.record.assert_not_called()

    def test_handles_service_failure_gracefully(self) -> None:
        mock_service = MagicMock()
        mock_service.record = AsyncMock(side_effect=RuntimeError("db error"))
        subscriber = AuditEventSubscriber(mock_service)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.record.assert_called_once()
