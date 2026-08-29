"""FastAPI dependency injection for shared resources."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Request
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio.client import Client as TemporalClient

from app.core.config import AppConfig, get_config


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated user identity."""

    user_id: str
    email: str = ""
    name: str = ""
    roles: tuple[str, ...] = ()


async def get_current_user(request: Request) -> CurrentUser:
    """Extract and validate the authenticated user from the JWT token.

    Decodes the JWT access token from the Authorization header.
    Always requires a valid token — no anonymous fallback.
    """
    config = get_config()
    from fastapi import HTTPException

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer ") or not auth_header[7:]:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = auth_header[7:]
    try:
        payload = jwt.decode(
            token,
            config.app_secret_key,
            algorithms=[config.jwt_algorithm],
        )
        user_id = payload.get("sub", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        return CurrentUser(
            user_id=user_id,
            email=payload.get("email", ""),
            name=payload.get("name", ""),
            roles=tuple(payload.get("roles", [])),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from None


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, Any]:
    """Provide an async database session for the request lifecycle."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_config_dependency() -> AppConfig:
    """Return the application configuration singleton."""
    return get_config()


def get_redis_client(request: Request) -> aioredis.Redis:
    """Return the application Redis client from app state."""
    client: aioredis.Redis = request.app.state.redis_client
    return client


def get_temporal_client(request: Request) -> TemporalClient:
    """Return the application Temporal client from app state."""
    client: TemporalClient = request.app.state.temporal_client
    return client
