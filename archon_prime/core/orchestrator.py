# ARCHON_FEAT: orchestrator-001
"""
ARCHON PRIME - Main Orchestrator
================================

Central orchestrator that coordinates all ARCHON PRIME components.

Features:
- Lifecycle management for all plugins
- Health monitoring
- Graceful shutdown
- Error recovery

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .event_bus import EventBus, Event, EventType
from .plugin_loader import PluginLoader
from .config_manager import ConfigManager
from .plugin_base import PluginCategory, Plugin

logger = logging.getLogger("ARCHON_Orchestrator")


class Orchestrator:
    """
    Main orchestrator for ARCHON PRIME.

    Coordinates:
    - Configuration loading
    - Plugin lifecycle
    - Event bus management
    - Health monitoring
    - Graceful shutdown

    Example:
        orchestrator = Orchestrator()
        await orchestrator.start("config/live.yaml")

        # Run until shutdown
        await orchestrator.run_forever()

        await orchestrator.shutdown()
    """

    def __init__(self):
        self._event_bus = EventBus()
        self._plugin_loader = PluginLoader()
        self._config_manager = ConfigManager()

        self._running = False
        self._started_at: Optional[datetime] = None
        self._shutdown_event = asyncio.Event()

        # Background tasks
        self._health_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None

        logger.info("Orchestrator initialized")

    @property
    def event_bus(self) -> EventBus:
        """Get event bus."""
        return self._event_bus

    @property
    def plugin_loader(self) -> PluginLoader:
        """Get plugin loader."""
        return self._plugin_loader

    @property
    def config(self) -> ConfigManager:
        """Get config manager."""
        return self._config_manager

    @property
    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running

    async def start(
        self,
        config_path: Optional[str] = None,
        plugin_dirs: Optional[List[str]] = None,
    ) -> bool:
        """
        Start the orchestrator.

        Args:
            config_path: Path to configuration file
            plugin_dirs: List of plugin directories

        Returns:
            True if started successfully
        """
        logger.info("Starting ARCHON PRIME Orchestrator...")

        # Load configuration
        if config_path:
            if not self._config_manager.load(Path(config_path)):
                logger.error("Failed to load configuration")
                return False

        # Validate configuration
        errors = self._config_manager.validate()
        if errors:
            for error in errors:
                logger.error(f"Config error: {error}")
            return False

        # Start event bus
        await self._event_bus.start()

        # Discover plugins
        if plugin_dirs:
            for plugin_dir in plugin_dirs:
                self._plugin_loader.add_plugin_dir(Path(plugin_dir))

        self._plugin_loader.discover_plugins()

        # Load and initialize plugins
        await self._plugin_loader.load_all()
        await self._plugin_loader.initialize_all(self._event_bus)
        await self._plugin_loader.start_all()

        # Start background tasks
        self._health_task = asyncio.create_task(self._health_monitor())
        self._metrics_task = asyncio.create_task(self._metrics_reporter())

        # Emit system start event
        await self._event_bus.publish(Event(
            event_type=EventType.SYSTEM_START,
            data={
                "mode": self._config_manager.config.mode,
                "plugins_loaded": len(self._plugin_loader.get_all_plugins()),
            },
            source="orchestrator",
        ))

        self._running = True
        self._started_at = datetime.now(timezone.utc)

        logger.info("ARCHON PRIME Orchestrator started")
        logger.info(f"Mode: {self._config_manager.config.mode.upper()}")
        logger.info(f"Plugins: {len(self._plugin_loader.get_all_plugins())}")

        return True

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        if not self._running:
            return

        logger.info("Shutting down ARCHON PRIME...")

        self._running = False
        self._shutdown_event.set()

        # Cancel background tasks
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass

        # Emit system stop event
        await self._event_bus.publish(Event(
            event_type=EventType.SYSTEM_STOP,
            data={"uptime_seconds": self._get_uptime()},
            source="orchestrator",
        ))

        # Stop all plugins
        await self._plugin_loader.stop_all()
        await self._plugin_loader.unload_all()

        # Stop event bus
        await self._event_bus.stop()

        logger.info("ARCHON PRIME shutdown complete")

    async def run_forever(self) -> None:
        """Run until shutdown signal."""
        # Setup signal handlers
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        # Wait for shutdown
        await self._shutdown_event.wait()

    async def _health_monitor(self) -> None:
        """Background health monitoring."""
        interval = self._config_manager.monitoring.health_check_interval_sec

        while self._running:
            try:
                await asyncio.sleep(interval)

                if not self._running:
                    break

                # Check all plugins
                health_results = await self._plugin_loader.health_check_all()

                # Check for unhealthy plugins
                unhealthy = [
                    name for name, status in health_results.items()
                    if not status["healthy"]
                ]

                if unhealthy:
                    logger.warning(f"Unhealthy plugins: {unhealthy}")

                    # Emit health check event
                    await self._event_bus.publish(Event(
                        event_type=EventType.HEALTH_CHECK,
                        data={
                            "healthy_count": len(health_results) - len(unhealthy),
                            "unhealthy_count": len(unhealthy),
                            "unhealthy_plugins": unhealthy,
                        },
                        source="orchestrator",
                    ))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def _metrics_reporter(self) -> None:
        """Background metrics reporting."""
        interval = self._config_manager.monitoring.metrics_interval_sec

        while self._running:
            try:
                await asyncio.sleep(interval)

                if not self._running:
                    break

                # Gather metrics
                metrics = self.get_metrics()

                # Emit metrics event
                await self._event_bus.publish(Event(
                    event_type=EventType.METRICS_UPDATE,
                    data=metrics,
                    source="orchestrator",
                ))

                # Emit heartbeat
                await self._event_bus.publish(Event(
                    event_type=EventType.HEARTBEAT,
                    data={"uptime_seconds": self._get_uptime()},
                    source="orchestrator",
                ))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics reporter error: {e}")

    def _get_uptime(self) -> float:
        """Get uptime in seconds."""
        if not self._started_at:
            return 0.0
        return (datetime.now(timezone.utc) - self._started_at).total_seconds()

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugin_loader.get_plugin(name)

    def get_plugins_by_category(self, category: PluginCategory) -> List[Plugin]:
        """Get all plugins in a category."""
        return self._plugin_loader.get_plugins_by_category(category)

    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        return {
            "uptime_seconds": self._get_uptime(),
            "mode": self._config_manager.config.mode,
            "event_bus": self._event_bus.get_stats(),
            "plugins": self._plugin_loader.get_stats(),
            "config": self._config_manager.get_info(),
        }

    async def register_plugin(self, plugin: Plugin) -> bool:
        """
        Register a plugin at runtime.

        Args:
            plugin: Plugin instance to register

        Returns:
            True if registered successfully
        """
        self._plugin_loader.register_plugin(plugin)

        if await plugin.load():
            if await plugin.initialize(self._event_bus):
                if await plugin.start():
                    logger.info(f"Plugin registered and started: {plugin.name}")
                    return True

        return False

    async def reload_plugin(self, name: str) -> bool:
        """
        Reload a plugin.

        Args:
            name: Plugin name

        Returns:
            True if reloaded successfully
        """
        return await self._plugin_loader.reload_plugin(name)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "Orchestrator",
]
