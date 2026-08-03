"""Tests for Notification domain entity."""

from app.notification.domain.entities import (
    Notification,
    NotificationChannel,
    NotificationEvent,
    NotificationStatus,
)


def test_notification_create() -> None:
    n = Notification.create(
        organization_id="org-1",
        user_id="user-1",
        channel=NotificationChannel.EMAIL.value,
        event=NotificationEvent.RUN_COMPLETED.value,
        title="Run Completed",
        message="Your evaluation run has completed successfully.",
        target="user@example.com",
    )
    assert n.organization_id == "org-1"
    assert n.channel == "email"
    assert n.event == "run_completed"
    assert n.status == NotificationStatus.PENDING.value


def test_notification_mark_sent() -> None:
    n = Notification.create(
        organization_id="org-1",
        user_id="user-1",
        channel=NotificationChannel.SLACK.value,
        event=NotificationEvent.ATTACK_DETECTED.value,
        title="Attack Detected",
        message="A prompt injection attack was detected.",
    )
    sent = n.mark_sent()
    assert sent.status == NotificationStatus.SENT.value
    assert sent.notification_id == n.notification_id


def test_notification_mark_failed() -> None:
    n = Notification.create(
        organization_id="org-1",
        user_id="user-1",
        channel=NotificationChannel.WEBHOOK.value,
        event=NotificationEvent.REPORT_GENERATED.value,
        title="Report Generated",
        message="Your report is ready.",
    )
    failed = n.mark_failed("Connection timeout")
    assert failed.status == NotificationStatus.FAILED.value
    assert failed.error_message == "Connection timeout"
    assert failed.retry_count == 1


def test_notification_channels() -> None:
    channels = {c.value for c in NotificationChannel}
    assert "email" in channels
    assert "slack" in channels
    assert "teams" in channels
    assert "discord" in channels
    assert "webhook" in channels


def test_notification_events() -> None:
    events = {e.value for e in NotificationEvent}
    assert "run_completed" in events
    assert "run_failed" in events
    assert "safety_regression" in events
    assert "attack_detected" in events
    assert "report_generated" in events
