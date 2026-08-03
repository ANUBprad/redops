"""Tests for API Keys domain entity."""

from datetime import UTC, datetime, timedelta

from app.apikeys.domain import ApiKey, generate_api_key, hash_api_key


def test_generate_api_key() -> None:
    key = generate_api_key()
    assert key.startswith("ro_")
    assert len(key) > 20


def test_hash_api_key() -> None:
    key = "ro_test123"
    hashed = hash_api_key(key)
    assert len(hashed) == 64  # SHA-256 hex
    assert hashed == hash_api_key(key)  # Deterministic


def test_api_key_create() -> None:
    entity, raw_key = ApiKey.create(
        name="Test Key",
        user_id="user-1",
        scopes=("evaluations:read", "runs:read"),
        expires_in_days=90,
    )
    assert entity.name == "Test Key"
    assert entity.user_id == "user-1"
    assert entity.scopes == ("evaluations:read", "runs:read")
    assert entity.is_active is True
    assert raw_key.startswith("ro_")


def test_api_key_validity() -> None:
    entity, _ = ApiKey.create(
        name="Test",
        user_id="user-1",
        expires_in_days=30,
    )
    assert entity.is_valid is True
    assert entity.is_expired is False


def test_api_key_expired() -> None:
    entity = ApiKey(
        name="Expired",
        key_hash="hash",
        prefix="ro_test",
        user_id="user-1",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert entity.is_expired is True
    assert entity.is_valid is False


def test_api_key_revoke() -> None:
    entity, _ = ApiKey.create(
        name="Test",
        user_id="user-1",
    )
    entity.revoke()
    assert entity.is_active is False
    assert entity.is_valid is False


def test_api_key_record_usage() -> None:
    entity, _ = ApiKey.create(
        name="Test",
        user_id="user-1",
    )
    entity.record_usage()
    assert entity.usage_count == 1
    assert entity.last_used_at is not None
