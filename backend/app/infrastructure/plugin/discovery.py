"""Plugin discovery mechanisms for filesystem and Python entry-point based plugins.

Provides two discovery strategies:
- FilesystemPluginDiscovery: walks a directory tree for plugin modules
- EntryPointPluginDiscovery: uses Python package metadata entry points
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.kernel.registry.plugin import Plugin

if TYPE_CHECKING:
    from pathlib import Path


class PluginDiscoveryStrategy(ABC):
    """Abstract strategy for discovering plugin modules."""

    @abstractmethod
    async def discover(self, plugin_type: str) -> list[type[Plugin]]:
        """Discover plugin classes for the given plugin type.

        Args:
            plugin_type: The type of plugin to discover (e.g., "provider", "evaluator").

        Returns:
            A list of discovered Plugin subclasses.

        """
        ...


class FilesystemPluginDiscovery(PluginDiscoveryStrategy):
    """Discovers plugins by scanning the filesystem for plugin modules.

    Scans a configured directory for Python files that contain
    Plugin subclass implementations.
    """

    def __init__(self, plugin_dirs: list[Path] | None = None) -> None:
        """Initialize with optional plugin directories."""
        self._plugin_dirs = plugin_dirs or []

    def add_plugin_dir(self, directory: Path) -> None:
        """Add a directory to scan for plugins.

        Args:
            directory: The filesystem path to scan.

        """
        if directory not in self._plugin_dirs:
            self._plugin_dirs.append(directory)

    async def discover(self, plugin_type: str) -> list[type[Plugin]]:
        """Discover Plugin subclasses from filesystem directories.

        Args:
            plugin_type: The type of plugin to discover (unused for filesystem).

        Returns:
            A list of discovered Plugin subclasses.

        """
        discovered: list[type[Plugin]] = []

        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.is_dir():
                continue

            for module_info in pkgutil.iter_modules([str(plugin_dir)]):
                try:
                    module = importlib.import_module(module_info.name)
                    for _name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, Plugin)
                            and obj is not Plugin
                            and not inspect.isabstract(obj)
                        ):
                            discovered.append(obj)
                except Exception:  # noqa: S112
                    continue

        return discovered


class EntryPointPluginDiscovery(PluginDiscoveryStrategy):
    """Discovers plugins registered as Python entry points.

    Uses importlib.metadata to find plugins registered under
    the "redops.plugins" entry point group.
    """

    def __init__(self, entry_point_group: str = "redops.plugins") -> None:
        """Initialize with the entry point group name."""
        self._entry_point_group = entry_point_group

    async def discover(self, plugin_type: str) -> list[type[Plugin]]:
        """Discover Plugin subclasses registered as entry points.

        Args:
            plugin_type: If provided, only loads entry points tagged with
                        this type. Otherwise, loads all entries.

        Returns:
            A list of discovered Plugin subclasses.

        """
        discovered: list[type[Plugin]] = []

        try:
            entry_points = importlib.metadata.entry_points(
                group=self._entry_point_group,
            )
        except Exception:
            return discovered

        for entry_point in entry_points:
            try:
                plugin_class = entry_point.load()
                if (
                    inspect.isclass(plugin_class)
                    and issubclass(plugin_class, Plugin)
                    and not inspect.isabstract(plugin_class)
                ):
                    discovered.append(plugin_class)
            except Exception:  # noqa: S112
                continue

        return discovered
