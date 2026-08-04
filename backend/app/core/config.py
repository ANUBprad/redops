"""Application configuration via Pydantic Settings.

Configuration is loaded exclusively from environment variables.
No hardcoded defaults for production — .env.example documents all variables.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "testing", "production"]


class AppConfig(BaseSettings):
    """Central configuration for the RedOps Eval application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # APP
    app_env: AppEnv = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="redops-eval", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=True, alias="APP_DEBUG")
    app_log_level: str = Field(default="DEBUG", alias="APP_LOG_LEVEL")

    # SERVER
    server_host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    server_port: int = Field(default=8000, ge=1, le=65535, alias="SERVER_PORT")
    server_cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="SERVER_CORS_ORIGINS",
    )

    # DATABASE
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, ge=1, le=65535, alias="DB_PORT")
    db_user: str = Field(default="redops", alias="DB_USER")
    db_password: str = Field(default="redops", alias="DB_PASSWORD")
    db_name: str = Field(default="redops", alias="DB_NAME")
    db_min_pool_size: int = Field(default=5, ge=1, alias="DB_MIN_POOL_SIZE")
    db_max_pool_size: int = Field(default=20, ge=1, alias="DB_MAX_POOL_SIZE")

    @property
    def database_url(self) -> str:
        """Construct the async PostgreSQL connection URL."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                path=self.db_name,
            )
        )

    @property
    def env(self) -> str:
        """Return the current environment string."""
        return self.app_env

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.server_cors_origins.split(",")]

    @property
    def app_logger(self) -> Any:
        """Get a pre-configured logger for the application."""
        from structlog import get_logger

        return get_logger("redops_eval")

    # REDIS
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, ge=1, le=65535, alias="REDIS_PORT")
    redis_db: int = Field(default=0, ge=0, le=15, alias="REDIS_DB")

    # TEMPORAL
    temporal_host: str = Field(default="localhost", alias="TEMPORAL_HOST")
    temporal_port: int = Field(default=7233, ge=1, le=65535, alias="TEMPORAL_PORT")
    temporal_namespace: str = Field(default="default", alias="TEMPORAL_NAMESPACE")
    temporal_task_queue: str = Field(default="redops-eval", alias="TEMPORAL_TASK_QUEUE")

    # SECURITY
    app_secret_key: str = Field(default="change-me", alias="APP_SECRET_KEY")

    # JWT
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_ttl_seconds: int = Field(default=3600, alias="JWT_ACCESS_TOKEN_TTL")
    jwt_refresh_token_ttl_seconds: int = Field(
        default=2592000,
        alias="JWT_REFRESH_TOKEN_TTL",
    )  # 30 days

    # OAUTH
    github_client_id: str = Field(default="", alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(default="", alias="GITHUB_CLIENT_SECRET")
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    oauth_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/oauth/callback",
        alias="OAUTH_REDIRECT_URI",
    )

    @field_validator("app_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid}")
        return v.upper()


@lru_cache
def get_config() -> AppConfig:
    """Return a cached singleton of the application configuration."""
    return AppConfig()
