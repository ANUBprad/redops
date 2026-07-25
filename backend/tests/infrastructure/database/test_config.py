"""Tests for infrastructure configuration."""

from app.infrastructure.config.database import DatabaseConfiguration
from app.infrastructure.config.logging import LoggingConfiguration
from app.infrastructure.config.redis import RedisConfiguration
from app.infrastructure.config.temporal import TemporalConfiguration
from app.kernel.contracts.config import BaseConfiguration


class TestDatabaseConfiguration:
    def test_extends_base_configuration(self) -> None:
        config = DatabaseConfiguration()
        assert isinstance(config, BaseConfiguration)

    def test_default_values(self) -> None:
        config = DatabaseConfiguration()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "redops"

    def test_database_url_generation(self) -> None:
        config = DatabaseConfiguration(
            host="pg.example.com",
            port=5432,
            user="admin",
            password="secret",
            database="mydb",
        )
        url = config.database_url
        assert "postgresql+asyncpg" in url
        assert "admin" in url
        assert "pg.example.com" in url
        assert "mydb" in url

    def test_max_overflow(self) -> None:
        config = DatabaseConfiguration(min_pool_size=5, max_pool_size=20)
        assert config.max_overflow == 15


class TestRedisConfiguration:
    def test_extends_base_configuration(self) -> None:
        config = RedisConfiguration(host="localhost", port=6379)
        assert isinstance(config, BaseConfiguration)

    def test_default_values(self) -> None:
        config = RedisConfiguration(host="localhost", port=6379)
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0

    def test_connection_url(self) -> None:
        config = RedisConfiguration(host="redis.example.com", port=6380, db=1)
        assert config.connection_url == "redis://redis.example.com:6380/1"


class TestTemporalConfiguration:
    def test_extends_base_configuration(self) -> None:
        config = TemporalConfiguration(host="localhost", port=7233)
        assert isinstance(config, BaseConfiguration)

    def test_target_host(self) -> None:
        config = TemporalConfiguration(host="temporal.example.com", port=7233)
        assert config.target_host == "temporal.example.com:7233"

    def test_task_queue_default(self) -> None:
        config = TemporalConfiguration(host="localhost", port=7233)
        assert config.task_queue == "redops-eval"


class TestLoggingConfiguration:
    def test_extends_base_configuration(self) -> None:
        config = LoggingConfiguration()
        assert isinstance(config, BaseConfiguration)

    def test_default_level(self) -> None:
        config = LoggingConfiguration()
        assert config.level == "INFO"
