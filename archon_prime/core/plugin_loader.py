# ARCHON_FEAT: plugin-loader-001
"""
ARCHON PRIME - Plugin Loader
============================

Dynamic plugin discovery, loading, and lifecycle management.

Features:
- Automatic plugin discovery from directories
- Dependency resolution
- Hot reload support
- Plugin isolation

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

from .plugin_base import Plugin, PluginConfig, PluginState, PluginCategory
from .event_bus import EventBus, Event, EventType

logger = logging.getLogger("ARCHON_PluginLoader")


@dataclass
class PluginInfo:
    """Plugin metadata."""

    name: str
    path: Path
    module_name: str
    plugin_class: Type[Plugin]
    config: PluginConfig
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PluginLoader:
    """
    Dynamic plugin loader and lifecycle manager.

    Discovers and loads plugins from specified directories,
    manages dependencies, and handles plugin lifecycle.

    Example:
        loader = PluginLoader()
        loader.discover_plugins(Path("plugins"))

        await loader.load_all()
        await loader.initialize_all(event_bus)
        await loader.start_all()
    """

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        self._plugin_dirs = plugin_dirs or []
        self._discovered: Dict[str, PluginInfo] = {}
        self._plugins: Dict[str, Plugin] = {}
        self._load_order: List[str] = []
        self._event_bus: Optional[EventBus] = None

        logger.info("PluginLoader initialized")

    def add_plugin_dir(self, path: Path) -> None:
        """Add a plugin directory to search."""
        if path.exists() and path.is_dir():
            self._plugin_dirs.append(path)
            logger.debug(f"Plugin directory added: {path}")

    def discover_plugins(self, base_path: Optional[Path] = None) -> int:
        """
        Discover plugins in directories.

        Args:
            base_path: Optional base path to search

        Returns:
            Number of plugins discovered
        """
        if base_path:
            self.add_plugin_dir(base_path)

        discovered_count = 0

        for plugin_dir in self._plugin_dirs:
            discovered_count += self._scan_directory(plugin_dir)

        # Resolve load order based on dependencies
        self._resolve_load_order()

        logger.info(f"Discovered {discovered_count} plugins")
        return discovered_count

    def _scan_directory(self, directory: Path) -> int:
        """Scan a directory for plugins."""
        count = 0

        if not directory.exists():
            return 0

        # Look for Python files that might be plugins
        for py_file in directory.glob("**/*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                plugin_info = self._load_plugin_info(py_file)
                if plugin_info:
                    self._discovered[plugin_info.name] = plugin_info
                    count += 1
                    logger.debug(f"Discovered plugin: {plugin_info.name}")
            except Exception as e:
                logger.warning(f"Failed to scan {py_file}: {e}")

        return count

    def _load_plugin_info(self, file_path: Path) -> Optional[PluginInfo]:
        """Load plugin info from a file."""
        try:
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, file_path)

            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find Plugin subclasses
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Plugin)
                    and attr is not Plugin
                    and not attr.__name__.endswith("Plugin")  # Skip base classes
                ):
                    # Create temporary instance to get config
                    try:
                        instance = attr()
                        config = instance.config

                        return PluginInfo(
                            name=config.name,
                            path=file_path,
                            module_name=module_name,
                            plugin_class=attr,
                            config=config,
                        )
                    except Exception:
                        continue

        except Exception as e:
            logger.debug(f"Could not load {file_path}: {e}")

        return None

    def _resolve_load_order(self) -> None:
        """Resolve plugin load order based on dependencies."""
        resolved = []
        unresolved = set(self._discovered.keys())

        while unresolved:
            made_progress = False

            for name in list(unresolved):
                info = self._discovered[name]
                deps = set(info.config.dependencies)

                # Check if all dependencies are resolved
                if deps.issubset(set(resolved)):
                    resolved.append(name)
                    unresolved.remove(name)
                    made_progress = True

            if not made_progress and unresolved:
                # Circular dependency or missing dependency
                logger.warning(f"Unresolved dependencies for: {unresolved}")
                # Add remaining in discovery order
                resolved.extend(unresolved)
                break

        self._load_order = resolved

    def register_plugin(self, plugin: Plugin) -> None:
        """
        Register a plugin instance directly.

        Args:
            plugin: Plugin instance to register
        """
        self._plugins[plugin.name] = plugin
        if plugin.name not in self._load_order:
            self._load_order.append(plugin.name)
        logger.debug(f"Plugin registered: {plugin.name}")

    async def load_plugin(self, name: str) -> Optional[Plugin]:
        """
        Load a single plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance if loaded successfully
        """
        if name in self._plugins:
            return self._plugins[name]

        if name not in self._discovered:
            logger.warning(f"Plugin not found: {name}")
            return None

        info = self._discovered[name]

        try:
            # Create plugin instance
            plugin = info.plugin_class()

            # Load plugin
            if await plugin.load():
                self._plugins[name] = plugin
                logger.info(f"Plugin loaded: {name}")
                return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")

        return None

    async def load_all(self, enabled_only: bool = True) -> int:
        """
        Load all discovered plugins.

        Args:
            enabled_only: Only load enabled plugins

        Returns:
            Number of plugins loaded
        """
        loaded = 0

        for name in self._load_order:
            if name in self._discovered:
                info = self._discovered[name]

                if enabled_only and not info.config.enabled:
                    continue

                if await self.load_plugin(name):
                    loaded += 1

        logger.info(f"Loaded {loaded} plugins")
        return loaded

    async def initialize_all(self, event_bus: EventBus) -> int:
        """
        Initialize all loaded plugins.

        Args:
            event_bus: Event bus for communication

        Returns:
            Number of plugins initialized
        """
        self._event_bus = event_bus
        initialized = 0

        for name in self._load_order:
            if name in self._plugins:
                plugin = self._plugins[name]

                if plugin.state == PluginState.LOADED:
                    try:
                        if await plugin.initialize(event_bus):
                            initialized += 1
                    except Exception as e:
                        logger.error(f"Failed to initialize {name}: {e}")
                        plugin.state = PluginState.ERROR

        logger.info(f"Initialized {initialized} plugins")
        return initialized

    async def start_all(self) -> int:
        """
        Start all initialized plugins.

        Returns:
            Number of plugins started
        """
        started = 0

        for name in self._load_order:
            if name in self._plugins:
                plugin = self._plugins[name]

                if plugin.state == PluginState.READY:
                    try:
                        if await plugin.start():
                            started += 1

                            # Emit plugin loaded event
                            if self._event_bus:
                                await self._event_bus.publish(Event(
                                    event_type=EventType.PLUGIN_LOADED,
                                    data={"name": name, "category": plugin.category.value},
                                    source="plugin_loader",
                                ))
                    except Exception as e:
                        logger.error(f"Failed to start {name}: {e}")
                        plugin.state = PluginState.ERROR

        logger.info(f"Started {started} plugins")
        return started

    async def stop_all(self) -> int:
        """
        Stop all running plugins.

        Returns:
            Number of plugins stopped
        """
        stopped = 0

        # Stop in reverse order
        for name in reversed(self._load_order):
            if name in self._plugins:
                plugin = self._plugins[name]

                if plugin.state == PluginState.RUNNING:
                    try:
                        if await plugin.stop():
                            stopped += 1
                    except Exception as e:
                        logger.error(f"Failed to stop {name}: {e}")

        logger.info(f"Stopped {stopped} plugins")
        return stopped

    async def unload_all(self) -> int:
        """
        Unload all plugins.

        Returns:
            Number of plugins unloaded
        """
        await self.stop_all()

        unloaded = 0

        for name in list(self._plugins.keys()):
            plugin = self._plugins[name]

            try:
                if await plugin.unload():
                    del self._plugins[name]
                    unloaded += 1
            except Exception as e:
                logger.error(f"Failed to unload {name}: {e}")

        logger.info(f"Unloaded {unloaded} plugins")
        return unloaded

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def get_plugins_by_category(self, category: PluginCategory) -> List[Plugin]:
        """Get all plugins in a category."""
        return [p for p in self._plugins.values() if p.category == category]

    def get_all_plugins(self) -> Dict[str, Plugin]:
        """Get all loaded plugins."""
        return self._plugins.copy()

    async def reload_plugin(self, name: str) -> bool:
        """
        Reload a plugin (hot reload).

        Args:
            name: Plugin name

        Returns:
            True if reloaded successfully
        """
        if name not in self._plugins:
            return False

        plugin = self._plugins[name]

        # Stop and unload
        await plugin.stop()
        await plugin.unload()
        del self._plugins[name]

        # Reload module
        if name in self._discovered:
            info = self._discovered[name]

            # Force reimport
            if info.module_name in sys.modules:
                del sys.modules[info.module_name]

            # Rediscover and reload
            new_info = self._load_plugin_info(info.path)
            if new_info:
                self._discovered[name] = new_info

                if await self.load_plugin(name):
                    plugin = self._plugins[name]

                    if self._event_bus:
                        await plugin.initialize(self._event_bus)
                        await plugin.start()
                        return True

        return False

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all plugins.

        Returns:
            Dict of plugin name to health status
        """
        results = {}

        for name, plugin in self._plugins.items():
            try:
                health = await plugin.health_check()
                results[name] = {
                    "healthy": health.healthy,
                    "message": health.message,
                    "metrics": health.metrics,
                }
            except Exception as e:
                results[name] = {
                    "healthy": False,
                    "message": str(e),
                    "metrics": {},
                }

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get loader statistics."""
        categories = {}
        for plugin in self._plugins.values():
            cat = plugin.category.value
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "discovered": len(self._discovered),
            "loaded": len(self._plugins),
            "categories": categories,
            "plugin_dirs": [str(d) for d in self._plugin_dirs],
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PluginInfo",
    "PluginLoader",
]
