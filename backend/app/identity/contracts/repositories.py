"""Repository contracts for the Identity domain."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from app.identity.domain.entities import RefreshToken, User
    from app.kernel.entities.base import UUIDv7


class UserRepository(ABC):
    """Abstract repository for User aggregates."""

    @abstractmethod
    async def save(self, user: User) -> None:
        """Persist a user aggregate."""

    @abstractmethod
    async def find_by_id(self, user_id: UUIDv7) -> User | None:
        """Find a user by ID."""

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None:
        """Find a user by email address."""

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """Check if a user with the given email exists."""

    @abstractmethod
    async def list_users(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """List users with pagination."""

    @abstractmethod
    async def count_users(self) -> int:
        """Count total users."""


class RefreshTokenRepository(ABC):
    """Abstract repository for refresh tokens."""

    @abstractmethod
    async def save(self, token: RefreshToken) -> None:
        """Persist a refresh token."""

    @abstractmethod
    async def find_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Find a refresh token by its hash."""

    @abstractmethod
    async def revoke_by_user_id(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user. Returns count revoked."""

    @abstractmethod
    async def revoke_by_token_hash(self, token_hash: str) -> None:
        """Revoke a specific refresh token."""

    @abstractmethod
    async def delete_expired(self, before: datetime) -> int:
        """Delete expired tokens. Returns count deleted."""
