from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BaseConfiguration(ABC): ...


@dataclass(frozen=True)
class ServiceConfiguration(BaseConfiguration):
    host: str
    port: int
    timeout_seconds: float = 30.0
    retry_count: int = 3
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class PluginConfiguration(BaseConfiguration):
    name: str
    enabled: bool = True
    version: str | None = None
    settings: dict[str, Any] | None = None


@dataclass(frozen=True)
class EnvironmentConfiguration(BaseConfiguration):
    env: str
    debug: bool = False
    log_level: str = "INFO"
    version: str = "0.0.0"
