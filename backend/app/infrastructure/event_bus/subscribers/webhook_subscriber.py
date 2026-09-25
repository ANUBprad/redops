"""Webhook delivery subscriber — delivers events to external webhook endpoints.

Consumes domain events from the EventBus and POSTs JSON payloads to
registered external webhook endpoints using the existing
WebhookNotificationProvider infrastructure for HTTP delivery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog import get_logger

from app.notification.domain.entities import Notification

if TYPE_CHECKING:
    from app.notification.providers.webhook_provider import WebhookNotificationProvider

logger = get_logger("redops_eval.event_subscribers.webhook")


class WebhookDeliverySubscriber:
    """Delivers domain events to registered external webhook endpoints.

    Maintains a mapping of event types to lists of webhook URLs. When
    an event matching a registered type arrives, it is serialized to
    JSON and POSTed to each registered endpoint via the existing
    WebhookNotificationProvider.
    """

    def __init__(
        self,
        webhook_provider: WebhookNotificationProvider,
        endpoint_registry: dict[str, list[str]] | None = None,
    ) -> None:
        self._webhook_provider = webhook_provider
        self._endpoint_registry: dict[str, list[str]] = endpoint_registry or {}

    def register_endpoint(self, event_type: str, url: str) -> None:
        """Register a webhook URL for a specific event type."""
        if event_type not in self._endpoint_registry:
            self._endpoint_registry[event_type] = []
        if url not in self._endpoint_registry[event_type]:
            self._endpoint_registry[event_type].append(url)

    def unregister_endpoint(self, event_type: str, url: str) -> None:
        """Unregister a webhook URL for a specific event type."""
        urls = self._endpoint_registry.get(event_type, [])
        self._endpoint_registry[event_type] = [u for u in urls if u != url]

    @property
    def endpoint_registry(self) -> dict[str, list[str]]:
        return dict(self._endpoint_registry)

    async def handle(self, event: Any) -> None:
        """Handle a domain event by delivering it to registered webhooks."""
        event_type = getattr(event, "event_type", None)
        if event_type is None:
            return

        urls = self._endpoint_registry.get(event_type, [])
        if not urls:
            return

        for url in urls:
            notification = Notification.create(
                organization_id="system",
                user_id="system",
                channel="webhook",
                event=event_type,
                title=f"Event: {event_type}",
                message=self._build_payload(event, event_type),
                target=url,
                metadata={
                    "event_type": event_type,
                    "correlation_id": getattr(event, "correlation_id", None) or "",
                },
            )
            try:
                success = await self._webhook_provider.send(notification)
                if not success:
                    logger.warning(
                        "Webhook delivery returned False",
                        event_type=event_type,
                        url=url,
                    )
            except Exception:
                logger.exception(
                    "Webhook delivery failed",
                    event_type=event_type,
                    url=url,
                )

    @staticmethod
    def _build_payload(event: Any, event_type: str) -> str:
        """Build a JSON payload string from the event."""
        import json

        payload: dict[str, Any] = {
            "event_type": event_type,
            "event_id": str(getattr(event, "event_id", "")),
            "occurred_at": getattr(event, "occurred_at", ""),
        }
        if hasattr(payload["occurred_at"], "isoformat"):
            payload["occurred_at"] = payload["occurred_at"].isoformat()

        correlation_id = getattr(event, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id

        for attr in (
            "run_id",
            "item_id",
            "items_total",
            "items_completed",
            "items_passed",
            "items_violated",
            "error_code",
            "error_message",
            "metric_name",
            "score",
            "campaign_id",
            "attack_category",
            "severity",
            "verdict",
            "violation_count",
            "total_rounds",
            "cost_summary",
        ):
            val = getattr(event, attr, None)
            if val is not None:
                payload[attr] = str(val) if not isinstance(val, (int, float, bool, dict)) else val

        return json.dumps(payload, default=str)
