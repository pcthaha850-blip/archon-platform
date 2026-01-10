"""
Tests for Position Manager
==========================

Tests the position tracking and P&L calculation system.
"""

import pytest
from datetime import datetime, timezone
from shared.archon_core.position_manager import (
    PositionSide,
    PositionStatus,
    PositionState,
    Position,
    PositionManagerConfig,
    PositionManager,
)


@pytest.fixture
def manager():
    """Create a position manager with default config."""
    return PositionManager()


@pytest.fixture
def manager_limited():
    """Create a position manager with limited positions."""
    config = PositionManagerConfig(
        max_positions=2,
        max_positions_per_symbol=1,
    )
    return PositionManager(config)


class TestPositionCreation:
    """Tests for position opening."""

    def test_open_long_position(self, manager):
        """Should open a long position."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )

        assert position is not None
        assert position.symbol == "EURUSD"
        assert position.side == PositionSide.LONG
        assert position.quantity == 0.1
        assert position.entry_price == 1.0850
        assert position.status == PositionStatus.OPEN

    def test_open_short_position(self, manager):
        """Should open a short position."""
        position = manager.open_position(
            symbol="GBPUSD",
            side=PositionSide.SHORT,
            quantity=0.05,
            entry_price=1.2750,
        )

        assert position is not None
        assert position.side == PositionSide.SHORT
        assert position.direction == -1

    def test_position_with_stops(self, manager):
        """Should create position with SL/TP."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
            stop_loss=1.0800,
            take_profit=1.0950,
        )

        assert position.stop_loss == 1.0800
        assert position.take_profit == 1.0950

    def test_position_limit_blocks_new(self, manager_limited):
        """Should block new positions when limit reached."""
        # Open first position
        pos1 = manager_limited.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        assert pos1 is not None

        # Open second position
        pos2 = manager_limited.open_position(
            symbol="GBPUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.2750,
        )
        assert pos2 is not None

        # Third position should be blocked
        pos3 = manager_limited.open_position(
            symbol="USDJPY",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=150.00,
        )
        assert pos3 is None

    def test_symbol_limit_blocks_new(self, manager_limited):
        """Should block new positions for same symbol."""
        # Open first position for EURUSD
        pos1 = manager_limited.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        assert pos1 is not None

        # Second EURUSD position should be blocked
        pos2 = manager_limited.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0860,
        )
        assert pos2 is None


class TestPositionClosing:
    """Tests for position closing."""

    def test_close_long_position_profit(self, manager):
        """Should close long position with profit."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )

        pnl = manager.close_position(position.ticket, close_price=1.0950)

        assert pnl is not None
        assert pnl > 0  # Profit
        assert pnl == pytest.approx(0.001, abs=0.0001)  # (1.0950 - 1.0850) * 0.1 = 0.001

    def test_close_long_position_loss(self, manager):
        """Should close long position with loss."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )

        pnl = manager.close_position(position.ticket, close_price=1.0750)

        assert pnl < 0  # Loss

    def test_close_short_position_profit(self, manager):
        """Should close short position with profit."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.SHORT,
            quantity=0.1,
            entry_price=1.0850,
        )

        pnl = manager.close_position(position.ticket, close_price=1.0750)

        assert pnl > 0  # Profit (price went down)

    def test_close_removes_position(self, manager):
        """Closed position should be removed."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        ticket = position.ticket

        manager.close_position(ticket, close_price=1.0900)

        assert manager.get_position(ticket) is None

    def test_close_nonexistent_returns_none(self, manager):
        """Closing nonexistent position returns None."""
        pnl = manager.close_position(99999, close_price=1.0000)
        assert pnl is None


class TestPriceUpdates:
    """Tests for price updates and unrealized P&L."""

    def test_update_prices_long(self, manager):
        """Should update unrealized P&L for long position."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )

        pnl_updates = manager.update_prices({"EURUSD": 1.0900})

        assert position.ticket in pnl_updates
        assert pnl_updates[position.ticket] > 0
        assert position.current_price == 1.0900

    def test_update_prices_short(self, manager):
        """Should update unrealized P&L for short position."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.SHORT,
            quantity=0.1,
            entry_price=1.0850,
        )

        pnl_updates = manager.update_prices({"EURUSD": 1.0800})

        assert pnl_updates[position.ticket] > 0  # Profit (price went down)

    def test_update_prices_missing_symbol(self, manager):
        """Should handle missing price data."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )

        pnl_updates = manager.update_prices({"GBPUSD": 1.2750})

        assert position.ticket not in pnl_updates


class TestExitChecks:
    """Tests for stop loss and take profit."""

    def test_stop_loss_triggered_long(self, manager):
        """Should trigger stop loss for long position."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
            stop_loss=1.0800,
        )

        exits = manager.check_exits({"EURUSD": 1.0790})

        assert len(exits) == 1
        assert exits[0]["reason"] == "stop_loss"

    def test_take_profit_triggered_long(self, manager):
        """Should trigger take profit for long position."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
            take_profit=1.0950,
        )

        exits = manager.check_exits({"EURUSD": 1.0960})

        assert len(exits) == 1
        assert exits[0]["reason"] == "take_profit"

    def test_stop_loss_triggered_short(self, manager):
        """Should trigger stop loss for short position."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.SHORT,
            quantity=0.1,
            entry_price=1.0850,
            stop_loss=1.0900,
        )

        exits = manager.check_exits({"EURUSD": 1.0910})

        assert len(exits) == 1
        assert exits[0]["reason"] == "stop_loss"

    def test_take_profit_triggered_short(self, manager):
        """Should trigger take profit for short position."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.SHORT,
            quantity=0.1,
            entry_price=1.0850,
            take_profit=1.0750,
        )

        exits = manager.check_exits({"EURUSD": 1.0740})

        assert len(exits) == 1
        assert exits[0]["reason"] == "take_profit"

    def test_no_exit_within_range(self, manager):
        """Should not trigger exit when price in range."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
            stop_loss=1.0800,
            take_profit=1.0950,
        )

        exits = manager.check_exits({"EURUSD": 1.0870})

        assert len(exits) == 0


