"""Email verification and password reset token services."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.identity.services.auth_service import generate_token, hash_token
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import NotFoundError, UnauthorizedError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.identity.domain.entities import User


class EmailVerificationService:
    """Service for email verification token lifecycle."""

    TOKEN_TTL_HOURS = 24

    async def create_verification_token(
        self,
        session: AsyncSession,
        user: User,
    ) -> str:
        """Create and persist an email verification token. Returns raw token."""
        from app.infrastructure.database.models.identity import (
            EmailVerificationTokenModel,
        )

        raw_token = generate_token()
        token_hash = hash_token(raw_token)
        now = datetime.now(UTC)

        model = EmailVerificationTokenModel(
            id=str(UUIDv7.generate()),
            user_id=str(user.id),
            token_hash=token_hash,
            expires_at=now + timedelta(hours=self.TOKEN_TTL_HOURS),
        )
        session.add(model)
        return raw_token

    async def verify_token(
        self,
        session: AsyncSession,
        token: str,
    ) -> User:
        """Verify a token and mark the user's email as verified."""
        from sqlalchemy import select

        from app.infrastructure.database.models.identity import (
            EmailVerificationTokenModel,
            UserModel,
        )

        token_hash = hash_token(token)
        stmt = select(EmailVerificationTokenModel).where(
            EmailVerificationTokenModel.token_hash == token_hash,
        )
        result = await session.execute(stmt)
        token_model = result.scalar_one_or_none()

        if token_model is None:
            raise NotFoundError(message="Invalid verification token")

        if token_model.used_at is not None:
            raise UnauthorizedError(message="Verification token has already been used")

        if datetime.now(UTC) > token_model.expires_at:
            raise UnauthorizedError(message="Verification token has expired")

        token_model.used_at = datetime.now(UTC)

        user_stmt = select(UserModel).where(UserModel.id == token_model.user_id)
        user_result = await session.execute(user_stmt)
        user_model = user_result.scalar_one_or_none()

        if user_model is None:
            raise NotFoundError(message="User not found")

        if user_model.email_verified_at is None:
            user_model.email_verified_at = datetime.now(UTC)
            user_model.status = "active"

        from app.identity.domain.entities import User as UserEntity
        from app.identity.domain.enums import UserStatus

        return UserEntity(
            entity_id=UUIDv7.from_string(user_model.id),
            email=user_model.email,
            display_name=user_model.display_name,
            password_hash=user_model.password_hash,
            avatar_url=user_model.avatar_url,
            status=UserStatus(user_model.status),
            email_verified_at=user_model.email_verified_at,
            last_login_at=user_model.last_login_at,
            login_count=user_model.login_count,
        )


class PasswordResetService:
    """Service for password reset token lifecycle."""

    TOKEN_TTL_HOURS = 1

    async def create_reset_token(
        self,
        session: AsyncSession,
        user: User,
    ) -> str:
        """Create and persist a password reset token. Returns raw token."""
        from app.infrastructure.database.models.identity import PasswordResetTokenModel

        raw_token = generate_token()
        token_hash = hash_token(raw_token)
        now = datetime.now(UTC)

        model = PasswordResetTokenModel(
            id=str(UUIDv7.generate()),
            user_id=str(user.id),
            token_hash=token_hash,
            expires_at=now + timedelta(hours=self.TOKEN_TTL_HOURS),
        )
        session.add(model)
        return raw_token

    async def reset_password(
        self,
        session: AsyncSession,
        token: str,
        new_password: str,
    ) -> None:
        """Verify token and reset the user's password."""
        from sqlalchemy import select

        from app.identity.services.auth_service import hash_password
        from app.infrastructure.database.models.identity import (
            PasswordResetTokenModel,
            RefreshTokenModel,
            UserModel,
        )

        token_hash = hash_token(token)
        stmt = select(PasswordResetTokenModel).where(
            PasswordResetTokenModel.token_hash == token_hash,
        )
        result = await session.execute(stmt)
        token_model = result.scalar_one_or_none()

        if token_model is None:
            raise NotFoundError(message="Invalid password reset token")

        if token_model.used_at is not None:
            raise UnauthorizedError(message="Password reset token has already been used")

        if datetime.now(UTC) > token_model.expires_at:
            raise UnauthorizedError(message="Password reset token has expired")

        token_model.used_at = datetime.now(UTC)

        user_stmt = select(UserModel).where(UserModel.id == token_model.user_id)
        user_result = await session.execute(user_stmt)
        user_model = user_result.scalar_one_or_none()

        if user_model is None:
            raise NotFoundError(message="User not found")

        user_model.password_hash = hash_password(new_password)

        revoke_stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == user_model.id,
            RefreshTokenModel.revoked_at.is_(None),
        )
        revoke_result = await session.execute(revoke_stmt)
        for rt in revoke_result.scalars().all():
            rt.revoked_at = datetime.now(UTC)
