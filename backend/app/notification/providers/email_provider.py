"""Email notification provider (stub)."""

from __future__ import annotations

from structlog import get_logger

from app.notification.domain.entities import Notification
from app.notification.providers.base import NotificationProvider

logger = get_logger("redops_eval.notification.email")


class EmailNotificationProvider(NotificationProvider):
    """Email notification provider.

    In production, integrate with an email service (SendGrid, SES, etc.).
    """

    async def send(self, notification: Notification) -> bool:
        logger.info(
            "Sending email notification",
            to=notification.target,
            title=notification.title,
            event=notification.event,
        )
        return True

    def validate_target(self, target: str) -> bool:
        return "@" in target and "." in target
