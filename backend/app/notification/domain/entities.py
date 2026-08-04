"""Notification domain entities and value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from app.kernel.entities.base import UUIDv7


class NotificationChannel(StrEnum):
    """Supported notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    WEBHOOK = "webhook"


class NotificationEvent(StrEnum):
    """Events that trigger notifications."""

    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    SAFETY_REGRESSION = "safety_regression"
    ATTACK_DETECTED = "attack_detected"
    REPORT_GENERATED = "report_generated"
    INVITATION_SENT = "invitation_sent"
    MEMBER_JOINED = "member_joined"
    MEMBER_REMOVED = "member_removed"
    SCHEDULE_FAILED = "schedule_failed"


class NotificationStatus(StrEnum):
    """Status of a notification."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass(frozen=True, slots=True)
class NotificationPreference:
    """User or org notification preferences."""

    channel: str
    event: str
    enabled: bool = True
    target: str = ""  # email address, Slack channel ID, webhook URL, etc.


@dataclass(frozen=True, slots=True)
class Notification:
    """Notification entity."""

    notification_id: str = field(default_factory=lambda: str(UUIDv7.generate()))
    organization_id: str = ""
    user_id: str = ""
    channel: str = ""
    event: str = ""
    title: str = ""
    message: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    status: str = NotificationStatus.PENDING.value
    target: str = ""
    error_message: str | None = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
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
        return cls(
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            event=event,
            title=title,
            message=message,
            target=target,
            metadata=metadata or {},
        )

    def mark_sent(self) -> Notification:
        return Notification(
            notification_id=self.notification_id,
            organization_id=self.organization_id,
            user_id=self.user_id,
            channel=self.channel,
            event=self.event,
            title=self.title,
            message=self.message,
            metadata=self.metadata,
            status=NotificationStatus.SENT.value,
            target=self.target,
            timestamp=self.timestamp,
        )

    def mark_failed(self, error: str) -> Notification:
        return Notification(
            notification_id=self.notification_id,
            organization_id=self.organization_id,
            user_id=self.user_id,
            channel=self.channel,
            event=self.event,
            title=self.title,
            message=self.message,
            metadata=self.metadata,
            status=NotificationStatus.FAILED.value,
            target=self.target,
            error_message=error,
            retry_count=self.retry_count + 1,
            timestamp=self.timestamp,
        )
