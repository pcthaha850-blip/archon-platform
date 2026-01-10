"""
ARCHON RI v6.3 - Position Manager
==================================

Manages trading position state including:
- Position tracking (open/close)
- P&L calculation (realized/unrealized)
- Stop loss and take profit management
- Position size scaling

Author: ARCHON RI Development Team
Version: 6.3.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARCHON_PositionManager")


class PositionSide(Enum):
    """Position side/direction."""

    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(Enum):
    """Position lifecycle status."""

    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    CLOSED = "CLOSED"


@dataclass
class PositionState:
    """Serializable position state for persistence."""

    symbol: str
    direction: int  # 1 = long, -1 = short
    entry_price: float
    entry_time: str  # ISO format
    volume: float
    sl_price: float
    tp_price: float
    trailing_sl: Optional[float] = None
    order_id: Optional[str] = None
    broker_ticket: Optional[int] = None
    unrealized_pnl: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time,
            "volume": self.volume,
            "sl_price": self.sl_price,
            "tp_price": self.tp_price,
            "trailing_sl": self.trailing_sl,
            "order_id": self.order_id,
            "broker_ticket": self.broker_ticket,
            "unrealized_pnl": self.unrealized_pnl,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PositionState":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class Position:
    """Active trading position."""

    symbol: str
    side: PositionSide
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    ticket: Optional[int] = None
    strategy: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def direction(self) -> int:
        """Get numeric direction (+1 long, -1 short)."""
        return 1 if self.side == PositionSide.LONG else -1

    def update_price(self, current_price: float) -> float:
        """Update current price and recalculate unrealized P&L."""
        self.current_price = current_price

        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity

        return self.unrealized_pnl

    def to_state(self) -> PositionState:
        """Convert to persistence state."""
        return PositionState(
            symbol=self.symbol,
            direction=self.direction,
            entry_price=self.entry_price,
            entry_time=self.opened_at.isoformat(),
            volume=self.quantity,
            sl_price=self.stop_loss or 0.0,
            tp_price=self.take_profit or 0.0,
            trailing_sl=self.trailing_stop,
            broker_ticket=self.ticket,
            unrealized_pnl=self.unrealized_pnl,
        )


@dataclass
class PositionManagerConfig:
    """Configuration for Position Manager."""

    max_positions: int = 5
    max_positions_per_symbol: int = 1
    default_stop_loss_pct: float = 2.0
    default_take_profit_pct: float = 4.0
    trailing_stop_activation_pct: float = 1.5
    trailing_stop_distance_pct: float = 0.5
    log_position_changes: bool = True


class PositionManager:
    """
    Manages trading positions and calculates P&L.

    Handles position lifecycle from open to close,
    including stop loss, take profit, and trailing stop management.

    Example:
        manager = PositionManager(config)

        # Open a position
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
            stop_loss=1.0800,
            take_profit=1.0950,
        )

        # Update prices
        manager.update_prices({"EURUSD": 1.0870})

        # Check exits
        exits = manager.check_exits({"EURUSD": 1.0870})
    """

    def __init__(self, config: Optional[PositionManagerConfig] = None):
        self.cfg = config or PositionManagerConfig()

        # Position storage
        self._positions: Dict[int, Position] = {}  # ticket -> Position
        self._next_ticket: int = 1

        # Statistics
        self._stats = {
            "total_opened": 0,
            "total_closed": 0,
            "total_realized_pnl": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
        }

        logger.info(
            f"PositionManager initialized: max_positions={self.cfg.max_positions}"
        )

    def open_position(
        self,
        symbol: str,
        side: PositionSide,
        quantity: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        strategy: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Position]:
        """
        Open a new position.

        Args:
            symbol: Trading pair/symbol
            side: LONG or SHORT
            quantity: Position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            strategy: Strategy name
            metadata: Additional data

        Returns:
            Position if opened, None if blocked
        """
        # Check position limits
        if len(self._positions) >= self.cfg.max_positions:
            logger.warning(f"Position limit reached: {self.cfg.max_positions}")
            return None

        # Check per-symbol limit
        symbol_positions = sum(
            1 for p in self._positions.values() if p.symbol == symbol
        )
        if symbol_positions >= self.cfg.max_positions_per_symbol:
            logger.warning(f"Symbol position limit reached for {symbol}")
            return None

        # Create position
        ticket = self._next_ticket
        self._next_ticket += 1

        position = Position(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            ticket=ticket,
            strategy=strategy,
            metadata=metadata or {},
        )

        self._positions[ticket] = position
        self._stats["total_opened"] += 1

        if self.cfg.log_position_changes:
            logger.info(
                f"Position opened: {ticket} {symbol} {side.value} "
                f"qty={quantity} @ {entry_price}"
            )

        return position

    def close_position(
        self,
        ticket: int,
        close_price: float,
        reason: str = "manual",
    ) -> Optional[float]:
        """
        Close a position and calculate realized P&L.

        Args:
            ticket: Position ticket
            close_price: Closing price
            reason: Close reason

        Returns:
            Realized P&L if closed, None if not found
        """
        if ticket not in self._positions:
            logger.warning(f"Position not found: {ticket}")
            return None

        position = self._positions[ticket]

        # Calculate realized P&L
        if position.side == PositionSide.LONG:
            realized_pnl = (close_price - position.entry_price) * position.quantity
        else:
            realized_pnl = (position.entry_price - close_price) * position.quantity

        # Update position
        position.realized_pnl = realized_pnl
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.now(timezone.utc)
        position.metadata["close_reason"] = reason
        position.metadata["close_price"] = close_price

        # Update statistics
        self._stats["total_closed"] += 1
        self._stats["total_realized_pnl"] += realized_pnl

        if realized_pnl > 0:
            self._stats["winning_trades"] += 1
        else:
            self._stats["losing_trades"] += 1

        # Remove from active positions
        del self._positions[ticket]

        if self.cfg.log_position_changes:
            logger.info(
                f"Position closed: {ticket} {position.symbol} "
                f"pnl={realized_pnl:.2f} reason={reason}"
            )

        return realized_pnl

    def get_position(self, ticket: int) -> Optional[Position]:
        """Get position by ticket."""
        return self._positions.get(ticket)

    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a symbol."""
        return [p for p in self._positions.values() if p.symbol == symbol]

    def get_all_positions(self) -> Dict[int, Position]:
        """Get all open positions."""
        return self._positions.copy()

    def update_prices(self, prices: Dict[str, float]) -> Dict[int, float]:
        """
        Update position prices and calculate unrealized P&L.

        Args:
            prices: Symbol -> current price

        Returns:
            Dict of ticket -> unrealized P&L
        """
        pnl_updates = {}

        for ticket, position in self._positions.items():
            if position.symbol in prices:
                pnl = position.update_price(prices[position.symbol])
                pnl_updates[ticket] = pnl

        return pnl_updates

    def check_exits(
        self, prices: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Check all positions for stop loss or take profit triggers.

        Args:
            prices: Symbol -> current price

        Returns:
            List of exit signals with ticket and reason
        """
        exits = []

        for ticket, position in self._positions.items():
            if position.symbol not in prices:
                continue

            current_price = prices[position.symbol]
            exit_signal = self._check_position_exit(position, current_price)

            if exit_signal:
                exits.append({
                    "ticket": ticket,
                    "symbol": position.symbol,
                    "side": position.side.value,
                    "reason": exit_signal["reason"],
                    "current_price": current_price,
                    "exit_price": exit_signal.get("price", current_price),
                })

        return exits

    def _check_position_exit(
        self, position: Position, current_price: float
    ) -> Optional[Dict[str, Any]]:
        """Check if a single position should exit."""
        # Check stop loss
        if position.stop_loss:
            if position.side == PositionSide.LONG:
                if current_price <= position.stop_loss:
                    return {"reason": "stop_loss", "price": position.stop_loss}
            else:
                if current_price >= position.stop_loss:
                    return {"reason": "stop_loss", "price": position.stop_loss}

        # Check take profit
        if position.take_profit:
            if position.side == PositionSide.LONG:
                if current_price >= position.take_profit:
                    return {"reason": "take_profit", "price": position.take_profit}
            else:
                if current_price <= position.take_profit:
                    return {"reason": "take_profit", "price": position.take_profit}

        # Check trailing stop
        if position.trailing_stop:
            if position.side == PositionSide.LONG:
                if current_price <= position.trailing_stop:
                    return {"reason": "trailing_stop", "price": position.trailing_stop}
            else:
                if current_price >= position.trailing_stop:
                    return {"reason": "trailing_stop", "price": position.trailing_stop}

        return None

    def update_trailing_stop(
        self, ticket: int, current_price: float
    ) -> Optional[float]:
        """
        Update trailing stop for a position.

        Args:
            ticket: Position ticket
            current_price: Current market price

        Returns:
            New trailing stop if updated, None otherwise
        """
        if ticket not in self._positions:
            return None

        position = self._positions[ticket]
        activation_pct = self.cfg.trailing_stop_activation_pct / 100
        distance_pct = self.cfg.trailing_stop_distance_pct / 100

        # Calculate profit percentage
        if position.side == PositionSide.LONG:
            profit_pct = (current_price - position.entry_price) / position.entry_price

            if profit_pct >= activation_pct:
                new_trailing = current_price * (1 - distance_pct)

                if position.trailing_stop is None or new_trailing > position.trailing_stop:
                    position.trailing_stop = new_trailing
                    return new_trailing
        else:
            profit_pct = (position.entry_price - current_price) / position.entry_price

            if profit_pct >= activation_pct:
                new_trailing = current_price * (1 + distance_pct)

                if position.trailing_stop is None or new_trailing < position.trailing_stop:
                    position.trailing_stop = new_trailing
                    return new_trailing

        return None

    def get_total_exposure(self) -> float:
        """Get total position exposure (sum of position values)."""
        total = 0.0
        for position in self._positions.values():
            total += position.quantity * position.current_price
        return total

    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L across all positions."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_statistics(self) -> Dict[str, Any]:
        """Get position manager statistics."""
        win_rate = 0.0
        total_trades = self._stats["winning_trades"] + self._stats["losing_trades"]
        if total_trades > 0:
            win_rate = self._stats["winning_trades"] / total_trades * 100

        return {
            "open_positions": len(self._positions),
            "total_opened": self._stats["total_opened"],
            "total_closed": self._stats["total_closed"],
            "total_realized_pnl": self._stats["total_realized_pnl"],
            "total_unrealized_pnl": self.get_total_unrealized_pnl(),
            "winning_trades": self._stats["winning_trades"],
            "losing_trades": self._stats["losing_trades"],
            "win_rate_pct": win_rate,
            "total_exposure": self.get_total_exposure(),
        }

    def reset(self) -> None:
        """Reset all positions and statistics."""
        self._positions.clear()
        self._stats = {
            "total_opened": 0,
            "total_closed": 0,
            "total_realized_pnl": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
        }
        logger.info("PositionManager reset")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PositionSide",
    "PositionStatus",
    "PositionState",
    "Position",
    "PositionManagerConfig",
    "PositionManager",
]
