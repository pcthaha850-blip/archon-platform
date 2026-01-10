# ARCHON PRIME Execution Plugins
"""
Execution plugins for order management.

Available Plugins:
    - Ghost Executor (stealth execution)
    - TWAP Executor (time-weighted average price)
    - Iceberg Executor (hidden size orders)
    - Smart Router (best execution routing)
"""

from .ghost_executor import GhostExecutor
from .twap_executor import TWAPExecutor

__all__ = [
    "GhostExecutor",
    "TWAPExecutor",
]
