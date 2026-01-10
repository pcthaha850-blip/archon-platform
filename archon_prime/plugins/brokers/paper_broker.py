# ARCHON_FEAT: paper-broker-001
"""
ARCHON PRIME - Paper Broker Plugin
==================================

Simulated broker for paper trading and backtesting.

Features:
- Simulated order execution
- Position tracking
- Realistic slippage simulation
- Account equity management

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from archon_prime.core.plugin_base import BrokerPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_Paper")


@dataclass
class PaperConfig:
    """Paper broker configuration."""

    initial_balance: float = 10000.0
    leverage: int = 100
    commission_per_lot: float = 7.0
    spread_pips: float = 1.5
    slippage_pips: float = 0.5
    slippage_probability: float = 0.3


@dataclass
class PaperPosition:
    """Paper trading position."""

    ticket: int
    symbol: str
    direction: int
    volume: float
    open_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    open_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    current_price: float = 0.0
    profit: float = 0.0


class PaperBroker(BrokerPlugin):
    """
    Paper Trading Broker.

    Simulates a real broker for:
    - Strategy testing
    - Development
    - Backtesting

    Includes realistic features:
    - Spread
    - Slippage
    - Commission
    """

    def __init__(self, config: Optional[PaperConfig] = None):
        super().__init__(PluginConfig(
            name="paper_broker",
            version="1.0.0",
            category=PluginCategory.BROKER,
            settings=config.__dict__ if config else PaperConfig().__dict__,
        ))

        self.paper_config = config or PaperConfig()

        # Account state
        self._balance = self.paper_config.initial_balance
        self._equity = self.paper_config.initial_balance
        self._margin_used = 0.0

        # Positions
        self._positions: Dict[int, PaperPosition] = {}
        self._next_ticket = 1
        self._closed_trades: List[Dict] = []

        # Price simulation
        self._prices: Dict[str, float] = {}

        # Statistics
        self._orders_total = 0
        self._orders_filled = 0

    async def connect(self) -> bool:
        """Connect to paper broker (always succeeds)."""
        self._connected = True
        self._logger.info(
            f"Paper broker connected. Balance: {self._balance:.2f}"
        )
        return True

    async def disconnect(self) -> bool:
        """Disconnect from paper broker."""
        self._connected = False
        return True

    async def submit_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit order to paper broker.

        Args:
            order: Order details

        Returns:
            Order result
        """
        if not self._connected:
            return {"success": False, "error": "Not connected"}

        symbol = order.get("symbol")
        direction = order.get("direction", 1)
        volume = order.get("lot_size", 0.01)
        sl = order.get("stop_loss")
        tp = order.get("take_profit")

        self._orders_total += 1

        # Get price
        base_price = self._get_price(symbol)
        if base_price == 0:
            base_price = order.get("entry_price", 1.0)
            self._prices[symbol] = base_price

        # Apply spread and slippage
        spread = self.paper_config.spread_pips * self._get_pip_value(symbol)
        slippage = 0.0

        if random.random() < self.paper_config.slippage_probability:
            slippage = random.uniform(0, self.paper_config.slippage_pips)
            slippage *= self._get_pip_value(symbol)

        if direction == 1:
            fill_price = base_price + spread / 2 + slippage
        else:
            fill_price = base_price - spread / 2 - slippage

        # Calculate margin
        contract_value = volume * 100000 * fill_price
        margin_required = contract_value / self.paper_config.leverage

        if margin_required > self._equity - self._margin_used:
            return {"success": False, "error": "Insufficient margin"}

        # Create position
        ticket = self._next_ticket
        self._next_ticket += 1

        position = PaperPosition(
            ticket=ticket,
            symbol=symbol,
            direction=direction,
            volume=volume,
            open_price=fill_price,
            sl=sl,
            tp=tp,
            current_price=fill_price,
        )

        self._positions[ticket] = position
        self._margin_used += margin_required
        self._balance -= self.paper_config.commission_per_lot * volume
        self._orders_filled += 1

        # Emit events
        await self._publish(Event(
            event_type=EventType.ORDER_FILLED,
            data={
                "symbol": symbol,
                "direction": direction,
                "lot_size": volume,
                "fill_price": fill_price,
                "ticket": ticket,
            },
            source=self.name,
        ))

        await self._publish(Event(
            event_type=EventType.POSITION_OPENED,
            data={
                "ticket": ticket,
                "symbol": symbol,
                "direction": direction,
                "volume": volume,
                "open_price": fill_price,
            },
            source=self.name,
        ))

        self._logger.info(
            f"Paper order filled: {ticket} {symbol} "
            f"{'BUY' if direction == 1 else 'SELL'} {volume} @ {fill_price:.5f}"
        )

        return {
            "success": True,
            "ticket": ticket,
            "price": fill_price,
            "volume": volume,
        }

    async def close_position(
        self, ticket: int, close_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Close a paper position.

        Args:
            ticket: Position ticket
            close_price: Optional close price

        Returns:
            Close result
        """
        if ticket not in self._positions:
            return {"success": False, "error": "Position not found"}

        position = self._positions[ticket]

        # Get close price
        if close_price is None:
            close_price = self._get_price(position.symbol)
            if close_price == 0:
                close_price = position.current_price

        # Apply spread
        spread = self.paper_config.spread_pips * self._get_pip_value(position.symbol)
        if position.direction == 1:
            close_price -= spread / 2  # Sell at bid
        else:
            close_price += spread / 2  # Buy at ask

        # Calculate profit
        pips = (close_price - position.open_price) * position.direction
        pip_value = self._get_pip_value(position.symbol)
        profit = (pips / pip_value) * position.volume * 10  # Simplified

        # Update account
        self._balance += profit
        self._equity = self._balance + self._get_floating_pl()

        # Release margin
        contract_value = position.volume * 100000 * position.open_price
        margin = contract_value / self.paper_config.leverage
        self._margin_used -= margin

        # Record trade
        self._closed_trades.append({
            "ticket": ticket,
            "symbol": position.symbol,
            "direction": position.direction,
            "volume": position.volume,
            "open_price": position.open_price,
            "close_price": close_price,
            "profit": profit,
            "open_time": position.open_time,
            "close_time": datetime.now(timezone.utc),
        })

        # Remove position
        del self._positions[ticket]

        # Emit event
        await self._publish(Event(
            event_type=EventType.POSITION_CLOSED,
            data={
                "ticket": ticket,
                "symbol": position.symbol,
                "close_price": close_price,
                "realized_pnl": profit,
            },
            source=self.name,
        ))

        self._logger.info(
            f"Paper position closed: {ticket} {position.symbol} "
            f"Profit: {profit:.2f}"
        )

        return {
            "success": True,
            "ticket": ticket,
            "close_price": close_price,
            "profit": profit,
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open paper positions."""
        result = []
        for ticket, pos in self._positions.items():
            result.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "volume": pos.volume,
                "open_price": pos.open_price,
                "current_price": pos.current_price,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "time": pos.open_time,
            })
        return result

    async def get_account_info(self) -> Dict[str, Any]:
        """Get paper account information."""
        return {
            "balance": self._balance,
            "equity": self._equity,
            "margin": self._margin_used,
            "margin_free": self._equity - self._margin_used,
            "margin_level": (
                (self._equity / self._margin_used * 100)
                if self._margin_used > 0 else 0
            ),
            "profit": self._get_floating_pl(),
            "currency": "USD",
        }

    def update_price(self, symbol: str, price: float) -> None:
        """Update price for a symbol."""
        self._prices[symbol] = price

        # Update positions
        for pos in self._positions.values():
            if pos.symbol == symbol:
                pos.current_price = price
                pos.profit = self._calculate_profit(pos, price)

        # Update equity
        self._equity = self._balance + self._get_floating_pl()

    def _get_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        return self._prices.get(symbol, 0.0)

    def _get_pip_value(self, symbol: str) -> float:
        """Get pip value for symbol."""
        if "JPY" in symbol:
            return 0.01
        return 0.0001

    def _calculate_profit(self, position: PaperPosition, current_price: float) -> float:
        """Calculate position profit."""
        pips = (current_price - position.open_price) * position.direction
        pip_value = self._get_pip_value(position.symbol)
        return (pips / pip_value) * position.volume * 10

    def _get_floating_pl(self) -> float:
        """Get total floating P&L."""
        return sum(pos.profit for pos in self._positions.values())

    def get_trade_history(self) -> List[Dict]:
        """Get closed trade history."""
        return self._closed_trades.copy()

    def reset(self) -> None:
        """Reset paper account."""
        self._balance = self.paper_config.initial_balance
        self._equity = self.paper_config.initial_balance
        self._margin_used = 0.0
        self._positions.clear()
        self._closed_trades.clear()
        self._next_ticket = 1
        self._logger.info("Paper account reset")

    def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics."""
        return {
            **super().get_stats(),
            "balance": self._balance,
            "equity": self._equity,
            "open_positions": len(self._positions),
            "closed_trades": len(self._closed_trades),
            "orders_total": self._orders_total,
            "orders_filled": self._orders_filled,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PaperConfig",
    "PaperPosition",
    "PaperBroker",
]
