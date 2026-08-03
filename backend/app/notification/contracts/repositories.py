"""Repository contracts for Notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.notification.domain.entities import Notification, NotificationPreference


class NotificationRepository(ABC):
    """Abstract repository for Notifications."""

    @abstractmethod
    async def save(self, notification: Notification) -> None:
        """Persist a notification."""

    @abstractmethod
    async def find_by_id(self, notification_id: str) -> Notification | None:
        """Find a notification by ID."""

    @abstractmethod
    async def list_by_organization(
        self,
        organization_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Notification]:
        """List notifications for an organization."""

    @abstractmethod
    async def list_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Notification]:
        """List notifications for a user."""

    @abstractmethod
    async def count_by_organization(self, organization_id: str) -> int:
        """Count notifications for an organization."""


class NotificationPreferenceRepository(ABC):
    """Abstract repository for NotificationPreferences."""

    @abstractmethod
    async def save(self, pref: NotificationPreference, org_id: str, user_id: str) -> None:
        """Persist a notification preference."""

    @abstractmethod
    async def list_by_user(
        self,
        user_id: str,
    ) -> list[NotificationPreference]:
        """List notification preferences for a user."""

    @abstractmethod
    async def delete(self, user_id: str, channel: str, event: str) -> bool:
        """Delete a notification preference."""
