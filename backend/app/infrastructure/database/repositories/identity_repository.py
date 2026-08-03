"""SQLAlchemy repository implementation for Identity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.identity.contracts.repositories import RefreshTokenRepository, UserRepository
from app.identity.domain.entities import RefreshToken, User
from app.identity.domain.enums import UserStatus
from app.infrastructure.database.models.identity import (
    RefreshTokenModel,
    UserModel,
)
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of UserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: User) -> None:
        model = self._to_model(user)
        self._session.add(model)

    async def find_by_id(self, user_id: UUIDv7) -> User | None:
        stmt = select(UserModel).where(UserModel.id == str(user_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email.lower().strip())
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def exists_by_email(self, email: str) -> bool:
        stmt = select(UserModel.id).where(UserModel.email == email.lower().strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_users(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[User]:
        stmt = select(UserModel).order_by(UserModel.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_users(self) -> int:
        stmt = select(func.count()).select_from(UserModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _to_model(user: User) -> UserModel:
        return UserModel(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            password_hash=user.password_hash,
            avatar_url=user.avatar_url,
            status=user.status.value,
            email_verified_at=user.email_verified_at,
            last_login_at=user.last_login_at,
            login_count=user.login_count,
            version=user.version,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            entity_id=UUIDv7.from_string(model.id),
            email=model.email,
            display_name=model.display_name,
            password_hash=model.password_hash,
            avatar_url=model.avatar_url,
            status=UserStatus(model.status),
            email_verified_at=model.email_verified_at,
            last_login_at=model.last_login_at,
            login_count=model.login_count,
        )


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    """SQLAlchemy implementation of RefreshTokenRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, token: RefreshToken) -> None:
        model = RefreshTokenModel(
            id=token.token_id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            revoked_at=token.revoked_at,
            replaced_by_token_id=token.replaced_by_token_id,
            created_at=token.created_at,
        )
        self._session.add(model)

    async def find_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return RefreshToken(
            token_id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            created_at=model.created_at,
            revoked_at=model.revoked_at,
            replaced_by_token_id=model.replaced_by_token_id,
        )

    async def revoke_by_user_id(self, user_id: str) -> int:
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked_at.is_(None),
        )
        result = await self._session.execute(stmt)
        tokens = list(result.scalars().all())
        now = datetime.now(UTC)
        for token in tokens:
            token.revoked_at = now
        return len(tokens)

    async def revoke_by_token_hash(self, token_hash: str) -> None:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            model.revoked_at = datetime.now(UTC)

    async def delete_expired(self, before: datetime) -> int:
        stmt = select(RefreshTokenModel).where(RefreshTokenModel.expires_at < before)
        result = await self._session.execute(stmt)
        tokens = list(result.scalars().all())
        for token in tokens:
            await self._session.delete(token)
        return len(tokens)
