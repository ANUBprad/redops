"""Database configuration provider extending Kernel BaseConfiguration."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import PostgresDsn

from app.kernel.contracts.config import BaseConfiguration


@dataclass(frozen=True)
class DatabaseConfiguration(BaseConfiguration):
    """Database connection and pool configuration.

    Central configuration for the PostgreSQL database connection,
    including pool sizing, timeouts, and connection URL generation.
    """

    host: str = "localhost"
    port: int = 5432
    user: str = "redops"
    password: str = "redops"
    database: str = "redops"
    min_pool_size: int = 5
    max_pool_size: int = 20
    echo: bool = False
    pool_pre_ping: bool = True
    connect_timeout_seconds: int = 10
    statement_timeout_seconds: int = 30

    @property
    def database_url(self) -> str:
        """Construct the async PostgreSQL connection URL."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                path=self.database,
            ),
        )

    @property
    def max_overflow(self) -> int:
        """Return the max overflow pool connections."""
        return self.max_pool_size - self.min_pool_size
