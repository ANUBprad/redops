"""Notification event subscriber — dispatches notifications on domain events.

Consumes domain events from the EventBus and dispatches notifications
through the existing NotificationService, using configured channels
(email, Slack, webhook) based on notification preferences.

Each event creates a fresh database session to ensure proper
transaction boundaries and prevent session leaks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from structlog import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncSessionFactory

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("redops_eval.event_subscribers.notification")


_NOTIFICATION_MAP: dict[str, dict[str, str]] = {
    "evaluation.completed": {
        "event": "run_completed",
        "title": "Evaluation Completed",
        "message_template": "Evaluation run {run_id} completed successfully.",
    },
    "evaluation.failed": {
        "event": "run_failed",
        "title": "Evaluation Failed",
        "message_template": "Evaluation run {run_id} failed: {error_message}",
    },
    "safety.finding.detected": {
        "event": "attack_detected",
        "title": "Safety Finding Detected",
        "message_template": (
            "Finding detected in campaign {campaign_id}: {attack_category} — severity {severity}"
        ),
    },
    "safety.campaign.completed": {
        "event": "safety_regression",
        "title": "Red Team Campaign Completed",
        "message_template": (
            "Campaign {campaign_id} completed with "
            "{violation_count} violations across {total_rounds} rounds."
        ),
    },
}


class NotificationEventSubscriber:
    """Subscribes to domain events and dispatches notifications.

    Maps selected domain events to notification templates and sends
    them through the existing NotificationService. Events not in the
    mapping are silently skipped.

    A fresh database session is created per event to ensure proper
    transaction boundaries.
    """

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def handle(self, event: Any) -> None:
        """Handle a domain event by dispatching a notification."""
        event_type = getattr(event, "event_type", None)
        if event_type is None:
            return

        mapping = _NOTIFICATION_MAP.get(event_type)
        if mapping is None:
            return

        message = self._format_message(mapping["message_template"], event)
        correlation_id = getattr(event, "correlation_id", None)
        metadata: dict[str, object] = {"event_type": event_type}
        if correlation_id:
            metadata["correlation_id"] = correlation_id

        from app.infrastructure.database.repositories.notification_repository import (
            SqlAlchemyNotificationRepository,
        )
        from app.notification.services.notification_service import NotificationService

        session: AsyncSession = self._session_factory()
        try:
            repo = SqlAlchemyNotificationRepository(session)
            notif_service = NotificationService(repo)
            await notif_service.send_notification(
                organization_id="system",
                user_id="system",
                channel="webhook",
                event=mapping["event"],
                title=mapping["title"],
                message=message,
                metadata=metadata,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to dispatch notification for event",
                event_type=event_type,
            )
        finally:
            await session.close()

    @staticmethod
    def _format_message(template: str, event: Any) -> str:
        values: dict[str, str] = {}
        for attr in (
            "run_id",
            "error_message",
            "campaign_id",
            "attack_category",
            "severity",
            "violation_count",
            "total_rounds",
        ):
            val = getattr(event, attr, None)
            if val is not None:
                values[attr] = str(val)
        try:
            return template.format(**values)
        except KeyError:
            return template
