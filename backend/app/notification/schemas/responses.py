"""Pydantic schemas for Notification API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SendNotificationRequest(BaseModel):
    """Request body for sending a notification."""

    channel: str
    event: str
    title: str = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1, max_length=5000)
    target: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    """Response for a notification."""

    notification_id: str
    organization_id: str
    user_id: str
    channel: str
    event: str
    title: str
    message: str
    metadata: dict[str, object] = Field(default_factory=dict)
    status: str
    target: str
    error_message: str | None = None
    retry_count: int = 0
    timestamp: str


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""

    items: list[NotificationResponse]
    total: int
    offset: int
    limit: int
