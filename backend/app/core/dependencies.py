"""FastAPI dependency injection for shared resources."""

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Request
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio.client import Client as TemporalClient

from app.core.config import AppConfig, get_config


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
