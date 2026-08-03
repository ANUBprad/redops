"""Base notification provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.notification.domain.entities import Notification


class NotificationProvider(ABC):
    """Abstract base for notification channel providers."""

    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True on success."""

    @abstractmethod
    def validate_target(self, target: str) -> bool:
        """Validate that a target string is valid for this channel."""
