"""Tests for WebhookDeliverySubscriber."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.event_bus.subscribers.webhook_subscriber import (
    WebhookDeliverySubscriber,
)
from app.kernel.entities.base import UUIDv7


@dataclass(frozen=True, slots=True)
class _FakeEvaluationCompletedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = "corr-789"
    run_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    items_completed: int = 8
    items_total: int = 8
    duration_ms: int = 4000

    @property
    def event_type(self) -> str:
        return "evaluation.completed"


@dataclass(frozen=True, slots=True)
class _FakeCampaignCompletedEvent:
    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    campaign_id: str = "camp-abc"
    state: str = "completed"
    total_rounds: int = 5
    violation_count: int = 2
    cost_summary: dict[str, object] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return "safety.campaign.completed"


class TestWebhookDeliverySubscriber:
    def test_delivers_to_registered_endpoints(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=True)
        subscriber = WebhookDeliverySubscriber(
            mock_provider,
            endpoint_registry={"evaluation.completed": ["https://example.com/hook"]},
        )
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_provider.send.assert_called_once()
        call_args = mock_provider.send.call_args
        notification = call_args[0][0]
        assert notification.target == "https://example.com/hook"
        assert notification.event == "evaluation.completed"

    def test_no_delivery_when_no_endpoints_registered(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=True)
        subscriber = WebhookDeliverySubscriber(mock_provider)
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_provider.send.assert_not_called()

    def test_delivers_to_multiple_endpoints(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=True)
        subscriber = WebhookDeliverySubscriber(
            mock_provider,
            endpoint_registry={
                "evaluation.completed": [
                    "https://a.example.com/hook",
                    "https://b.example.com/hook",
                ],
            },
        )
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        assert mock_provider.send.call_count == 2

    def test_register_and_unregister_endpoint(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=True)
        subscriber = WebhookDeliverySubscriber(mock_provider)

        subscriber.register_endpoint("test.event", "https://example.com/hook1")
        subscriber.register_endpoint("test.event", "https://example.com/hook2")
        assert len(subscriber.endpoint_registry["test.event"]) == 2

        subscriber.unregister_endpoint("test.event", "https://example.com/hook1")
        assert len(subscriber.endpoint_registry["test.event"]) == 1
        assert subscriber.endpoint_registry["test.event"][0] == "https://example.com/hook2"

    def test_duplicate_endpoint_not_added(self) -> None:
        mock_provider = MagicMock()
        subscriber = WebhookDeliverySubscriber(mock_provider)

        subscriber.register_endpoint("test.event", "https://example.com/hook")
        subscriber.register_endpoint("test.event", "https://example.com/hook")
        assert len(subscriber.endpoint_registry["test.event"]) == 1

    def test_handles_provider_failure_gracefully(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=False)
        subscriber = WebhookDeliverySubscriber(
            mock_provider,
            endpoint_registry={"evaluation.completed": ["https://example.com/hook"]},
        )
        event = _FakeEvaluationCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        mock_provider.send.assert_called_once()

    def test_skips_event_without_event_type(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=True)
        subscriber = WebhookDeliverySubscriber(mock_provider)

        import asyncio

        asyncio.run(subscriber.handle("not_an_event"))

        mock_provider.send.assert_not_called()

    def test_payload_contains_event_data(self) -> None:
        mock_provider = MagicMock()
        mock_provider.send = AsyncMock(return_value=True)
        subscriber = WebhookDeliverySubscriber(
            mock_provider,
            endpoint_registry={"safety.campaign.completed": ["https://example.com/hook"]},
        )
        event = _FakeCampaignCompletedEvent()

        import asyncio

        asyncio.run(subscriber.handle(event))

        call_kwargs = mock_provider.send.call_args.kwargs
        notification = call_kwargs.get("notification") or mock_provider.send.call_args[0][0]
        import json

        payload = json.loads(notification.message)
        assert payload["event_type"] == "safety.campaign.completed"
        assert payload["campaign_id"] == "camp-abc"
        assert payload["violation_count"] == 2
