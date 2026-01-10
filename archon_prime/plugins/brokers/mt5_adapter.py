# ARCHON_FEAT: mt5-adapter-001
"""
ARCHON PRIME - MT5 Broker Adapter
=================================

MetaTrader 5 broker connectivity and order management.

Features:
- Connection management with auto-reconnect
- Order execution (market, limit, stop)
- Position tracking
- Real-time quotes
- Historical data

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from archon_prime.core.plugin_base import BrokerPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_MT5")


@dataclass
class MT5Config:
    """MT5 adapter configuration."""

    server: str = ""
    login: int = 0
    password: str = ""
    path: str = ""  # Path to terminal64.exe
    timeout: int = 60000
    auto_reconnect: bool = True
    reconnect_delay_sec: int = 5
    max_reconnect_attempts: int = 10


class MT5Adapter(BrokerPlugin):
    """
    MetaTrader 5 Broker Adapter.

    Provides connectivity to MT5 brokers for:
    - Order execution
    - Position management
    - Market data
    - Account information

    Requires MetaTrader5 Python package.
    """

    def __init__(self, config: Optional[MT5Config] = None):
        super().__init__(PluginConfig(
            name="mt5_adapter",
            version="1.0.0",
            category=PluginCategory.BROKER,
            settings=config.__dict__ if config else MT5Config().__dict__,
        ))

        self.mt5_config = config or MT5Config()
        self._mt5 = None  # MT5 module reference
        self._reconnect_attempts = 0
        self._subscribed_symbols: set = set()
        self._last_tick: Dict[str, Dict] = {}
        self._orders_sent = 0
        self._orders_filled = 0

    async def connect(self) -> bool:
        """
        Connect to MT5 terminal.

        Returns:
            True if connected successfully
        """
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            self._logger.error("MetaTrader5 package not installed")
            return False

        # Initialize MT5
        init_params = {}
        if self.mt5_config.path:
            init_params["path"] = self.mt5_config.path
        if self.mt5_config.login:
            init_params["login"] = self.mt5_config.login
        if self.mt5_config.password:
            init_params["password"] = self.mt5_config.password
        if self.mt5_config.server:
            init_params["server"] = self.mt5_config.server
        if self.mt5_config.timeout:
            init_params["timeout"] = self.mt5_config.timeout

        if not self._mt5.initialize(**init_params):
            error = self._mt5.last_error()
            self._logger.error(f"MT5 initialization failed: {error}")
            return False

        self._connected = True
        self._reconnect_attempts = 0

        # Get account info
        account_info = await self.get_account_info()
        self._logger.info(
            f"MT5 connected: {account_info.get('name', 'Unknown')} "
            f"Balance: {account_info.get('balance', 0):.2f}"
        )

        return True

    async def disconnect(self) -> bool:
        """
        Disconnect from MT5 terminal.

        Returns:
            True if disconnected successfully
        """
        if self._mt5:
            self._mt5.shutdown()
            self._connected = False
            self._logger.info("MT5 disconnected")
        return True

    async def submit_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit order to MT5.

        Args:
            order: Order details

        Returns:
            Order result
        """
        if not self._connected:
            return {"success": False, "error": "Not connected"}

        symbol = order.get("symbol")
        direction = order.get("direction", 1)
        lot_size = order.get("lot_size", 0.01)
        stop_loss = order.get("stop_loss")
        take_profit = order.get("take_profit")
        order_type = order.get("order_type", "market")

        # Get current price
        tick = self._mt5.symbol_info_tick(symbol)
        if not tick:
            return {"success": False, "error": f"No tick data for {symbol}"}

        # Determine price and order type
        if direction == 1:
            trade_type = self._mt5.ORDER_TYPE_BUY
            price = tick.ask
        else:
            trade_type = self._mt5.ORDER_TYPE_SELL
            price = tick.bid

        # Build request
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": trade_type,
            "price": price,
            "deviation": 20,
            "magic": 12345,
            "comment": "ARCHON_PRIME",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }

        if stop_loss:
            request["sl"] = stop_loss
        if take_profit:
            request["tp"] = take_profit

        self._orders_sent += 1

        # Send order
        result = self._mt5.order_send(request)

        if result is None:
            error = self._mt5.last_error()
            return {"success": False, "error": str(error)}

        if result.retcode != self._mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "error": f"Order failed: {result.retcode} - {result.comment}",
                "retcode": result.retcode,
            }

        self._orders_filled += 1

        # Emit order filled event
        await self._publish(Event(
            event_type=EventType.ORDER_FILLED,
            data={
                "symbol": symbol,
                "direction": direction,
                "lot_size": lot_size,
                "fill_price": result.price,
                "ticket": result.order,
                "deal": result.deal,
            },
            source=self.name,
        ))

        self._logger.info(
            f"Order filled: {symbol} {'BUY' if direction == 1 else 'SELL'} "
            f"{lot_size} @ {result.price}"
        )

        return {
            "success": True,
            "ticket": result.order,
            "deal": result.deal,
            "price": result.price,
            "volume": result.volume,
        }

    async def close_position(self, ticket: int) -> Dict[str, Any]:
        """
        Close a position by ticket.

        Args:
            ticket: Position ticket

        Returns:
            Close result
        """
        if not self._connected:
            return {"success": False, "error": "Not connected"}

        # Get position info
        position = self._mt5.positions_get(ticket=ticket)
        if not position:
            return {"success": False, "error": "Position not found"}

        position = position[0]

        # Reverse trade to close
        if position.type == self._mt5.POSITION_TYPE_BUY:
            trade_type = self._mt5.ORDER_TYPE_SELL
            price = self._mt5.symbol_info_tick(position.symbol).bid
        else:
            trade_type = self._mt5.ORDER_TYPE_BUY
            price = self._mt5.symbol_info_tick(position.symbol).ask

        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": trade_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 12345,
            "comment": "ARCHON_CLOSE",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }

        result = self._mt5.order_send(request)

        if result is None or result.retcode != self._mt5.TRADE_RETCODE_DONE:
            return {"success": False, "error": "Close failed"}

        return {
            "success": True,
            "ticket": ticket,
            "close_price": result.price,
            "profit": position.profit,
        }

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of position dictionaries
        """
        if not self._connected:
            return []

        positions = self._mt5.positions_get()
        if not positions:
            return []

        result = []
        for pos in positions:
            result.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "direction": 1 if pos.type == self._mt5.POSITION_TYPE_BUY else -1,
                "volume": pos.volume,
                "open_price": pos.price_open,
                "current_price": pos.price_current,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "swap": pos.swap,
                "time": datetime.fromtimestamp(pos.time, tz=timezone.utc),
            })

        return result

    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.

        Returns:
            Account info dictionary
        """
        if not self._connected:
            return {}

        info = self._mt5.account_info()
        if not info:
            return {}

        return {
            "login": info.login,
            "name": info.name,
            "server": info.server,
            "currency": info.currency,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "margin_free": info.margin_free,
            "margin_level": info.margin_level,
            "profit": info.profit,
        }

    async def get_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current tick for symbol."""
        if not self._connected:
            return None

        tick = self._mt5.symbol_info_tick(symbol)
        if not tick:
            return None

        return {
            "symbol": symbol,
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "volume": tick.volume,
            "time": datetime.fromtimestamp(tick.time, tz=timezone.utc),
        }

    async def subscribe_symbol(self, symbol: str) -> bool:
        """Subscribe to symbol market data."""
        if not self._connected:
            return False

        if self._mt5.symbol_select(symbol, True):
            self._subscribed_symbols.add(symbol)
            return True
        return False

    async def _reconnect(self) -> None:
        """Attempt to reconnect to MT5."""
        if not self.mt5_config.auto_reconnect:
            return

        while self._reconnect_attempts < self.mt5_config.max_reconnect_attempts:
            self._reconnect_attempts += 1
            self._logger.info(
                f"Reconnection attempt {self._reconnect_attempts}/"
                f"{self.mt5_config.max_reconnect_attempts}"
            )

            if await self.connect():
                return

            await asyncio.sleep(self.mt5_config.reconnect_delay_sec)

        self._logger.error("Max reconnection attempts reached")

    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics."""
        return {
            **super().get_stats(),
            "connected": self._connected,
            "orders_sent": self._orders_sent,
            "orders_filled": self._orders_filled,
            "subscribed_symbols": list(self._subscribed_symbols),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "MT5Config",
    "MT5Adapter",
]
