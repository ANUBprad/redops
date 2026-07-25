"""Plugin loading and automatic registration into the Kernel PluginRegistry.

Provides a concrete PluginLoaderImpl that discovers plugins through
multiple strategies and registers them into the Kernel's PluginRegistry.
"""

from __future__ import annotations

from structlog import get_logger

from app.infrastructure.plugin.discovery import (
    EntryPointPluginDiscovery,
    FilesystemPluginDiscovery,
    PluginDiscoveryStrategy,
)
from app.kernel.registry.plugin import Plugin, PluginContext, PluginLoader, PluginRegistry


class PluginLoaderImpl(PluginLoader):
    """Concrete plugin loader that discovers and loads plugins.

    Uses configured discovery strategies to find plugins, then
    instantiates and registers them into a Kernel PluginRegistry.

    Supports multiple discovery strategies that are consulted
    in order. Duplicate plugin names are handled by first-wins
    semantics.
    """

    def __init__(
        self,
        registry: PluginRegistry[Plugin],
        discovery_strategies: list[PluginDiscoveryStrategy] | None = None,
    ) -> None:
        """Initialize with registry and optional discovery strategies."""
        self._registry = registry
        self._discovery_strategies = discovery_strategies or [
            FilesystemPluginDiscovery(),
            EntryPointPluginDiscovery(),
        ]

    def add_discovery_strategy(self, strategy: PluginDiscoveryStrategy) -> None:
        """Add a discovery strategy to the loader.

        Args:
            strategy: The discovery strategy to add.

        """
        self._discovery_strategies.append(strategy)

    async def discover_plugins(self, plugin_type: str) -> list[Plugin]:  # type: ignore[override]
        """Discover and instantiate plugins of the given type.

        Each discovery strategy is consulted in order. Plugin classes
        are instantiated without arguments and returned.

        Args:
            plugin_type: The type of plugin to discover.

        Returns:
            A list of instantiated Plugin instances.

        """
        discovered_classes: set[type[Plugin]] = set()
        for strategy in self._discovery_strategies:
            classes = await strategy.discover(plugin_type)
            discovered_classes.update(classes)

        return [cls() for cls in discovered_classes]

    async def load_plugin(self, name: str, plugin_type: str) -> Plugin | None:  # type: ignore[override]
        """Load a single named plugin.

        Iterates through discovery strategies to find a plugin
        with the given name.

        Args:
            name: The name of the plugin to load.
            plugin_type: The type of plugin to find.

        Returns:
            The loaded Plugin instance, or None if not found.

        """
        plugins = await self.discover_plugins(plugin_type)
        for plugin in plugins:
            if plugin.metadata().name == name:
                return plugin
        return None

    async def discover_and_register(
        self,
        plugin_type: str,
        context: PluginContext | None = None,
    ) -> list[Plugin]:
        """Discover plugins and automatically register them.

        Args:
            plugin_type: The type of plugin to discover.
            context: Optional context passed to each plugin during initialization.

        Returns:
            A list of successfully registered plugins.

        """
        plugins = await self.discover_plugins(plugin_type)
        registered: list[Plugin] = []
        logger = get_logger("redops_eval.plugin")
        for plugin in plugins:
            try:
                self._registry.register(plugin)
                await plugin.initialize(context)
                registered.append(plugin)
            except Exception:
                logger.exception("Failed to register plugin", plugin_name=plugin.metadata().name)
                continue
        return registered
