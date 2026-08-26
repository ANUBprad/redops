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
    def _make_session_factory(self, send_mock: AsyncMock) -> MagicMock:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.execute = AsyncMock()
        factory = MagicMock(return_value=mock_session)
        return factory, mock_session

    def test_sends_notification_for_completed_event(self) -> None:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.execute = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)

        subscriber = NotificationEventSubscriber(session_factory)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_session.commit.assert_awaited_once()
        mock_session.add.assert_called_once()

    def test_sends_notification_for_failed_event(self) -> None:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.execute = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)

        subscriber = NotificationEventSubscriber(session_factory)
        event = _FakeEvaluationFailedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_session.commit.assert_awaited_once()
        model = mock_session.add.call_args[0][0]
        assert "API rate limit exceeded" in model.message

    def test_sends_notification_for_finding_detected(self) -> None:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.execute = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)

        subscriber = NotificationEventSubscriber(session_factory)
        event = _FakeFindingDetectedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_session.commit.assert_awaited_once()
        model = mock_session.add.call_args[0][0]
        assert "camp-99" in model.message
        assert "jailbreak" in model.message

    def test_skips_unmapped_event(self) -> None:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        session_factory = MagicMock(return_value=mock_session)

        subscriber = NotificationEventSubscriber(session_factory)

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

        mock_session.add.assert_not_called()

    def test_rolls_back_on_failure(self) -> None:
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session.add = MagicMock(side_effect=RuntimeError("db error"))
        session_factory = MagicMock(return_value=mock_session)

        subscriber = NotificationEventSubscriber(session_factory)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
