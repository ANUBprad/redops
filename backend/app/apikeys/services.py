"""API Keys service."""

from __future__ import annotations

from app.apikeys.contracts import ApiKeyRepository
from app.apikeys.domain import ApiKey, hash_api_key
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import NotFoundError, UnauthorizedError


class ApiKeyService:
    """Service for API key operations."""

    def __init__(self, repo: ApiKeyRepository) -> None:
        self._repo = repo

    async def create_key(
        self,
        *,
        name: str,
        user_id: str,
        organization_id: str | None = None,
        scopes: tuple[str, ...] = (),
        expires_in_days: int | None = None,
    ) -> tuple[ApiKey, str]:
        """Create a new API key. Returns (entity, raw_key)."""
        entity, raw_key = ApiKey.create(
            name=name,
            user_id=user_id,
            organization_id=organization_id,
            scopes=scopes,
            expires_in_days=expires_in_days,
        )
        await self._repo.save(entity)
        return entity, raw_key

    async def validate_key(self, raw_key: str) -> ApiKey:
        """Validate an API key and record usage."""
        key_hash = hash_api_key(raw_key)
        api_key = await self._repo.find_by_key_hash(key_hash)
        if api_key is None:
            raise UnauthorizedError(message="Invalid API key")
        if not api_key.is_valid:
            raise UnauthorizedError(
                message="API key is revoked or expired",
                details={"key_id": str(api_key.id)},
            )
        api_key.record_usage()
        await self._repo.save(api_key)
        return api_key

    async def revoke_key(self, key_id: str, user_id: str) -> ApiKey:
        """Revoke an API key."""
        api_key = await self._repo.find_by_id(UUIDv7.from_string(key_id))
        if api_key is None:
            raise NotFoundError(
                message="API key not found",
                resource_type="ApiKey",
                resource_id=key_id,
            )
        if api_key.user_id != user_id:
            raise UnauthorizedError(message="Not authorized to revoke this key")
        api_key.revoke()
        await self._repo.save(api_key)
        return api_key

    async def rotate_key(
        self,
        key_id: str,
        user_id: str,
    ) -> tuple[ApiKey, str]:
        """Rotate an API key. Revokes the old one and creates a new one."""
        old_key = await self._repo.find_by_id(UUIDv7.from_string(key_id))
        if old_key is None:
            raise NotFoundError(
                message="API key not found",
                resource_type="ApiKey",
                resource_id=key_id,
            )
        if old_key.user_id != user_id:
            raise UnauthorizedError(message="Not authorized to rotate this key")
        old_key.revoke()
        await self._repo.save(old_key)
        new_key, raw_key = ApiKey.create(
            name=old_key.name,
            user_id=old_key.user_id,
            organization_id=old_key.organization_id,
            scopes=old_key.scopes,
            expires_in_days=90,
        )
        # Set rotated_from by creating a new entity with it
        rotated_key = ApiKey(
            entity_id=new_key.id,
            name=new_key.name,
            key_hash=new_key.key_hash,
            prefix=new_key.prefix,
            user_id=new_key.user_id,
            organization_id=new_key.organization_id,
            scopes=new_key.scopes,
            expires_at=new_key.expires_at,
            rotated_from=str(old_key.id),
        )
        await self._repo.save(rotated_key)
        return rotated_key, raw_key

    async def list_user_keys(self, user_id: str) -> list[ApiKey]:
        return await self._repo.list_by_user(user_id)

    async def delete_key(self, key_id: str, user_id: str) -> bool:
        api_key = await self._repo.find_by_id(UUIDv7.from_string(key_id))
        if api_key is None:
            raise NotFoundError(
                message="API key not found",
                resource_type="ApiKey",
                resource_id=key_id,
            )
        if api_key.user_id != user_id:
            raise UnauthorizedError(message="Not authorized to delete this key")
        return await self._repo.delete(UUIDv7.from_string(key_id))