class TestTrailingStop:
    """Tests for trailing stop functionality."""

    def test_trailing_stop_activates_long(self, manager):
        """Trailing stop should activate at threshold."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0000,
        )

        # 1.5% profit should activate (default threshold)
        new_trailing = manager.update_trailing_stop(position.ticket, 1.0160)

        assert new_trailing is not None
        assert position.trailing_stop is not None
        assert position.trailing_stop < 1.0160

    def test_trailing_stop_moves_up_long(self, manager):
        """Trailing stop should move up with price for long."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0000,
        )

        # First update
        manager.update_trailing_stop(position.ticket, 1.0200)
        first_trailing = position.trailing_stop

        # Price goes higher
        manager.update_trailing_stop(position.ticket, 1.0300)
        second_trailing = position.trailing_stop

        assert second_trailing > first_trailing

    def test_trailing_stop_triggers_exit(self, manager):
        """Trailing stop should trigger exit."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0000,
        )

        # Activate trailing stop
        manager.update_trailing_stop(position.ticket, 1.0200)
        trailing = position.trailing_stop

        # Price falls to trailing stop
        exits = manager.check_exits({"EURUSD": trailing - 0.0001})

        assert len(exits) == 1
        assert exits[0]["reason"] == "trailing_stop"


class TestPositionQueries:
    """Tests for position queries."""

    def test_get_position(self, manager):
        """Should retrieve position by ticket."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )

        retrieved = manager.get_position(position.ticket)

        assert retrieved is not None
        assert retrieved.symbol == "EURUSD"

    def test_get_positions_by_symbol(self, manager):
        """Should retrieve positions by symbol."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        manager.open_position(
            symbol="GBPUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.2750,
        )

        eur_positions = manager.get_positions_by_symbol("EURUSD")

        assert len(eur_positions) == 1
        assert eur_positions[0].symbol == "EURUSD"

    def test_get_all_positions(self, manager):
        """Should retrieve all positions."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        manager.open_position(
            symbol="GBPUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.2750,
        )

        all_positions = manager.get_all_positions()

        assert len(all_positions) == 2


class TestStatistics:
    """Tests for statistics tracking."""

    def test_statistics_after_trades(self, manager):
        """Should track trading statistics."""
        # Open and close a winning trade
        pos1 = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        manager.close_position(pos1.ticket, close_price=1.0950)

        # Open and close a losing trade
        pos2 = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        manager.close_position(pos2.ticket, close_price=1.0750)

        stats = manager.get_statistics()

        assert stats["total_opened"] == 2
        assert stats["total_closed"] == 2
        assert stats["winning_trades"] == 1
        assert stats["losing_trades"] == 1
        assert stats["win_rate_pct"] == 50.0

    def test_total_exposure(self, manager):
        """Should calculate total exposure."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )
        manager.open_position(
            symbol="GBPUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.2750,
        )

        exposure = manager.get_total_exposure()

        # 0.1 * 1.0850 + 0.1 * 1.2750 = 0.236
        assert exposure == pytest.approx(0.236, abs=0.001)

    def test_reset_clears_all(self, manager):
        """Reset should clear positions and stats."""
        manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
        )

        manager.reset()

        assert len(manager.get_all_positions()) == 0
        stats = manager.get_statistics()
        assert stats["total_opened"] == 0


class TestPositionState:
    """Tests for PositionState serialization."""

    def test_position_to_state(self, manager):
        """Should convert Position to PositionState."""
        position = manager.open_position(
            symbol="EURUSD",
            side=PositionSide.LONG,
            quantity=0.1,
            entry_price=1.0850,
            stop_loss=1.0800,
            take_profit=1.0950,
        )

        state = position.to_state()

        assert state.symbol == "EURUSD"
        assert state.direction == 1
        assert state.volume == 0.1
        assert state.entry_price == 1.0850
        assert state.sl_price == 1.0800
        assert state.tp_price == 1.0950

    def test_state_to_dict_roundtrip(self):
        """Should roundtrip through dict."""
        original = PositionState(
            symbol="EURUSD",
            direction=1,
            entry_price=1.0850,
            entry_time="2024-01-01T00:00:00Z",
            volume=0.1,
            sl_price=1.0800,
            tp_price=1.0950,
        )

        data = original.to_dict()
        restored = PositionState.from_dict(data)

        assert restored.symbol == original.symbol
        assert restored.direction == original.direction
        assert restored.entry_price == original.entry_price
