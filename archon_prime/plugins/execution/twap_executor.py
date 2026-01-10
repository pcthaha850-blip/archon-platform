# ARCHON_FEAT: twap-exec-001
"""
ARCHON PRIME - TWAP Executor Plugin
===================================

Time-Weighted Average Price execution algorithm.

Features:
- Order slicing over time
- Market impact minimization
- Scheduled execution
- Volume participation

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from archon_prime.core.plugin_base import ExecutionPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_TWAP")


@dataclass
class TWAPConfig:
    """TWAP executor configuration."""

    enabled: bool = True
    min_duration_sec: int = 60   # Minimum execution window
    max_duration_sec: int = 3600 # Maximum execution window (1 hour)
    min_slices: int = 3
    max_slices: int = 20
    slice_interval_sec: int = 30
    market_participation_pct: float = 10.0  # Max % of volume


class TWAPExecutor(ExecutionPlugin):
    """
    TWAP (Time-Weighted Average Price) Executor.

    Slices orders over time to minimize market impact
    and achieve average price execution.

    Suitable for:
    - Large orders
    - Illiquid markets
    - When average price is more important than speed

    Algorithm:
    1. Calculate total slices based on size
    2. Spread slices evenly over duration
    3. Execute each slice at scheduled time
    4. Track average fill price
    """

    def __init__(self, config: Optional[TWAPConfig] = None):
        super().__init__(PluginConfig(
            name="twap_executor",
            version="1.0.0",
            category=PluginCategory.EXECUTION,
            settings=config.__dict__ if config else TWAPConfig().__dict__,
        ))

        self.twap_config = config or TWAPConfig()

        # Active TWAP orders
        self._active_orders: Dict[str, Dict[str, Any]] = {}
        self._orders_executed = 0
        self._slices_executed = 0

    async def execute_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute order using TWAP.

        Args:
            order_data: Order details

        Returns:
            TWAP execution result
        """
        if not self.twap_config.enabled:
            return await self._direct_execute(order_data)

        symbol = order_data.get("symbol")
        direction = order_data.get("direction", 1)
        lot_size = order_data.get("lot_size", 0.01)
        duration_sec = order_data.get("twap_duration", self.twap_config.min_duration_sec)

        # Bound duration
        duration_sec = max(self.twap_config.min_duration_sec, duration_sec)
        duration_sec = min(self.twap_config.max_duration_sec, duration_sec)

        # Calculate slices
        num_slices = self._calculate_slices(lot_size, duration_sec)
        slice_size = lot_size / num_slices
        slice_interval = duration_sec / num_slices

        # Create TWAP order
        order_id = f"twap_{datetime.now().timestamp()}"

        self._active_orders[order_id] = {
            "symbol": symbol,
            "direction": direction,
            "total_size": lot_size,
            "remaining_size": lot_size,
            "slice_size": slice_size,
            "num_slices": num_slices,
            "slices_executed": 0,
            "filled_prices": [],
            "start_time": datetime.now(timezone.utc),
            "slice_interval": slice_interval,
            "stop_loss": order_data.get("stop_loss"),
            "take_profit": order_data.get("take_profit"),
        }

        self._logger.info(
            f"TWAP started: {symbol} {lot_size} lots "
            f"over {duration_sec}s in {num_slices} slices"
        )

        # Start TWAP execution
        asyncio.create_task(self._execute_twap(order_id))

        self._orders_executed += 1

        return {
            "success": True,
            "order_id": order_id,
            "symbol": symbol,
            "total_size": lot_size,
            "num_slices": num_slices,
            "duration_sec": duration_sec,
            "status": "started",
        }

    def _calculate_slices(self, lot_size: float, duration_sec: int) -> int:
        """Calculate optimal number of slices."""
        # More slices for larger orders
        size_based = int(lot_size / 0.05)

        # More slices for longer duration
        time_based = int(duration_sec / self.twap_config.slice_interval_sec)

        # Use smaller of the two, within bounds
        num_slices = min(size_based, time_based)
        num_slices = max(self.twap_config.min_slices, num_slices)
        num_slices = min(self.twap_config.max_slices, num_slices)

        return num_slices

    async def _execute_twap(self, order_id: str) -> None:
        """Execute TWAP order slices."""
        if order_id not in self._active_orders:
            return

        order = self._active_orders[order_id]
        num_slices = order["num_slices"]
        slice_interval = order["slice_interval"]

        for i in range(num_slices):
            if order_id not in self._active_orders:
                break  # Order cancelled

            # Execute slice
            await self._execute_slice(order_id, i)

            # Wait for next slice (except for last)
            if i < num_slices - 1:
                await asyncio.sleep(slice_interval)

        # Complete order
        await self._complete_order(order_id)

    async def _execute_slice(self, order_id: str, slice_num: int) -> None:
        """Execute a single slice."""
        order = self._active_orders.get(order_id)
        if not order:
            return

        slice_size = order["slice_size"]
        remaining = order["remaining_size"]

        # Adjust last slice for any remainder
        if slice_num == order["num_slices"] - 1:
            slice_size = remaining
        else:
            slice_size = min(slice_size, remaining)

        slice_size = round(slice_size, 2)
        if slice_size < 0.01:
            return

        # Create slice order
        slice_order = {
            "symbol": order["symbol"],
            "direction": order["direction"],
            "lot_size": slice_size,
            "is_twap_slice": True,
            "twap_order_id": order_id,
            "slice_num": slice_num,
        }

        # Add SL/TP to first/last slice
        if slice_num == 0:
            slice_order["stop_loss"] = order["stop_loss"]
        if slice_num == order["num_slices"] - 1:
            slice_order["take_profit"] = order["take_profit"]

        # Emit order
        await self._publish(Event(
            event_type=EventType.ORDER_SUBMIT,
            data=slice_order,
            source=self.name,
        ))

        # Update order state
        order["remaining_size"] -= slice_size
        order["slices_executed"] += 1
        self._slices_executed += 1

        # Assume fill at current price (in real impl, get actual fill)
        order["filled_prices"].append(slice_order.get("entry_price", 0))

        self._logger.debug(
            f"TWAP slice {slice_num + 1}/{order['num_slices']}: "
            f"{slice_size} lots"
        )

    async def _complete_order(self, order_id: str) -> None:
        """Complete TWAP order and emit result."""
        order = self._active_orders.get(order_id)
        if not order:
            return

        # Calculate TWAP
        prices = order["filled_prices"]
        if prices:
            twap = sum(prices) / len(prices)
        else:
            twap = 0

        duration = (datetime.now(timezone.utc) - order["start_time"]).total_seconds()

        # Emit completion event
        await self._publish(Event(
            event_type=EventType.ORDER_FILLED,
            data={
                "symbol": order["symbol"],
                "direction": order["direction"],
                "lot_size": order["total_size"],
                "avg_fill_price": twap,
                "slices_executed": order["slices_executed"],
                "duration_sec": duration,
                "twap_order_id": order_id,
            },
            source=self.name,
        ))

        self._logger.info(
            f"TWAP complete: {order['symbol']} "
            f"TWAP={twap:.5f} over {duration:.0f}s"
        )

        # Cleanup
        del self._active_orders[order_id]

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an active TWAP order."""
        if order_id in self._active_orders:
            del self._active_orders[order_id]
            self._logger.info(f"TWAP cancelled: {order_id}")
            return True
        return False

    async def _direct_execute(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Direct execution without TWAP."""
        await self._publish(Event(
            event_type=EventType.ORDER_SUBMIT,
            data=order_data,
            source=self.name,
        ))
        return {"success": True, "twap_mode": False}

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            **super().get_stats(),
            "orders_executed": self._orders_executed,
            "slices_executed": self._slices_executed,
            "active_orders": len(self._active_orders),
            "twap_enabled": self.twap_config.enabled,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TWAPConfig",
    "TWAPExecutor",
]
