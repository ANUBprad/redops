"""Slack notification provider (stub)."""

from __future__ import annotations

import httpx
from structlog import get_logger

from app.notification.domain.entities import Notification
from app.notification.providers.base import NotificationProvider

logger = get_logger("redops_eval.notification.slack")


class SlackNotificationProvider(NotificationProvider):
    """Slack notification provider via incoming webhook."""

    async def send(self, notification: Notification) -> bool:
        if not notification.target:
            logger.warning("No Slack webhook URL configured")
            return False
        payload = {
            "text": f"*{notification.title}*\n{notification.message}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{notification.title}*\n{notification.message}",
                    },
                },
            ],
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    notification.target,
                    json=payload,
                    timeout=10.0,
                )
                resp.raise_for_status()
                return True
        except Exception:
            logger.exception("Failed to send Slack notification")
            return False

    def validate_target(self, target: str) -> bool:
        return target.startswith("https://hooks.slack.com/")
