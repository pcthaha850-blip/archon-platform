# ARCHON_FEAT: ghost-exec-001
"""
ARCHON PRIME - Ghost Executor Plugin
====================================

Stealth execution to minimize market impact and detection.

Features:
- Order time randomization
- Size fragmentation
- Entry point spreading
- Pattern obfuscation

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from archon_prime.core.plugin_base import ExecutionPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_Ghost")


@dataclass
class GhostConfig:
    """Ghost executor configuration."""

    enabled: bool = True
    min_fragments: int = 2
    max_fragments: int = 5
    min_delay_ms: int = 500
    max_delay_ms: int = 3000
    time_jitter_ms: int = 200
    spread_entries: bool = True
    entry_spread_pips: float = 0.5


class GhostExecutor(ExecutionPlugin):
    """
    Ghost Mode Executor.

    Executes orders with stealth characteristics:
    1. Fragments large orders into smaller pieces
    2. Randomizes timing between fragments
    3. Spreads entry points slightly
    4. Adds jitter to avoid pattern detection

    This helps avoid:
    - Broker pattern detection
    - Market impact
    - Front-running
    """

    def __init__(self, config: Optional[GhostConfig] = None):
        super().__init__(PluginConfig(
            name="ghost_executor",
            version="1.0.0",
            category=PluginCategory.EXECUTION,
            settings=config.__dict__ if config else GhostConfig().__dict__,
        ))

        self.ghost_config = config or GhostConfig()
        self._orders_executed = 0
        self._fragments_sent = 0

    async def execute_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute order with ghost mode.

        Args:
            order_data: Order details

        Returns:
            Execution result with fragment details
        """
        if not self.ghost_config.enabled:
            return await self._direct_execute(order_data)

        symbol = order_data.get("symbol")
        direction = order_data.get("direction", 1)
        lot_size = order_data.get("lot_size", 0.01)
        entry_price = order_data.get("entry_price", 0)
        stop_loss = order_data.get("stop_loss")
        take_profit = order_data.get("take_profit")

        # Fragment the order
        fragments = self._create_fragments(lot_size, entry_price)

        self._logger.info(
            f"Ghost executing {symbol}: {lot_size} lots in {len(fragments)} fragments"
        )

        # Execute fragments with delays
        results = []
        for i, fragment in enumerate(fragments):
            # Random delay between fragments
            if i > 0:
                delay = random.randint(
                    self.ghost_config.min_delay_ms,
                    self.ghost_config.max_delay_ms
                )
                # Add jitter
                delay += random.randint(-self.ghost_config.time_jitter_ms,
                                       self.ghost_config.time_jitter_ms)
                delay = max(100, delay)
                await asyncio.sleep(delay / 1000)

            # Execute fragment
            fragment_order = {
                "symbol": symbol,
                "direction": direction,
                "lot_size": fragment["size"],
                "entry_price": fragment["price"],
                "stop_loss": stop_loss if i == 0 else None,  # SL on first only
                "take_profit": take_profit if i == len(fragments) - 1 else None,  # TP on last
                "fragment_id": f"{self._orders_executed}_{i}",
                "is_ghost": True,
            }

            result = await self._send_fragment(fragment_order)
            results.append(result)
            self._fragments_sent += 1

        self._orders_executed += 1

        # Calculate average fill
        total_size = sum(f["size"] for f in fragments)
        avg_price = sum(f["size"] * f["price"] for f in fragments) / total_size if total_size > 0 else entry_price

        # Emit order filled event
        await self._publish(Event(
            event_type=EventType.ORDER_FILLED,
            data={
                "symbol": symbol,
                "direction": direction,
                "lot_size": total_size,
                "avg_fill_price": avg_price,
                "fragments": len(fragments),
                "ghost_mode": True,
            },
            source=self.name,
        ))

        return {
            "success": True,
            "symbol": symbol,
            "total_size": total_size,
            "avg_price": avg_price,
            "fragments": len(fragments),
            "fragment_results": results,
        }

    def _create_fragments(
        self, lot_size: float, entry_price: float
    ) -> List[Dict[str, float]]:
        """Create order fragments."""
        # Determine number of fragments
        if lot_size < 0.05:
            num_fragments = 1  # Too small to fragment
        else:
            num_fragments = random.randint(
                self.ghost_config.min_fragments,
                min(self.ghost_config.max_fragments, int(lot_size / 0.01))
            )

        fragments = []
        remaining = lot_size

        for i in range(num_fragments):
            if i == num_fragments - 1:
                # Last fragment gets remainder
                frag_size = remaining
            else:
                # Random portion of remaining
                min_portion = 0.2
                max_portion = 0.6
                portion = random.uniform(min_portion, max_portion)
                frag_size = remaining * portion

            # Round to 0.01
            frag_size = round(frag_size, 2)
            frag_size = max(0.01, frag_size)

            # Spread entry price slightly
            if self.ghost_config.spread_entries:
                spread = self.ghost_config.entry_spread_pips
                price_offset = random.uniform(-spread, spread) * 0.0001
                frag_price = entry_price + price_offset
            else:
                frag_price = entry_price

            fragments.append({
                "size": frag_size,
                "price": frag_price,
            })

            remaining -= frag_size
            remaining = max(0, remaining)

        return fragments

    async def _send_fragment(self, fragment: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single fragment to broker."""
        # Emit order submit event
        await self._publish(Event(
            event_type=EventType.ORDER_SUBMIT,
            data=fragment,
            source=self.name,
        ))

        # In real implementation, wait for broker response
        return {
            "fragment_id": fragment["fragment_id"],
            "size": fragment["lot_size"],
            "price": fragment["entry_price"],
            "status": "sent",
        }

    async def _direct_execute(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Direct execution without ghost mode."""
        await self._publish(Event(
            event_type=EventType.ORDER_SUBMIT,
            data=order_data,
            source=self.name,
        ))

        return {
            "success": True,
            "ghost_mode": False,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            **super().get_stats(),
            "orders_executed": self._orders_executed,
            "fragments_sent": self._fragments_sent,
            "ghost_mode_enabled": self.ghost_config.enabled,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "GhostConfig",
    "GhostExecutor",
]
