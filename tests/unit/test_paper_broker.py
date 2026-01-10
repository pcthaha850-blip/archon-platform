"""
Tests for ARCHON PRIME Paper Broker
===================================

Tests the paper trading broker simulation.
"""

import pytest
import asyncio
from datetime import datetime, timezone

from archon_prime.core.event_bus import EventBus
from archon_prime.plugins.brokers.paper_broker import (
    PaperBroker,
    PaperConfig,
    PaperPosition,
)


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
async def paper_broker(event_bus):
    """Create and initialize a paper broker."""
    config = PaperConfig(
        initial_balance=10000.0,
        spread_pips=1.0,
        slippage_probability=0.0,  # Disable for deterministic tests
    )
    broker = PaperBroker(config)
    await broker.load()
    await broker.initialize(event_bus)
    await broker.connect()
    return broker


class TestPaperBrokerConnection:
    """Tests for broker connection."""

    @pytest.mark.asyncio
    async def test_connect(self, event_bus):
        """Should connect successfully."""
        broker = PaperBroker()
        await broker.load()
        await broker.initialize(event_bus)

        result = await broker.connect()
        assert result is True
        assert broker.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, paper_broker):
        """Should disconnect successfully."""
        result = await paper_broker.disconnect()
        assert result is True
        assert paper_broker.is_connected is False


class TestOrderExecution:
    """Tests for order execution."""

    @pytest.mark.asyncio
    async def test_buy_order(self, paper_broker):
        """Should execute buy order."""
        paper_broker.update_price("EURUSD", 1.0850)

        result = await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
            "entry_price": 1.0850,
        })

        assert result["success"] is True
        assert result["ticket"] == 1
        assert result["volume"] == 0.1

    @pytest.mark.asyncio
    async def test_sell_order(self, paper_broker):
        """Should execute sell order."""
        paper_broker.update_price("EURUSD", 1.0850)

        result = await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": -1,
            "lot_size": 0.05,
            "entry_price": 1.0850,
        })

        assert result["success"] is True
        assert result["ticket"] == 1

    @pytest.mark.asyncio
    async def test_order_with_sl_tp(self, paper_broker):
        """Should execute order with SL/TP."""
        paper_broker.update_price("EURUSD", 1.0850)

        result = await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
            "entry_price": 1.0850,
            "stop_loss": 1.0800,
            "take_profit": 1.0950,
        })

        assert result["success"] is True

        positions = await paper_broker.get_positions()
        assert len(positions) == 1
        assert positions[0]["sl"] == 1.0800
        assert positions[0]["tp"] == 1.0950


class TestPositionManagement:
    """Tests for position management."""

    @pytest.mark.asyncio
    async def test_get_positions(self, paper_broker):
        """Should return open positions."""
        paper_broker.update_price("EURUSD", 1.0850)

        await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
        })

        positions = await paper_broker.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "EURUSD"

    @pytest.mark.asyncio
    async def test_close_position_profit(self, paper_broker):
        """Should close position with profit."""
        paper_broker.update_price("EURUSD", 1.0850)

        result = await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
        })
        ticket = result["ticket"]

        # Price goes up
        paper_broker.update_price("EURUSD", 1.0950)

        close_result = await paper_broker.close_position(ticket, 1.0950)
        assert close_result["success"] is True
        assert close_result["profit"] > 0

    @pytest.mark.asyncio
    async def test_close_position_loss(self, paper_broker):
        """Should close position with loss."""
        paper_broker.update_price("EURUSD", 1.0850)

        result = await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
        })
        ticket = result["ticket"]

        # Price goes down
        paper_broker.update_price("EURUSD", 1.0750)

        close_result = await paper_broker.close_position(ticket, 1.0750)
        assert close_result["success"] is True
        assert close_result["profit"] < 0


class TestAccountInfo:
    """Tests for account information."""

    @pytest.mark.asyncio
    async def test_get_account_info(self, paper_broker):
        """Should return account information."""
        info = await paper_broker.get_account_info()

        assert info["balance"] == 10000.0
        assert info["equity"] == 10000.0
        assert info["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_balance_updates(self, paper_broker):
        """Balance should update after trades."""
        paper_broker.update_price("EURUSD", 1.0850)

        result = await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
        })

        paper_broker.update_price("EURUSD", 1.0950)
        await paper_broker.close_position(result["ticket"], 1.0950)

        info = await paper_broker.get_account_info()
        assert info["balance"] != 10000.0  # Changed due to P&L


class TestPriceUpdates:
    """Tests for price updates."""

    @pytest.mark.asyncio
    async def test_price_update(self, paper_broker):
        """Should update position prices."""
        paper_broker.update_price("EURUSD", 1.0850)

        await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
        })

        paper_broker.update_price("EURUSD", 1.0900)

        positions = await paper_broker.get_positions()
        assert positions[0]["current_price"] == 1.0900
        assert positions[0]["profit"] > 0


class TestReset:
    """Tests for account reset."""

    @pytest.mark.asyncio
    async def test_reset(self, paper_broker):
        """Should reset account to initial state."""
        paper_broker.update_price("EURUSD", 1.0850)

        await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
        })

        paper_broker.reset()

        positions = await paper_broker.get_positions()
        assert len(positions) == 0

        info = await paper_broker.get_account_info()
        assert info["balance"] == 10000.0


class TestTradeHistory:
    """Tests for trade history."""

    @pytest.mark.asyncio
    async def test_trade_history(self, paper_broker):
        """Should track closed trades."""
        paper_broker.update_price("EURUSD", 1.0850)

        result = await paper_broker.submit_order({
            "symbol": "EURUSD",
            "direction": 1,
            "lot_size": 0.1,
        })

        await paper_broker.close_position(result["ticket"], 1.0900)

        history = paper_broker.get_trade_history()
        assert len(history) == 1
        assert history[0]["symbol"] == "EURUSD"
