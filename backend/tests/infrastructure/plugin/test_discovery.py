"""Tests for plugin discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.plugin.discovery import (
    EntryPointPluginDiscovery,
    FilesystemPluginDiscovery,
    PluginDiscoveryStrategy,
)
from app.kernel.registry.plugin import Plugin


class TestPluginDiscoveryStrategy:
    """Verify PluginDiscoveryStrategy is abstract."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            PluginDiscoveryStrategy()  # type: ignore[abstract]


class TestFilesystemPluginDiscovery:
    def test_init_with_dirs(self) -> None:
        discovery = FilesystemPluginDiscovery(
            plugin_dirs=[Path("/tmp/plugins")],
        )
        assert discovery._plugin_dirs == [Path("/tmp/plugins")]

    def test_add_plugin_dir(self) -> None:
        discovery = FilesystemPluginDiscovery()
        discovery.add_plugin_dir(Path("/custom/plugins"))
        assert Path("/custom/plugins") in discovery._plugin_dirs

    def test_discover_nonexistent_dir(self) -> None:
        discovery = FilesystemPluginDiscovery(
            plugin_dirs=[Path("/nonexistent/path")],
        )

        async def _run() -> list[type[Plugin]]:
            return await discovery.discover("test")

        import asyncio

        result = asyncio.run(_run())
        assert result == []


class TestEntryPointPluginDiscovery:
    def test_discover_no_entry_points(self) -> None:
        discovery = EntryPointPluginDiscovery(
            entry_point_group="nonexistent.group",
        )

        async def _run() -> list[type[Plugin]]:
            return await discovery.discover("test")

        import asyncio

        result = asyncio.run(_run())
        assert result == []


class TestPluginLoaderImpl:
    async def test_discover_and_register(self) -> None:
        from app.infrastructure.plugin.loader import PluginLoaderImpl
        from app.kernel.registry.plugin import Plugin, PluginRegistry

        registry = PluginRegistry[Plugin](plugin_type="test")
        loader = PluginLoaderImpl(registry)
        plugins = await loader.discover_plugins("test")
        assert isinstance(plugins, list)
