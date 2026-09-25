"""Regression tests: refresh-token rotation chain survival.

A rotated session must stay usable: the credential returned by
POST /identity/refresh has to be a valid input to the next rotation.
Previously the route returned the stored SHA-256 *hash* instead of the
raw token, so hashing it again never matched storage and every client
was locked out after exactly one rotation (the service discarded the
raw value it had just created).

These tests drive AuthService with an in-memory token store and feed
each rotation's returned credential into the next one — the exact
client contract — plus assert the returned credential is the raw
pre-image of the persisted hash.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.identity.domain.entities import User
from app.identity.domain.enums import UserStatus
from app.identity.services.auth_service import (
    AuthService,
    hash_password,
    hash_token,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import UnauthorizedError


def _make_user() -> User:
    return User(
        entity_id=UUIDv7.generate(),
        email="rotate@example.com",
        display_name="Rotate",
        password_hash=hash_password("password123"),
        status=UserStatus.ACTIVE,
    )


@pytest.fixture
def token_store():
    """In-memory refresh-token table keyed by stored hash."""
    return {}


def _make_service(token_store, user) -> AuthService:
    user_repo = AsyncMock()
    user_repo.find_by_id.return_value = user
    refresh_repo = AsyncMock()

    async def _find_by_hash(token_hash: str):
        return token_store.get(token_hash)

    async def _revoke_by_hash(token_hash: str) -> None:
        from dataclasses import replace

        entity = token_store.get(token_hash)
        if entity is not None:
            token_store[token_hash] = replace(entity, revoked_at=datetime.now(UTC))

    async def _save(entity) -> None:
        token_store[entity.token_hash] = entity

    refresh_repo.find_by_token_hash.side_effect = _find_by_hash
    refresh_repo.revoke_by_token_hash.side_effect = _revoke_by_hash
    refresh_repo.save.side_effect = _save
    return AuthService(user_repo, refresh_repo)


@pytest.mark.asyncio
async def test_rotation_chain_survives_two_rotations() -> None:
    """The credential from rotation N must drive rotation N+1."""
    user = _make_user()
    store: dict = {}
    service = _make_service(store, user)

    raw_initial, initial_entity = service.create_refresh_token(user)
    store[initial_entity.token_hash] = initial_entity

    _, credential_one, _ = await service.refresh_tokens(raw_initial)
    _, credential_two, _ = await service.refresh_tokens(credential_one)
    _, _, _ = await service.refresh_tokens(credential_two)


@pytest.mark.asyncio
async def test_returned_credential_is_raw_preimage_of_stored_hash() -> None:
    """The route forwards this value verbatim, so it must hash to storage."""
    user = _make_user()
    store: dict = {}
    service = _make_service(store, user)

    raw_initial, initial_entity = service.create_refresh_token(user)
    store[initial_entity.token_hash] = initial_entity

    _, credential, _ = await service.refresh_tokens(raw_initial)
    assert hash_token(credential) in store


@pytest.mark.asyncio
async def test_revoked_token_stays_dead() -> None:
    """Rotation still revokes the presented token (no replay)."""
    user = _make_user()
    store: dict = {}
    service = _make_service(store, user)

    raw_initial, initial_entity = service.create_refresh_token(user)
    store[initial_entity.token_hash] = initial_entity

    await service.refresh_tokens(raw_initial)
    with pytest.raises(UnauthorizedError):
        await service.refresh_tokens(raw_initial)
