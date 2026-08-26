"""Tests for NotificationEventSubscriber."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.event_bus.subscribers.notification_subscriber import (
    NotificationEventSubscriber,
)
from app.kernel.entities.base import UUIDv7


@dataclass(frozen=True, slots=True)
class _FakeEvaluationCompletedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = "corr-456"
    run_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    items_completed: int = 5
    items_total: int = 5
    duration_ms: int = 3000

    @property
    def event_type(self) -> str:
        return "evaluation.completed"


@dataclass(frozen=True, slots=True)
class _FakeEvaluationFailedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    error_code: str = "PROVIDER_ERROR"
    error_message: str = "API rate limit exceeded"

    @property
    def event_type(self) -> str:
        return "evaluation.failed"


@dataclass(frozen=True, slots=True)
class _FakeFindingDetectedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    finding_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    campaign_id: str = "camp-99"
    attack_category: str = "jailbreak"
    severity: str = "critical"
    verdict: str = "fail"

    @property
    def event_type(self) -> str:
        return "safety.finding.detected"


class TestNotificationEventSubscriber:
    def test_sends_notification_for_completed_event(self) -> None:
        mock_service = MagicMock()
        mock_service.send_notification = AsyncMock()
        subscriber = NotificationEventSubscriber(mock_service)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.send_notification.assert_called_once()
        call_kwargs = mock_service.send_notification.call_args.kwargs
        assert call_kwargs["event"] == "run_completed"
        assert call_kwargs["title"] == "Evaluation Completed"
        assert call_kwargs["channel"] == "webhook"
        assert "corr-456" in call_kwargs["metadata"]["correlation_id"]

    def test_sends_notification_for_failed_event(self) -> None:
        mock_service = MagicMock()
        mock_service.send_notification = AsyncMock()
        subscriber = NotificationEventSubscriber(mock_service)
        event = _FakeEvaluationFailedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.send_notification.assert_called_once()
        call_kwargs = mock_service.send_notification.call_args.kwargs
        assert call_kwargs["event"] == "run_failed"
        assert "API rate limit exceeded" in call_kwargs["message"]

    def test_sends_notification_for_finding_detected(self) -> None:
        mock_service = MagicMock()
        mock_service.send_notification = AsyncMock()
        subscriber = NotificationEventSubscriber(mock_service)
        event = _FakeFindingDetectedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.send_notification.assert_called_once()
        call_kwargs = mock_service.send_notification.call_args.kwargs
        assert call_kwargs["event"] == "attack_detected"
        assert "camp-99" in call_kwargs["message"]
        assert "jailbreak" in call_kwargs["message"]

    def test_skips_unmapped_event(self) -> None:
        mock_service = MagicMock()
        mock_service.send_notification = AsyncMock()
        subscriber = NotificationEventSubscriber(mock_service)

        @dataclass(frozen=True, slots=True)
        class _UnmappedEvent:
            event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
            occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
            correlation_id: str | None = None

            @property
            def event_type(self) -> str:
                return "evaluation.item.started"

        import asyncio

        asyncio.run(subscriber.handle(_UnmappedEvent()))

        mock_service.send_notification.assert_not_called()

    def test_handles_service_failure_gracefully(self) -> None:
        mock_service = MagicMock()
        mock_service.send_notification = AsyncMock(side_effect=RuntimeError("svc error"))
        subscriber = NotificationEventSubscriber(mock_service)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_service.send_notification.assert_called_once()
