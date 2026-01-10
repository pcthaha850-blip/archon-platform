# ARCHON_FEAT: plugin-base-001
"""
ARCHON PRIME - Plugin Base Classes
==================================

Base classes and interfaces for all ARCHON PRIME plugins.

Plugin Categories:
- Strategy: Signal generation
- Risk: Position sizing and risk management
- Execution: Order execution and routing
- Broker: Broker connectivity
- Data: Market data feeds
- Monitoring: System monitoring and alerting
- ML: Machine learning models
- Stealth: Ghost mode execution

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .event_bus import EventBus, Event, EventType

logger = logging.getLogger("ARCHON_Plugin")


class PluginCategory(Enum):
    """Plugin categories."""

    STRATEGY = "strategy"
    RISK = "risk"
    EXECUTION = "execution"
    BROKER = "broker"
    DATA = "data"
    MONITORING = "monitoring"
    ML = "ml"
    STEALTH = "stealth"


class PluginState(Enum):
    """Plugin lifecycle state."""

    UNLOADED = auto()
    LOADED = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    ERROR = auto()


@dataclass
class PluginConfig:
    """Plugin configuration."""

    name: str
    version: str = "1.0.0"
    category: PluginCategory = PluginCategory.STRATEGY
    enabled: bool = True
    priority: int = 100  # Lower = higher priority
    dependencies: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "settings": self.settings,
        }


@dataclass
class PluginHealth:
    """Plugin health status."""

    healthy: bool
    message: str = ""
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: Dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """
    Base class for all ARCHON PRIME plugins.

    Plugins are hot-swappable components that provide:
    - Strategy signals
    - Risk management
    - Order execution
    - Broker connectivity
    - Market data
    - Monitoring

    Lifecycle:
        1. load() - Load plugin resources
        2. initialize() - Initialize with event bus
        3. start() - Begin operation
        4. stop() - Clean shutdown
        5. unload() - Release resources

    Example:
        class MyStrategy(Plugin):
            def __init__(self):
                super().__init__(PluginConfig(
                    name="my_strategy",
                    category=PluginCategory.STRATEGY,
                ))

            async def on_tick(self, event: Event):
                # Generate signals
                pass
    """

    def __init__(self, config: PluginConfig):
        self.config = config
        self.state = PluginState.UNLOADED
        self._event_bus: Optional["EventBus"] = None
        self._subscriptions: Set[str] = set()
        self._logger = logging.getLogger(f"ARCHON_{config.name}")
        self._started_at: Optional[datetime] = None
        self._stats = {
            "events_processed": 0,
            "errors": 0,
        }

    @property
    def name(self) -> str:
        """Plugin name."""
        return self.config.name

    @property
    def category(self) -> PluginCategory:
        """Plugin category."""
        return self.config.category

    @property
    def is_running(self) -> bool:
        """Check if plugin is running."""
        return self.state == PluginState.RUNNING

    @property
    def event_bus(self) -> Optional["EventBus"]:
        """Get event bus reference."""
        return self._event_bus

    async def load(self) -> bool:
        """
        Load plugin resources.

        Override to load configuration, models, etc.

        Returns:
            True if loaded successfully
        """
        self.state = PluginState.LOADED
        self._logger.info(f"Plugin loaded: {self.name}")
        return True

    async def initialize(self, event_bus: "EventBus") -> bool:
        """
        Initialize plugin with event bus.

        Args:
            event_bus: Event bus for communication

        Returns:
            True if initialized successfully
        """
        self.state = PluginState.INITIALIZING
        self._event_bus = event_bus

        # Setup subscriptions
        await self._setup_subscriptions()

        self.state = PluginState.READY
        self._logger.info(f"Plugin initialized: {self.name}")
        return True

    @abstractmethod
    async def _setup_subscriptions(self) -> None:
        """Setup event subscriptions. Must be implemented by subclasses."""
        pass

    async def start(self) -> bool:
        """
        Start plugin operation.

        Returns:
            True if started successfully
        """
        if self.state != PluginState.READY:
            self._logger.warning(f"Cannot start plugin in state: {self.state}")
            return False

        self.state = PluginState.RUNNING
        self._started_at = datetime.now(timezone.utc)
        self._logger.info(f"Plugin started: {self.name}")
        return True

    async def stop(self) -> bool:
        """
        Stop plugin operation.

        Returns:
            True if stopped successfully
        """
        self.state = PluginState.STOPPING

        # Cleanup subscriptions
        await self._cleanup_subscriptions()

        self.state = PluginState.LOADED
        self._logger.info(f"Plugin stopped: {self.name}")
        return True

    async def unload(self) -> bool:
        """
        Unload plugin resources.

        Returns:
            True if unloaded successfully
        """
        if self.state == PluginState.RUNNING:
            await self.stop()

        self._event_bus = None
        self.state = PluginState.UNLOADED
        self._logger.info(f"Plugin unloaded: {self.name}")
        return True

    async def pause(self) -> bool:
        """Pause plugin operation."""
        if self.state != PluginState.RUNNING:
            return False

        self.state = PluginState.PAUSED
        self._logger.info(f"Plugin paused: {self.name}")
        return True

    async def resume(self) -> bool:
        """Resume plugin operation."""
        if self.state != PluginState.PAUSED:
            return False

        self.state = PluginState.RUNNING
        self._logger.info(f"Plugin resumed: {self.name}")
        return True

    async def _cleanup_subscriptions(self) -> None:
        """Remove all event subscriptions."""
        if self._event_bus:
            for sub_id in self._subscriptions:
                self._event_bus.unsubscribe(sub_id)
        self._subscriptions.clear()

    def _subscribe(
        self,
        event_types: Set["EventType"],
        handler,
        filter_func=None,
    ) -> str:
        """
        Subscribe to events.

        Args:
            event_types: Event types to subscribe to
            handler: Event handler function
            filter_func: Optional filter function

        Returns:
            Subscription ID
        """
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        sub_id = f"{self.name}_{len(self._subscriptions)}"
        self._event_bus.subscribe(
            sub_id,
            event_types,
            handler,
            filter_func,
        )
        self._subscriptions.add(sub_id)
        return sub_id

    async def _publish(self, event: "Event") -> None:
        """Publish an event."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        await self._event_bus.publish(event)

    async def health_check(self) -> PluginHealth:
        """
        Check plugin health.

        Override to add custom health checks.

        Returns:
            PluginHealth status
        """
        return PluginHealth(
            healthy=self.state in {PluginState.READY, PluginState.RUNNING},
            message=f"State: {self.state.name}",
            metrics={
                "events_processed": self._stats["events_processed"],
                "errors": self._stats["errors"],
                "uptime_seconds": (
                    (datetime.now(timezone.utc) - self._started_at).total_seconds()
                    if self._started_at else 0
                ),
            },
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        return {
            "name": self.name,
            "category": self.category.value,
            "state": self.state.name,
            "enabled": self.config.enabled,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            **self._stats,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name} state={self.state.name}>"


# =============================================================================
# SPECIALIZED BASE CLASSES
# =============================================================================


class StrategyPlugin(Plugin):
    """Base class for strategy plugins."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.STRATEGY
        super().__init__(config)
        self._signals_generated = 0

    @abstractmethod
    async def on_tick(self, event: "Event") -> None:
        """Handle tick event."""
        pass

    @abstractmethod
    async def on_bar(self, event: "Event") -> None:
        """Handle bar event."""
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup strategy subscriptions."""
        from .event_bus import EventType
        self._subscribe({EventType.TICK}, self._handle_tick)
        self._subscribe({EventType.BAR}, self._handle_bar)

    async def _handle_tick(self, event: "Event") -> None:
        """Wrapper for tick handler."""
        try:
            await self.on_tick(event)
            self._stats["events_processed"] += 1
        except Exception as e:
            self._logger.error(f"Tick handler error: {e}")
            self._stats["errors"] += 1

    async def _handle_bar(self, event: "Event") -> None:
        """Wrapper for bar handler."""
        try:
            await self.on_bar(event)
            self._stats["events_processed"] += 1
        except Exception as e:
            self._logger.error(f"Bar handler error: {e}")
            self._stats["errors"] += 1


class RiskPlugin(Plugin):
    """Base class for risk management plugins."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.RISK
        super().__init__(config)

    @abstractmethod
    async def evaluate_risk(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate risk for a signal.

        Args:
            signal_data: Signal data to evaluate

        Returns:
            Risk evaluation with position size, approval, etc.
        """
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup risk subscriptions."""
        from .event_bus import EventType
        self._subscribe({EventType.SIGNAL_GENERATED}, self._handle_signal)
        self._subscribe({EventType.POSITION_OPENED, EventType.POSITION_CLOSED},
                       self._handle_position)

    async def _handle_signal(self, event: "Event") -> None:
        """Handle signal for risk evaluation."""
        try:
            result = await self.evaluate_risk(event.data)
            self._stats["events_processed"] += 1
        except Exception as e:
            self._logger.error(f"Risk evaluation error: {e}")
            self._stats["errors"] += 1

    async def _handle_position(self, event: "Event") -> None:
        """Handle position updates."""
        self._stats["events_processed"] += 1


class ExecutionPlugin(Plugin):
    """Base class for execution plugins."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.EXECUTION
        super().__init__(config)

    @abstractmethod
    async def execute_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an order.

        Args:
            order_data: Order details

        Returns:
            Execution result
        """
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup execution subscriptions."""
        from .event_bus import EventType
        self._subscribe({EventType.SIGNAL_APPROVED}, self._handle_approved_signal)

    async def _handle_approved_signal(self, event: "Event") -> None:
        """Handle approved signal for execution."""
        try:
            await self.execute_order(event.data)
            self._stats["events_processed"] += 1
        except Exception as e:
            self._logger.error(f"Execution error: {e}")
            self._stats["errors"] += 1


class BrokerPlugin(Plugin):
    """Base class for broker adapters."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.BROKER
        super().__init__(config)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to broker."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from broker."""
        pass

    @abstractmethod
    async def submit_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Submit order to broker."""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        pass

    @abstractmethod
    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup broker subscriptions."""
        from .event_bus import EventType
        self._subscribe({EventType.ORDER_SUBMIT}, self._handle_order_submit)

    async def _handle_order_submit(self, event: "Event") -> None:
        """Handle order submission."""
        try:
            await self.submit_order(event.data)
            self._stats["events_processed"] += 1
        except Exception as e:
            self._logger.error(f"Order submit error: {e}")
            self._stats["errors"] += 1


class DataPlugin(Plugin):
    """Base class for data feed plugins."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.DATA
        super().__init__(config)

    @abstractmethod
    async def subscribe_symbol(self, symbol: str) -> bool:
        """Subscribe to market data for symbol."""
        pass

    @abstractmethod
    async def unsubscribe_symbol(self, symbol: str) -> bool:
        """Unsubscribe from market data."""
        pass

    @abstractmethod
    async def get_historical(
        self, symbol: str, timeframe: str, bars: int
    ) -> List[Dict[str, Any]]:
        """Get historical data."""
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup data subscriptions."""
        pass  # Data plugins typically produce events, not consume them


class MonitoringPlugin(Plugin):
    """Base class for monitoring plugins."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.MONITORING
        super().__init__(config)

    @abstractmethod
    async def record_metric(self, name: str, value: float, tags: Dict[str, str]) -> None:
        """Record a metric."""
        pass

    @abstractmethod
    async def send_alert(self, level: str, message: str, context: Dict[str, Any]) -> None:
        """Send an alert."""
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup monitoring subscriptions."""
        from .event_bus import EventType
        # Subscribe to all events for monitoring
        self._subscribe(
            {EventType.RISK_ALERT, EventType.SYSTEM_ERROR, EventType.DRAWDOWN_WARNING},
            self._handle_alert_event
        )

    async def _handle_alert_event(self, event: "Event") -> None:
        """Handle alert events."""
        self._stats["events_processed"] += 1


class MLPlugin(Plugin):
    """Base class for ML plugins."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.ML
        super().__init__(config)
        self._model_loaded = False

    @abstractmethod
    async def load_model(self) -> bool:
        """Load ML model."""
        pass

    @abstractmethod
    async def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Make prediction."""
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup ML subscriptions."""
        from .event_bus import EventType
        self._subscribe({EventType.TICK, EventType.BAR}, self._handle_data)

    async def _handle_data(self, event: "Event") -> None:
        """Handle data for ML processing."""
        self._stats["events_processed"] += 1


class StealthPlugin(Plugin):
    """Base class for stealth/ghost mode plugins."""

    def __init__(self, config: PluginConfig):
        config.category = PluginCategory.STEALTH
        super().__init__(config)
        self._ghost_mode_active = False

    @property
    def is_ghost_mode(self) -> bool:
        """Check if ghost mode is active."""
        return self._ghost_mode_active

    @abstractmethod
    async def mask_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Apply stealth masking to order."""
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup stealth subscriptions."""
        from .event_bus import EventType
        self._subscribe({EventType.ORDER_SUBMIT}, self._handle_order)

    async def _handle_order(self, event: "Event") -> None:
        """Handle order for stealth processing."""
        self._stats["events_processed"] += 1


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PluginCategory",
    "PluginState",
    "PluginConfig",
    "PluginHealth",
    "Plugin",
    "StrategyPlugin",
    "RiskPlugin",
    "ExecutionPlugin",
    "BrokerPlugin",
    "DataPlugin",
    "MonitoringPlugin",
    "MLPlugin",
    "StealthPlugin",
]
