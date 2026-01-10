"""
Tests for ARCHON PRIME Plugin Base
==================================

Tests the plugin base classes and lifecycle.
"""

import pytest
import asyncio
from datetime import datetime, timezone

from archon_prime.core.event_bus import EventBus, Event, EventType
from archon_prime.core.plugin_base import (
    Plugin,
    PluginConfig,
    PluginState,
    PluginCategory,
    PluginHealth,
    StrategyPlugin,
    RiskPlugin,
)


class SamplePlugin(Plugin):
    """Sample plugin implementation for testing."""

    def __init__(self):
        super().__init__(PluginConfig(
            name="test_plugin",
            version="1.0.0",
            category=PluginCategory.STRATEGY,
        ))
        self.events_received = []

    async def _setup_subscriptions(self):
        self._subscribe(
            {EventType.TICK},
            self._handle_tick,
        )

    async def _handle_tick(self, event):
        self.events_received.append(event)


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def test_plugin():
    """Create a test plugin."""
    return SamplePlugin()


class TestPluginConfig:
    """Tests for plugin configuration."""

    def test_config_defaults(self):
        """Should have sensible defaults."""
        config = PluginConfig(name="test")
        assert config.enabled is True
        assert config.priority == 100
        assert config.dependencies == []

    def test_config_to_dict(self):
        """Should convert to dictionary."""
        config = PluginConfig(
            name="test",
            version="2.0.0",
            category=PluginCategory.RISK,
        )
        data = config.to_dict()
        assert data["name"] == "test"
        assert data["category"] == "risk"


class TestPluginLifecycle:
    """Tests for plugin lifecycle."""

    @pytest.mark.asyncio
    async def test_initial_state(self, test_plugin):
        """Plugin should start unloaded."""
        assert test_plugin.state == PluginState.UNLOADED

    @pytest.mark.asyncio
    async def test_load(self, test_plugin):
        """Should transition to LOADED state."""
        await test_plugin.load()
        assert test_plugin.state == PluginState.LOADED

    @pytest.mark.asyncio
    async def test_initialize(self, test_plugin, event_bus):
        """Should transition to READY state."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        assert test_plugin.state == PluginState.READY
        assert test_plugin.event_bus is event_bus

    @pytest.mark.asyncio
    async def test_start(self, test_plugin, event_bus):
        """Should transition to RUNNING state."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()
        assert test_plugin.state == PluginState.RUNNING
        assert test_plugin.is_running

    @pytest.mark.asyncio
    async def test_stop(self, test_plugin, event_bus):
        """Should transition back to LOADED state."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()
        await test_plugin.stop()
        assert test_plugin.state == PluginState.LOADED

    @pytest.mark.asyncio
    async def test_unload(self, test_plugin, event_bus):
        """Should transition to UNLOADED state."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()
        await test_plugin.unload()
        assert test_plugin.state == PluginState.UNLOADED
        assert test_plugin.event_bus is None


class TestPluginPauseResume:
    """Tests for pause/resume functionality."""

    @pytest.mark.asyncio
    async def test_pause(self, test_plugin, event_bus):
        """Should pause running plugin."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()

        result = await test_plugin.pause()
        assert result is True
        assert test_plugin.state == PluginState.PAUSED

    @pytest.mark.asyncio
    async def test_resume(self, test_plugin, event_bus):
        """Should resume paused plugin."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()
        await test_plugin.pause()

        result = await test_plugin.resume()
        assert result is True
        assert test_plugin.state == PluginState.RUNNING


class TestPluginSubscriptions:
    """Tests for event subscriptions."""

    @pytest.mark.asyncio
    async def test_receives_events(self, test_plugin, event_bus):
        """Plugin should receive subscribed events."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()

        await event_bus.publish_sync(Event(
            event_type=EventType.TICK,
            data={"symbol": "EURUSD"},
            source="test",
        ))

        assert len(test_plugin.events_received) == 1


class TestPluginHealth:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check_running(self, test_plugin, event_bus):
        """Should report healthy when running."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()

        health = await test_plugin.health_check()
        assert health.healthy is True

    @pytest.mark.asyncio
    async def test_health_check_not_running(self, test_plugin):
        """Should report unhealthy when not running."""
        health = await test_plugin.health_check()
        assert health.healthy is False


class TestPluginStats:
    """Tests for plugin statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, test_plugin, event_bus):
        """Should return statistics."""
        await test_plugin.load()
        await test_plugin.initialize(event_bus)
        await test_plugin.start()

        stats = test_plugin.get_stats()
        assert stats["name"] == "test_plugin"
        assert stats["state"] == "RUNNING"
        assert stats["enabled"] is True


class TestPluginHealthDataclass:
    """Tests for PluginHealth dataclass."""

    def test_health_creation(self):
        """Should create health status."""
        health = PluginHealth(
            healthy=True,
            message="All systems operational",
        )
        assert health.healthy is True
        assert health.message == "All systems operational"
        assert health.last_check is not None
