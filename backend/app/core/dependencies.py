"""FastAPI dependency injection for shared resources."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio.client import Client as TemporalClient

from app.core.config import AppConfig, get_config


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated user identity."""

    user_id: str


async def get_current_user(request: Request) -> CurrentUser:
    """Extract the authenticated user from the request.

    Dependency hook for authentication. Replace with JWT/token
    validation when the authentication system is fully implemented.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:]:
        return CurrentUser(user_id=auth_header[7:])
    return CurrentUser(user_id="anonymous")


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
