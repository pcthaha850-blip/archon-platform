# ARCHON PRIME - Production Trading Platform
"""
ARCHON PRIME: Institutional-grade production trading platform.

Core Components:
    - Event Bus: Async pub/sub communication
    - Plugin System: Hot-swappable modules
    - Orchestrator: Central coordination

Plugin Categories:
    - Strategies: Signal generation (TSM, VMR, RWEC)
    - Risk: Position sizing and risk control
    - Execution: Order execution algorithms
    - Brokers: Broker connectivity
    - Monitoring: System observability
    - ML: Machine learning models
    - Stealth: Ghost mode execution

Example:
    from archon_prime import Orchestrator

    orchestrator = Orchestrator()
    await orchestrator.start("config/live.yaml")
    await orchestrator.run_forever()

Author: ARCHON Development Team
Version: 2.0.0
"""

from archon_prime.core.event_bus import EventBus, Event, EventType
from archon_prime.core.plugin_base import (
    Plugin,
    PluginConfig,
    PluginState,
    PluginCategory,
    StrategyPlugin,
    RiskPlugin,
    ExecutionPlugin,
    BrokerPlugin,
)
from archon_prime.core.plugin_loader import PluginLoader
from archon_prime.core.config_manager import ConfigManager
from archon_prime.core.orchestrator import Orchestrator

__version__ = "2.0.0"
__author__ = "ARCHON Development Team"

__all__ = [
    # Core
    "EventBus",
    "Event",
    "EventType",
    "Plugin",
    "PluginConfig",
    "PluginState",
    "PluginCategory",
    "PluginLoader",
    "ConfigManager",
    "Orchestrator",
    # Base plugins
    "StrategyPlugin",
    "RiskPlugin",
    "ExecutionPlugin",
    "BrokerPlugin",
]
