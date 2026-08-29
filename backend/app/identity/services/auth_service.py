"""Authentication service. JWT, password hashing, token management."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_config
from app.identity.contracts.repositories import RefreshTokenRepository, UserRepository
from app.identity.domain.entities import RefreshToken, User
from app.identity.domain.enums import UserStatus
from app.kernel.entities.base import UUIDv7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    result: str = pwd_context.hash(password)
    return result


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    result: bool = pwd_context.verify(plain_password, hashed_password)
    return result


def hash_token(token: str) -> str:
    """SHA-256 hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)


class AuthService:
    """Authentication service handling JWT and password operations."""

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
    ) -> None:
        self._user_repo = user_repo
        self._refresh_token_repo = refresh_token_repo
        self._config = get_config()

    def _get_secret_key(self) -> str:
        return self._config.app_secret_key

    def _get_algorithm(self) -> str:
        return "HS256"

    def _get_access_token_ttl(self) -> int:
        return 3600  # 1 hour

    def _get_refresh_token_ttl(self) -> int:
        return 30 * 24 * 3600  # 30 days

    def create_access_token(
        self,
        user: User,
        org_id: str | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a JWT access token."""
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": str(user.id),
            "email": user.email,
            "name": user.display_name,
            "status": user.status.value,
            "iat": now,
            "exp": now + timedelta(seconds=self._get_access_token_ttl()),
            "type": "access",
        }
        if org_id is not None:
            payload["org_id"] = org_id
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, self._get_secret_key(), algorithm=self._get_algorithm())

    def create_refresh_token(self, user: User) -> tuple[str, RefreshToken]:
        """Create a refresh token. Returns (raw_token, domain_entity)."""
        raw_token = generate_token()
        token_hash_value = hash_token(raw_token)
        now = datetime.now(UTC)
        refresh_token = RefreshToken(
            token_id=str(UUIDv7.generate()),
            user_id=str(user.id),
            token_hash=token_hash_value,
            expires_at=now + timedelta(seconds=self._get_refresh_token_ttl()),
            created_at=now,
        )
        return raw_token, refresh_token

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT access token."""
        result: dict[str, Any] = jwt.decode(
            token,
            self._get_secret_key(),
            algorithms=[self._get_algorithm()],
        )
        return result

    async def register(
        self,
        email: str,
        display_name: str,
        password: str,
    ) -> User:
        """Register a new user."""
        if await self._user_repo.exists_by_email(email):
            from app.kernel.exceptions.errors import ConflictError

            raise ConflictError(
                message="A user with this email already exists",
                details={"email": email},
            )
        password_hash = hash_password(password)
        user = User.create(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
        )
        await self._user_repo.save(user)
        return user

    async def authenticate(
        self,
        email: str,
        password: str,
    ) -> User:
        """Authenticate with email and password."""
        user = await self._user_repo.find_by_email(email)
        if user is None:
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(message="Invalid email or password")
        if user.password_hash is None:
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(
                message="This account uses OAuth login. Please sign in with your provider.",
            )
        if not verify_password(password, user.password_hash):
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(message="Invalid email or password")
        if user.status == UserStatus.SUSPENDED:
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(message="Account is suspended")
        if user.status == UserStatus.DEACTIVATED:
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(message="Account is deactivated")
        user.record_login()
        return user

    async def refresh_tokens(
        self,
        refresh_token_raw: str,
    ) -> tuple[str, RefreshToken, User]:
        """Refresh access and refresh tokens. Returns (new_access, new_refresh, user)."""
        token_hash_value = hash_token(refresh_token_raw)
        stored_token = await self._refresh_token_repo.find_by_token_hash(token_hash_value)
        if stored_token is None or not stored_token.is_valid:
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(message="Invalid or expired refresh token")
        user = await self._user_repo.find_by_id(UUIDv7.from_string(stored_token.user_id))
        if user is None or user.status != UserStatus.ACTIVE:
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(message="User account is not active")
        # Revoke old token
        await self._refresh_token_repo.revoke_by_token_hash(token_hash_value)
        # Create new tokens
        new_access = self.create_access_token(user)
        _new_raw_refresh, new_refresh_entity = self.create_refresh_token(user)
        await self._refresh_token_repo.save(new_refresh_entity)
        return new_access, new_refresh_entity, user

    async def logout_all(self, user_id: str) -> int:
        """Revoke all refresh tokens for a user."""
        return await self._refresh_token_repo.revoke_by_user_id(user_id)

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change a user's password."""
        if user.password_hash is None:
            from app.kernel.exceptions.errors import ConflictError

            raise ConflictError(message="This account uses OAuth login")
        if not verify_password(current_password, user.password_hash):
            from app.kernel.exceptions.errors import UnauthorizedError

            raise UnauthorizedError(message="Current password is incorrect")
        new_hash = hash_password(new_password)
        user.set_password_hash(new_hash)
        await self._user_repo.save(user)
        # Revoke all refresh tokens on password change
        await self._refresh_token_repo.revoke_by_user_id(str(user.id))

    async def reset_password(
        self,
        user: User,
        new_password: str,
    ) -> None:
        """Reset a user's password (admin or token-based)."""
        new_hash = hash_password(new_password)
        user.set_password_hash(new_hash)
        await self._user_repo.save(user)
        await self._refresh_token_repo.revoke_by_user_id(str(user.id))
