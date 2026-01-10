# ARCHON Brokers - Broker Adapters
"""
Broker connectivity adapters.

Modules:
    base: Abstract broker interface
    mt5_adapter: MetaTrader 5 adapter (Windows only)
    oanda_adapter: OANDA v20 REST API
    ib_adapter: Interactive Brokers via ib_insync
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseBroker

__all__ = [
    "BaseBroker",
]
