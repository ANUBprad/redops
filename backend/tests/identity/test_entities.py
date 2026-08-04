"""Tests for Identity domain entities."""

from datetime import UTC, datetime, timedelta

from app.identity.domain.entities import OAuthAccount, RefreshToken, User
from app.identity.domain.enums import OAuthProvider, UserStatus


def test_user_create() -> None:
    user = User.create(
        email="test@example.com",
        display_name="Test User",
        password_hash="hashed",
    )
    assert user.email == "test@example.com"
    assert user.display_name == "Test User"
    assert user.status == UserStatus.PENDING_VERIFICATION
    assert user.is_active is False
    assert user.is_email_verified is False


def test_user_verify_email() -> None:
    user = User.create(
        email="test@example.com",
        display_name="Test User",
    )
    user.verify_email()
    assert user.is_email_verified is True
    assert user.status == UserStatus.ACTIVE


def test_user_record_login() -> None:
    user = User.create(
        email="test@example.com",
        display_name="Test User",
    )
    user.record_login()
    assert user.login_count == 1
    assert user.last_login_at is not None


def test_user_suspend_deactivate() -> None:
    user = User.create(
        email="test@example.com",
        display_name="Test User",
        password_hash="hashed",
    )
    user.verify_email()
    assert user.is_active is True
    user.suspend()
    assert user.status == UserStatus.SUSPENDED
    user.activate()
    assert user.status == UserStatus.ACTIVE
    user.deactivate()
    assert user.status == UserStatus.DEACTIVATED


def test_user_set_password_hash() -> None:
    user = User.create(
        email="test@example.com",
        display_name="Test User",
        password_hash="old_hash",
    )
    old_version = user.version
    user.set_password_hash("new_hash")
    assert user.password_hash == "new_hash"
    assert user.version > old_version


def test_user_update_profile() -> None:
    user = User.create(
        email="test@example.com",
        display_name="Old Name",
    )
    user.update_profile(display_name="New Name", avatar_url="https://example.com/avatar.png")
    assert user.display_name == "New Name"
    assert user.avatar_url == "https://example.com/avatar.png"


def test_refresh_token_is_valid() -> None:
    token = RefreshToken(
        token_id="1",
        user_id="user-1",
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert token.is_valid is True
    assert token.is_expired is False
    assert token.is_revoked is False


def test_refresh_token_is_expired() -> None:
    token = RefreshToken(
        token_id="1",
        user_id="user-1",
        token_hash="hash",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert token.is_valid is False
    assert token.is_expired is True


def test_refresh_token_is_revoked() -> None:
    token = RefreshToken(
        token_id="1",
        user_id="user-1",
        token_hash="hash",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked_at=datetime.now(UTC),
    )
    assert token.is_valid is False
    assert token.is_revoked is True


def test_oauth_account() -> None:
    account = OAuthAccount(
        provider=OAuthProvider.GITHUB,
        provider_user_id="12345",
        user_id="user-1",
        access_token="token",
    )
    assert account.provider == OAuthProvider.GITHUB
    assert account.provider_user_id == "12345"
