"""Repository contract for API Keys."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.apikeys.domain import ApiKey
    from app.kernel.entities.base import UUIDv7


class ApiKeyRepository(ABC):
    """Abstract repository for API Key entities."""

    @abstractmethod
    async def save(self, api_key: ApiKey) -> None:
        """Persist an API key."""

    @abstractmethod
    async def find_by_id(self, key_id: UUIDv7) -> ApiKey | None:
        """Find an API key by ID."""

    @abstractmethod
    async def find_by_key_hash(self, key_hash: str) -> ApiKey | None:
        """Find an API key by its hash."""

    @abstractmethod
    async def list_by_user(self, user_id: str) -> list[ApiKey]:
        """List API keys for a user."""

    @abstractmethod
    async def list_by_organization(self, org_id: str) -> list[ApiKey]:
        """List API keys for an organization."""

    @abstractmethod
    async def delete(self, key_id: UUIDv7) -> bool:
        """Delete an API key."""

    @abstractmethod
    async def delete_expired(self) -> int:
        """Delete expired keys. Returns count deleted."""
