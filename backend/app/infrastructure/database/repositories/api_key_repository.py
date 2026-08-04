"""SQLAlchemy repository implementation for API Keys."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.apikeys.contracts import ApiKeyRepository
from app.apikeys.domain import ApiKey
from app.infrastructure.database.models.api_key import ApiKeyModel
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyApiKeyRepository(ApiKeyRepository):
    """SQLAlchemy implementation of ApiKeyRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, api_key: ApiKey) -> None:
        model = ApiKeyModel(
            id=str(api_key.id),
            name=api_key.name,
            key_hash=api_key.key_hash,
            prefix=api_key.prefix,
            user_id=api_key.user_id,
            organization_id=api_key.organization_id,
            scopes=list(api_key.scopes),
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            usage_count=api_key.usage_count,
            is_active=api_key.is_active,
            rotated_from=api_key.rotated_from,
            created_at=api_key.created_at,
            updated_at=api_key.updated_at,
        )
        self._session.add(model)

    async def find_by_id(self, key_id: UUIDv7) -> ApiKey | None:
        stmt = select(ApiKeyModel).where(ApiKeyModel.id == str(key_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_key_hash(self, key_hash: str) -> ApiKey | None:
        stmt = select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_user(self, user_id: str) -> list[ApiKey]:
        stmt = (
            select(ApiKeyModel)
            .where(ApiKeyModel.user_id == user_id)
            .order_by(ApiKeyModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def list_by_organization(self, org_id: str) -> list[ApiKey]:
        stmt = (
            select(ApiKeyModel)
            .where(ApiKeyModel.organization_id == org_id)
            .order_by(ApiKeyModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def delete(self, key_id: UUIDv7) -> bool:
        stmt = select(ApiKeyModel).where(ApiKeyModel.id == str(key_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    async def delete_expired(self) -> int:
        now = datetime.now(UTC)
        stmt = select(ApiKeyModel).where(
            ApiKeyModel.expires_at.isnot(None),
            ApiKeyModel.expires_at < now,
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        for m in models:
            await self._session.delete(m)
        return len(models)

    @staticmethod
    def _to_domain(model: ApiKeyModel) -> ApiKey:
        return ApiKey(
            entity_id=UUIDv7.from_string(model.id),
            name=model.name,
            key_hash=model.key_hash,
            prefix=model.prefix,
            user_id=model.user_id,
            organization_id=model.organization_id,
            scopes=tuple(model.scopes),
            expires_at=model.expires_at,
            last_used_at=model.last_used_at,
            usage_count=model.usage_count,
            is_active=model.is_active,
            rotated_from=model.rotated_from,
        )
