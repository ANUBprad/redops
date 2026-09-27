"""Alembic environment configuration for async SQLAlchemy.

Consumes database configuration from environment variables to match the
application's canonical configuration (DB_HOST, DB_PORT, DB_USER,
DB_PASSWORD, DB_NAME). Falls back to alembic.ini for local development
without Docker.
"""

import asyncio
import os
from logging.config import fileConfig

from pydantic import PostgresDsn
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models here when business contexts are created
from app.infrastructure.database.models.base import Base  # noqa: E402

target_metadata = Base.metadata


def _build_database_url() -> str:
    """Build database URL from environment variables, matching AppConfig.

    Uses the same env vars as the application: DB_HOST, DB_PORT, DB_USER,
    DB_PASSWORD, DB_NAME. Falls back to alembic.ini sqlalchemy.url if
    not all variables are set (e.g., local development without Docker).
    """
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")

    if all(v is not None for v in (host, port, user, password, database)):
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=user,
                password=password,
                host=host,
                port=int(port),
                path=database,
            )
        )

    # Fallback to alembic.ini for local/dev without full env
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _build_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations with a connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    url = _build_database_url()
    connectable = create_async_engine(url)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
