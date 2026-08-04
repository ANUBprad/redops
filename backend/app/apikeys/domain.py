"""API Keys domain entities."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.kernel.entities.base import Entity, UUIDv7


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return f"ro_{secrets.token_urlsafe(32)}"


def hash_api_key(key: str) -> str:
    """SHA-256 hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKey(Entity):
    """API Key entity with rotation, expiration, and usage tracking."""

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        name: str,
        key_hash: str,
        prefix: str,
        user_id: str,
        organization_id: str | None = None,
        scopes: tuple[str, ...] = (),
        expires_at: datetime | None = None,
        last_used_at: datetime | None = None,
        usage_count: int = 0,
        is_active: bool = True,
        rotated_from: str | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        self._name = name.strip()
        self._key_hash = key_hash
        self._prefix = prefix
        self._user_id = user_id
        self._organization_id = organization_id
        self._scopes = scopes
        self._expires_at = expires_at
        self._last_used_at = last_used_at
        self._usage_count = usage_count
        self._is_active = is_active
        self._rotated_from = rotated_from

    @property
    def name(self) -> str:
        return self._name

    @property
    def key_hash(self) -> str:
        return self._key_hash

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def organization_id(self) -> str | None:
        return self._organization_id

    @property
    def scopes(self) -> tuple[str, ...]:
        return self._scopes

    @property
    def expires_at(self) -> datetime | None:
        return self._expires_at

    @property
    def last_used_at(self) -> datetime | None:
        return self._last_used_at

    @property
    def usage_count(self) -> int:
        return self._usage_count

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_expired(self) -> bool:
        if self._expires_at is None:
            return False
        return datetime.now(UTC) > self._expires_at

    @property
    def is_valid(self) -> bool:
        return self._is_active and not self.is_expired

    @property
    def rotated_from(self) -> str | None:
        return self._rotated_from

    def record_usage(self) -> None:
        self._last_used_at = datetime.now(UTC)
        self._usage_count += 1
        self.touch()

    def revoke(self) -> None:
        self._is_active = False
        self.touch()

    def activate(self) -> None:
        self._is_active = True
        self.touch()

    def update_expiry(self, expires_at: datetime | None) -> None:
        self._expires_at = expires_at
        self.touch()

    @classmethod
    def create(
        cls,
        *,
        name: str,
        user_id: str,
        organization_id: str | None = None,
        scopes: tuple[str, ...] = (),
        expires_in_days: int | None = None,
    ) -> tuple[ApiKey, str]:
        """Create a new API key. Returns (entity, raw_key)."""
        raw_key = generate_api_key()
        key_hash_value = hash_api_key(raw_key)
        prefix = raw_key[:12]
        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
        entity = cls(
            name=name,
            key_hash=key_hash_value,
            prefix=prefix,
            user_id=user_id,
            organization_id=organization_id,
            scopes=scopes,
            expires_at=expires_at,
        )
        return entity, raw_key


@dataclass(frozen=True, slots=True)
class ApiKeyUsageLog:
    """Log entry for API key usage."""

    api_key_id: str
    endpoint: str
    method: str
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
