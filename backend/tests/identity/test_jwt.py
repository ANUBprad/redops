"""Tests for JWT and token operations."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.identity.services.auth_service import (
    generate_token,
    hash_token,
)


def test_hash_token_deterministic() -> None:
    h1 = hash_token("abc")
    h2 = hash_token("abc")
    assert h1 == h2


def test_hash_token_different_inputs() -> None:
    h1 = hash_token("abc")
    h2 = hash_token("def")
    assert h1 != h2


def test_generate_token_unique() -> None:
    tokens = {generate_token() for _ in range(100)}
    assert len(tokens) == 100


def test_jwt_roundtrip() -> None:
    secret = "test-secret"
    payload = {"sub": "user123", "email": "a@b.com", "exp": datetime.now(UTC) + timedelta(hours=1)}
    token = jwt.encode(payload, secret, algorithm="HS256")
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["sub"] == "user123"
    assert decoded["email"] == "a@b.com"


def test_jwt_expired_token() -> None:
    secret = "test-secret"
    payload = {"sub": "user123", "exp": datetime.now(UTC) - timedelta(hours=1)}
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, secret, algorithms=["HS256"])


def test_jwt_wrong_secret() -> None:
    payload = {"sub": "user123", "exp": datetime.now(UTC) + timedelta(hours=1)}
    token = jwt.encode(payload, "secret-a", algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "secret-b", algorithms=["HS256"])
