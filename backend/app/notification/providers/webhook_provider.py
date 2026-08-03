"""Webhook notification provider."""

from __future__ import annotations

import json

import httpx
from structlog import get_logger

from app.notification.domain.entities import Notification
from app.notification.providers.base import NotificationProvider

logger = get_logger("redops_eval.notification.webhook")


class WebhookNotificationProvider(NotificationProvider):
    """Generic webhook notification provider."""

    async def send(self, notification: Notification) -> bool:
        if not notification.target:
            logger.warning("No webhook URL configured")
            return False
        payload = {
            "event": notification.event,
            "title": notification.title,
            "message": notification.message,
            "organization_id": notification.organization_id,
            "metadata": notification.metadata,
            "timestamp": notification.timestamp.isoformat(),
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    notification.target,
                    content=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                    timeout=10.0,
                )
                resp.raise_for_status()
                return True
        except Exception:
            logger.exception("Failed to send webhook notification")
            return False

    def validate_target(self, target: str) -> bool:
        return target.startswith("http://") or target.startswith("https://")
