"""API Keys REST endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.apikeys.schemas import ApiKeyCreatedResponse, ApiKeyResponse, CreateApiKeyRequest
from app.apikeys.services import ApiKeyService
from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.repositories.api_key_repository import (
    SqlAlchemyApiKeyRepository,
)
from app.kernel.exceptions.errors import BaseError

if TYPE_CHECKING:
    from app.apikeys.domain import ApiKey

apikeys_router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _get_service(session: AsyncSession) -> ApiKeyService:
    return ApiKeyService(SqlAlchemyApiKeyRepository(session))


def _key_to_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=str(key.id),
        name=key.name,
        prefix=key.prefix,
        user_id=key.user_id,
        organization_id=key.organization_id,
        scopes=list(key.scopes),
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        usage_count=key.usage_count,
        is_active=key.is_active,
        rotated_from=key.rotated_from,
        created_at=key.created_at.isoformat(),
        updated_at=key.updated_at.isoformat(),
    )


@apikeys_router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeyCreatedResponse:
    """Create a new API key."""
    service = _get_service(session)
    try:
        key, raw_key = await service.create_key(
            name=body.name,
            user_id=current_user.user_id,
            scopes=tuple(body.scopes),
            expires_in_days=body.expires_in_days,
        )
        return ApiKeyCreatedResponse(
            id=str(key.id),
            name=key.name,
            key=raw_key,
            prefix=key.prefix,
            scopes=list(key.scopes),
            expires_at=key.expires_at.isoformat() if key.expires_at else None,
            created_at=key.created_at.isoformat(),
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@apikeys_router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ApiKeyResponse]:
    """List the current user's API keys."""
    service = _get_service(session)
    keys = await service.list_user_keys(current_user.user_id)
    return [_key_to_response(k) for k in keys]


@apikeys_router.post("/{key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeyResponse:
    """Revoke an API key."""
    service = _get_service(session)
    try:
        key = await service.revoke_key(key_id, current_user.user_id)
        return _key_to_response(key)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@apikeys_router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeyCreatedResponse:
    """Rotate an API key (revoke old, create new)."""
    service = _get_service(session)
    try:
        key, raw_key = await service.rotate_key(key_id, current_user.user_id)
        return ApiKeyCreatedResponse(
            id=str(key.id),
            name=key.name,
            key=raw_key,
            prefix=key.prefix,
            scopes=list(key.scopes),
            expires_at=key.expires_at.isoformat() if key.expires_at else None,
            created_at=key.created_at.isoformat(),
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@apikeys_router.delete("/{key_id}", status_code=204)
async def delete_api_key(
    key_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an API key."""
    service = _get_service(session)
    try:
        await service.delete_key(key_id, current_user.user_id)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
