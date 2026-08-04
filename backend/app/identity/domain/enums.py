"""Identity domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    """User account status."""

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class OAuthProvider(StrEnum):
    """Supported OAuth providers."""

    GITHUB = "github"
    GOOGLE = "google"


class TokenType(StrEnum):
    """JWT token types."""

    ACCESS = "access"
    REFRESH = "refresh"
