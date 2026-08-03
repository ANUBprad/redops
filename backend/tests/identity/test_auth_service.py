"""Tests for auth service."""

from unittest.mock import AsyncMock

import pytest

from app.identity.domain.entities import User
from app.identity.domain.enums import UserStatus
from app.identity.services.auth_service import (
    AuthService,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, UnauthorizedError


def test_hash_password() -> None:
    h = hash_password("mypassword")
    assert verify_password("mypassword", h) is True
    assert verify_password("wrong", h) is False


def test_hash_token() -> None:
    h = hash_token("raw_token")
    assert len(h) == 64  # SHA-256 hex digest


def test_generate_token() -> None:
    t1 = generate_token()
    t2 = generate_token()
    assert t1 != t2
    assert len(t1) > 20


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.exists_by_email.return_value = False
    repo.find_by_email.return_value = None
    repo.find_by_id.return_value = None
    return repo


@pytest.fixture
def mock_refresh_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_token_hash.return_value = None
    return repo


@pytest.fixture
def auth_service(
    mock_user_repo: AsyncMock,
    mock_refresh_repo: AsyncMock,
) -> AuthService:
    return AuthService(mock_user_repo, mock_refresh_repo)


def _make_user(
    *,
    email: str = "test@example.com",
    status: UserStatus = UserStatus.ACTIVE,
    password_hash: str | None = hash_password("password123"),
) -> User:
    return User(
        entity_id=UUIDv7.generate(),
        email=email,
        display_name="Test",
        password_hash=password_hash,
        status=status,
    )


@pytest.mark.asyncio
async def test_register_success(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
) -> None:
    user = await auth_service.register("new@example.com", "New User", "password123")
    assert user.email == "new@example.com"
    mock_user_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_duplicate_email(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
) -> None:
    mock_user_repo.exists_by_email.return_value = True
    with pytest.raises(ConflictError):
        await auth_service.register("exists@example.com", "User", "password123")


@pytest.mark.asyncio
async def test_authenticate_success(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
) -> None:
    user = _make_user()
    mock_user_repo.find_by_email.return_value = user
    result = await auth_service.authenticate("test@example.com", "password123")
    assert result.email == "test@example.com"


@pytest.mark.asyncio
async def test_authenticate_wrong_password(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
) -> None:
    user = _make_user()
    mock_user_repo.find_by_email.return_value = user
    with pytest.raises(UnauthorizedError):
        await auth_service.authenticate("test@example.com", "wrongpassword")


@pytest.mark.asyncio
async def test_authenticate_no_user(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
) -> None:
    mock_user_repo.find_by_email.return_value = None
    with pytest.raises(UnauthorizedError):
        await auth_service.authenticate("nobody@example.com", "password123")


@pytest.mark.asyncio
async def test_authenticate_suspended_user(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
) -> None:
    user = _make_user(status=UserStatus.SUSPENDED)
    mock_user_repo.find_by_email.return_value = user
    with pytest.raises(UnauthorizedError):
        await auth_service.authenticate("test@example.com", "password123")


@pytest.mark.asyncio
async def test_authenticate_oauth_only_user(
    auth_service: AuthService,
    mock_user_repo: AsyncMock,
) -> None:
    user = _make_user(password_hash=None)
    mock_user_repo.find_by_email.return_value = user
    with pytest.raises(UnauthorizedError):
        await auth_service.authenticate("test@example.com", "password123")


def test_create_access_token(auth_service: AuthService) -> None:
    user = _make_user()
    token = auth_service.create_access_token(user)
    assert isinstance(token, str)
    payload = auth_service.decode_access_token(token)
    assert payload["sub"] == str(user.id)
    assert payload["email"] == user.email


def test_create_refresh_token(auth_service: AuthService) -> None:
    user = _make_user()
    raw_token, refresh = auth_service.create_refresh_token(user)
    assert isinstance(raw_token, str)
    assert refresh.user_id == str(user.id)
    assert refresh.is_valid is True
