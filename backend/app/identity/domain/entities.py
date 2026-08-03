"""Identity domain entities.

Represents Users, RefreshTokens, and OAuth accounts as aggregate roots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.identity.domain.enums import OAuthProvider, UserStatus
from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin


class User(AggregateRoot, VersionMixin):
    """User aggregate root."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        email: str,
        display_name: str,
        password_hash: str | None = None,
        avatar_url: str | None = None,
        status: UserStatus = UserStatus.PENDING_VERIFICATION,
        email_verified_at: datetime | None = None,
        last_login_at: datetime | None = None,
        login_count: int = 0,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._email = email.lower().strip()
        self._display_name = display_name.strip()
        self._password_hash = password_hash
        self._avatar_url = avatar_url
        self._status = status
        self._email_verified_at = email_verified_at
        self._last_login_at = last_login_at
        self._login_count = login_count

    @property
    def email(self) -> str:
        return self._email

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def password_hash(self) -> str | None:
        return self._password_hash

    @property
    def avatar_url(self) -> str | None:
        return self._avatar_url

    @property
    def status(self) -> UserStatus:
        return self._status

    @property
    def email_verified_at(self) -> datetime | None:
        return self._email_verified_at

    @property
    def last_login_at(self) -> datetime | None:
        return self._last_login_at

    @property
    def login_count(self) -> int:
        return self._login_count

    @property
    def is_active(self) -> bool:
        return self._status == UserStatus.ACTIVE

    @property
    def is_email_verified(self) -> bool:
        return self._email_verified_at is not None

    def verify_email(self) -> None:
        if self._email_verified_at is not None:
            return
        self._email_verified_at = datetime.now(UTC)
        if self._status == UserStatus.PENDING_VERIFICATION:
            self._status = UserStatus.ACTIVE
        self.touch()
        self.increment_version()

    def record_login(self) -> None:
        self._last_login_at = datetime.now(UTC)
        self._login_count += 1
        self.touch()

    def set_password_hash(self, password_hash: str) -> None:
        self._password_hash = password_hash
        self.touch()
        self.increment_version()

    def update_profile(
        self,
        *,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> None:
        if display_name is not None:
            self._display_name = display_name.strip()
        if avatar_url is not None:
            self._avatar_url = avatar_url
        self.touch()
        self.increment_version()

    def suspend(self) -> None:
        self._status = UserStatus.SUSPENDED
        self.touch()
        self.increment_version()

    def deactivate(self) -> None:
        self._status = UserStatus.DEACTIVATED
        self.touch()
        self.increment_version()

    def activate(self) -> None:
        self._status = UserStatus.ACTIVE
        self.touch()
        self.increment_version()

    @classmethod
    def create(
        cls,
        *,
        email: str,
        display_name: str,
        password_hash: str | None = None,
    ) -> User:
        user = cls(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            status=UserStatus.PENDING_VERIFICATION,
        )
        return user


@dataclass(frozen=True, slots=True)
class RefreshToken:
    """Refresh token value object."""

    token_id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revoked_at: datetime | None = None
    replaced_by_token_id: str | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_revoked


@dataclass(frozen=True, slots=True)
class OAuthAccount:
    """OAuth account linkage."""

    provider: OAuthProvider
    provider_user_id: str
    user_id: str
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
