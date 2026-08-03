"""Tests for API Keys domain and service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.apikeys.domain import ApiKey, hash_api_key
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import NotFoundError, UnauthorizedError


def test_api_key_creation() -> None:
    key, raw_key = ApiKey.create(
        name="Test Key",
        user_id="user-1",
        scopes=("read", "write"),
    )
    assert key.name == "Test Key"
    assert key.user_id == "user-1"
    assert key.scopes == ("read", "write")
    assert key.is_active is True
    assert raw_key.startswith("ro_")
    assert key.prefix == raw_key[:12]
    assert key.key_hash == hash_api_key(raw_key)


def test_api_key_no_expiry() -> None:
    key, _ = ApiKey.create(name="Key", user_id="u1")
    assert key.is_expired is False
    assert key.is_valid is True


def test_api_key_with_expiry() -> None:
    key, _ = ApiKey.create(name="Key", user_id="u1", expires_in_days=30)
    assert key.expires_at is not None
    assert key.is_expired is False
    assert key.is_valid is True


def test_api_key_expired() -> None:
    key = ApiKey(
        name="Key",
        key_hash="hash",
        prefix="ro_abc",
        user_id="u1",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert key.is_expired is True
    assert key.is_valid is False


def test_api_key_revoked() -> None:
    key, _ = ApiKey.create(name="Key", user_id="u1")
    key.revoke()
    assert key.is_active is False
    assert key.is_valid is False


def test_api_key_record_usage() -> None:
    key, _ = ApiKey.create(name="Key", user_id="u1")
    assert key.usage_count == 0
    assert key.last_used_at is None
    key.record_usage()
    assert key.usage_count == 1
    assert key.last_used_at is not None


def test_api_key_activate() -> None:
    key, _ = ApiKey.create(name="Key", user_id="u1")
    key.revoke()
    assert key.is_valid is False
    key.activate()
    assert key.is_valid is True


def test_hash_api_key() -> None:
    h = hash_api_key("ro_test123")
    assert len(h) == 64


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_key_hash.return_value = None
    repo.find_by_id.return_value = None
    return repo


@pytest.mark.asyncio
async def test_validate_key_invalid(mock_repo: AsyncMock) -> None:
    from app.apikeys.services import ApiKeyService

    service = ApiKeyService(mock_repo)
    with pytest.raises(UnauthorizedError):
        await service.validate_key("ro_invalid")


@pytest.mark.asyncio
async def test_validate_key_revoked(mock_repo: AsyncMock) -> None:
    from app.apikeys.services import ApiKeyService

    service = ApiKeyService(mock_repo)
    key, raw = ApiKey.create(name="Key", user_id="u1")
    key.revoke()
    mock_repo.find_by_key_hash.return_value = key
    with pytest.raises(UnauthorizedError):
        await service.validate_key(raw)


@pytest.mark.asyncio
async def test_revoke_key_not_found(mock_repo: AsyncMock) -> None:
    from app.apikeys.services import ApiKeyService

    service = ApiKeyService(mock_repo)
    with pytest.raises(NotFoundError):
        await service.revoke_key(str(UUIDv7.generate()), "user-1")


@pytest.mark.asyncio
async def test_create_key(mock_repo: AsyncMock) -> None:
    from app.apikeys.services import ApiKeyService

    service = ApiKeyService(mock_repo)
    key, raw = await service.create_key(
        name="Test",
        user_id="user-1",
        scopes=("read",),
        expires_in_days=30,
    )
    assert key.name == "Test"
    assert raw.startswith("ro_")
    mock_repo.save.assert_awaited_once()
