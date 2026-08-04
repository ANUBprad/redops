"""Notification service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.notification.contracts.repositories import (
    NotificationRepository,
)
from app.notification.domain.entities import (
    Notification,
    NotificationChannel,
)
from app.notification.providers.email_provider import EmailNotificationProvider
from app.notification.providers.slack_provider import SlackNotificationProvider
from app.notification.providers.webhook_provider import WebhookNotificationProvider

if TYPE_CHECKING:
    from app.notification.providers.base import NotificationProvider


_PROVIDER_MAP: dict[str, type[NotificationProvider]] = {
    NotificationChannel.EMAIL.value: EmailNotificationProvider,
    NotificationChannel.SLACK.value: SlackNotificationProvider,
    NotificationChannel.WEBHOOK.value: WebhookNotificationProvider,
}


class NotificationService:
    """Service for sending and managing notifications."""

    def __init__(self, repo: NotificationRepository) -> None:
        self._repo = repo
        self._providers: dict[str, NotificationProvider] = {}
        for channel, cls in _PROVIDER_MAP.items():
            self._providers[channel] = cls()

    def _get_provider(self, channel: str) -> NotificationProvider:
        provider = self._providers.get(channel)
        if provider is None:
            from app.kernel.exceptions.errors import ValidationError

            raise ValidationError(
                message=f"Unsupported notification channel: {channel}",
                field="channel",
            )
        return provider

    async def send_notification(
        self,
        *,
        organization_id: str,
        user_id: str,
        channel: str,
        event: str,
        title: str,
        message: str,
        target: str = "",
        metadata: dict[str, object] | None = None,
    ) -> Notification:
        """Create and send a notification."""
        notification = Notification.create(
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            event=event,
            title=title,
            message=message,
            target=target,
            metadata=metadata,
        )
        provider = self._get_provider(channel)
        try:
            success = await provider.send(notification)
            if success:
                notification = notification.mark_sent()
            else:
                notification = notification.mark_failed("Provider returned False")
        except Exception as exc:
            notification = notification.mark_failed(str(exc))
        await self._repo.save(notification)
        return notification

    async def list_organization_notifications(
        self,
        organization_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Notification]:
        return await self._repo.list_by_organization(
            organization_id,
            offset=offset,
            limit=limit,
        )

    async def list_user_notifications(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Notification]:
        return await self._repo.list_by_user(user_id, offset=offset, limit=limit)

    async def count_organization_notifications(
        self,
        organization_id: str,
    ) -> int:
        return await self._repo.count_by_organization(organization_id)
