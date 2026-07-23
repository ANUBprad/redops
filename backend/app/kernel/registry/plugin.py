from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar


@dataclass(frozen=True)
class PluginMetadata:
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    plugin_type: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PluginContext:
    plugin_name: str
    plugin_type: str
    config: dict[str, Any] | None = None


class Plugin(ABC):
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        ...

    @abstractmethod
    async def initialize(self, context: PluginContext | None = None) -> None:
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    async def validate(self) -> list[str]:
        return []


P = TypeVar("P", bound=Plugin)


class PluginRegistry(Generic[P]):
    def __init__(self, plugin_type: str = "") -> None:
        self._plugins: dict[str, P] = {}
        self._plugin_type = plugin_type

    def register(self, plugin: P) -> None:
        name = plugin.metadata().name
        if name in self._plugins:
            raise ValueError(
                f"Plugin '{name}' is already registered in registry '{self._plugin_type}'"
            )
        self._plugins[name] = plugin

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    def get(self, name: str) -> P | None:
        return self._plugins.get(name)

    def get_all(self) -> list[P]:
        return list(self._plugins.values())

    def list_metadata(self) -> list[PluginMetadata]:
        return [p.metadata() for p in self._plugins.values()]

    async def initialize_all(self) -> list[tuple[str, bool]]:
        results: list[tuple[str, bool]] = []
        for name, plugin in self._plugins.items():
            try:
                ctx = PluginContext(plugin_name=name, plugin_type=self._plugin_type)
                await plugin.initialize(ctx)
                results.append((name, True))
            except Exception:
                results.append((name, False))
        return results

    async def shutdown_all(self) -> None:
        for name, plugin in reversed(list(self._plugins.items())):
            try:
                await plugin.shutdown()
            except Exception:
                pass

    async def health_all(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for name, plugin in self._plugins.items():
            try:
                result[name] = await plugin.health()
            except Exception:
                result[name] = False
        return result

    async def validate_all(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for name, plugin in self._plugins.items():
            try:
                issues = await plugin.validate()
                result[name] = issues
            except Exception:
                result[name] = ["Validation raised exception"]
        return result

    @property
    def count(self) -> int:
        return len(self._plugins)


class PluginLoader(ABC):
    @abstractmethod
    async def discover_plugins(self, plugin_type: str) -> list[P]:
        ...

    @abstractmethod
    async def load_plugin(self, name: str, plugin_type: str) -> P | None:
        ...
