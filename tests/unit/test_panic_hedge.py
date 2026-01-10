"""
Tests for Panic Hedge Emergency Protection System
=================================================

Tests the emergency protection system for extreme market conditions.
"""

import pytest
from datetime import datetime, timezone, timedelta
from shared.archon_core.panic_hedge import (
    PanicTrigger,
    PanicAction,
    PanicConfig,
    PanicState,
    PanicHedge,
)


@pytest.fixture
def panic_hedge():
    """Create a PanicHedge with default config."""
    return PanicHedge()


@pytest.fixture
def panic_hedge_custom():
    """Create a PanicHedge with custom config."""
    config = PanicConfig(
        flash_crash_pct=1.0,  # Lower threshold for testing
        flash_crash_window_sec=30,
        volatility_spike_atr_mult=2.0,
        spread_explosion_mult=5.0,
        drawdown_kill_switch_pct=3.0,
        cooldown_minutes=10,
    )
    return PanicHedge(config)


class TestInitialState:
    """Tests for initial panic hedge state."""

    def test_initial_state_inactive(self, panic_hedge):
        """Panic hedge should start inactive."""
        state = panic_hedge.get_state()
        assert not state.is_active
        assert state.trigger == PanicTrigger.NONE

    def test_should_not_halt_initially(self, panic_hedge):
        """Should not halt trading initially."""
        assert not panic_hedge.should_halt_trading()


class TestFlashCrashDetection:
    """Tests for flash crash detection."""

    def test_no_crash_detected_stable_prices(self, panic_hedge):
        """No crash with stable prices."""
        # Update with stable prices
        for _ in range(10):
            result = panic_hedge.update_price("EURUSD", 1.1000)
            assert result is None

    def test_flash_crash_detected(self, panic_hedge_custom):
        """Flash crash should be detected on sharp drop."""
        # Simulate flash crash (1% drop for custom config)
        panic_hedge_custom.update_price("EURUSD", 1.1000)

        # Small price drop within threshold
        result = panic_hedge_custom.update_price("EURUSD", 1.0990)
        assert result is None

        # Large drop exceeding threshold
        result = panic_hedge_custom.update_price("EURUSD", 1.0880)  # ~1.1% drop
        assert result == PanicTrigger.FLASH_CRASH

    def test_flash_crash_activates_halt(self, panic_hedge_custom):
        """Flash crash should activate trading halt."""
        panic_hedge_custom.update_price("EURUSD", 1.1000)
        panic_hedge_custom.update_price("EURUSD", 1.0880)

        assert panic_hedge_custom.should_halt_trading()

    def test_flash_crash_recorded_in_history(self, panic_hedge_custom):
        """Flash crash should be recorded in history."""
        panic_hedge_custom.update_price("EURUSD", 1.1000)
        panic_hedge_custom.update_price("EURUSD", 1.0880)

        history = panic_hedge_custom.get_trigger_history()
        assert len(history) > 0
        assert history[-1]["trigger"] == PanicTrigger.FLASH_CRASH.value


class TestSpreadExplosion:
    """Tests for spread explosion detection."""

    def test_no_explosion_normal_spread(self, panic_hedge):
        """No explosion with normal spread."""
        panic_hedge.set_baseline_spread("EURUSD", 0.0002)
        result = panic_hedge.update_price("EURUSD", 1.1000, spread=0.0003)
        assert result is None

    def test_spread_explosion_detected(self, panic_hedge_custom):
        """Spread explosion should be detected."""
        panic_hedge_custom.set_baseline_spread("EURUSD", 0.0002)

        # Normal spread
        result = panic_hedge_custom.update_price("EURUSD", 1.1000, spread=0.0004)
        assert result is None

        # Explosive spread (5x threshold in custom config)
        result = panic_hedge_custom.update_price("EURUSD", 1.1000, spread=0.0012)
        assert result == PanicTrigger.SPREAD_EXPLOSION

    def test_spread_explosion_without_baseline(self, panic_hedge):
        """No explosion detection without baseline."""
        # No baseline set
        result = panic_hedge.update_price("EURUSD", 1.1000, spread=0.01)
        assert result is None


class TestVolatilitySpike:
    """Tests for volatility spike detection."""

    def test_no_spike_normal_volatility(self, panic_hedge):
        """No spike with normal volatility."""
        panic_hedge.set_baseline_atr("EURUSD", 0.005)
        result = panic_hedge.check_volatility("EURUSD", 0.006)
        assert result is None

    def test_volatility_spike_detected(self, panic_hedge_custom):
        """Volatility spike should be detected."""
        panic_hedge_custom.set_baseline_atr("EURUSD", 0.005)

        # Normal volatility
        result = panic_hedge_custom.check_volatility("EURUSD", 0.008)
        assert result is None

        # Spike (2x threshold in custom config)
        result = panic_hedge_custom.check_volatility("EURUSD", 0.015)
        assert result == PanicTrigger.VOLATILITY_SPIKE

    def test_volatility_spike_without_baseline(self, panic_hedge):
        """No spike detection without baseline."""
        result = panic_hedge.check_volatility("EURUSD", 0.1)
        assert result is None


class TestDrawdownBreach:
    """Tests for drawdown breach detection."""

    def test_no_breach_within_threshold(self, panic_hedge):
        """No breach within threshold."""
        result = panic_hedge.check_drawdown(
            current_equity=480.0,
            peak_equity=500.0,
        )
        assert result is None  # 4% DD is below 5% threshold

    def test_drawdown_breach_detected(self, panic_hedge):
        """Drawdown breach should be detected."""
        result = panic_hedge.check_drawdown(
            current_equity=470.0,
            peak_equity=500.0,
        )
        assert result == PanicTrigger.DRAWDOWN_BREACH  # 6% DD exceeds 5%

    def test_drawdown_custom_threshold(self, panic_hedge_custom):
        """Custom drawdown threshold should work."""
        # Custom config has 3% threshold
        result = panic_hedge_custom.check_drawdown(
            current_equity=480.0,
            peak_equity=500.0,
        )
        assert result == PanicTrigger.DRAWDOWN_BREACH  # 4% exceeds 3%

    def test_drawdown_invalid_peak(self, panic_hedge):
        """Invalid peak equity should return None."""
        result = panic_hedge.check_drawdown(
            current_equity=100.0,
            peak_equity=0.0,
        )
        assert result is None


class TestCooldown:
    """Tests for cooldown period."""

    def test_no_trigger_during_cooldown(self, panic_hedge_custom):
        """No triggers during cooldown period."""
        # Trigger flash crash
        panic_hedge_custom.update_price("EURUSD", 1.1000)
        panic_hedge_custom.update_price("EURUSD", 1.0880)

        # Reset price history for new pair
        panic_hedge_custom.set_baseline_spread("GBPUSD", 0.0002)

        # Try to trigger spread explosion during cooldown
        result = panic_hedge_custom.update_price("GBPUSD", 1.3000, spread=0.01)
        assert result is None  # Should be blocked by cooldown


class TestManualHalt:
    """Tests for manual halt functionality."""

    def test_manual_halt(self, panic_hedge):
        """Manual halt should activate."""
        panic_hedge.manual_halt("Testing manual halt")

        assert panic_hedge.should_halt_trading()
        state = panic_hedge.get_state()
        assert state.trigger == PanicTrigger.MANUAL_HALT

    def test_manual_halt_in_history(self, panic_hedge):
        """Manual halt should be recorded in history."""
        panic_hedge.manual_halt("Test reason")

        history = panic_hedge.get_trigger_history()
        assert len(history) > 0
        assert history[-1]["trigger"] == PanicTrigger.MANUAL_HALT.value


class TestReset:
    """Tests for state reset."""

    def test_reset_clears_state(self, panic_hedge_custom):
        """Reset should clear panic state."""
        # Trigger panic
        panic_hedge_custom.manual_halt("Test")
        assert panic_hedge_custom.should_halt_trading()

        # Reset
        panic_hedge_custom.reset()
        assert not panic_hedge_custom.should_halt_trading()

        state = panic_hedge_custom.get_state()
        assert state.trigger == PanicTrigger.NONE


class TestCallbacks:
    """Tests for panic callbacks."""

    def test_callback_executed_on_panic(self, panic_hedge):
        """Callback should be executed on panic."""
        callback_called = []

        def test_callback(state):
            callback_called.append(state)

        panic_hedge.on_panic(test_callback)
        panic_hedge.manual_halt("Test")

        assert len(callback_called) == 1
        assert callback_called[0].trigger == PanicTrigger.MANUAL_HALT

    def test_multiple_callbacks(self, panic_hedge):
        """Multiple callbacks should all be executed."""
        results = []

        panic_hedge.on_panic(lambda s: results.append("callback1"))
        panic_hedge.on_panic(lambda s: results.append("callback2"))

        panic_hedge.manual_halt("Test")

        assert "callback1" in results
        assert "callback2" in results

    def test_callback_error_handled(self, panic_hedge):
        """Callback errors should be handled gracefully."""
        def error_callback(state):
            raise ValueError("Callback error")

        panic_hedge.on_panic(error_callback)

        # Should not raise
        panic_hedge.manual_halt("Test")
        assert panic_hedge.should_halt_trading()


class TestStatistics:
    """Tests for statistics."""

    def test_get_statistics(self, panic_hedge):
        """Should return valid statistics."""
        panic_hedge.update_price("EURUSD", 1.1000)
        panic_hedge.update_price("GBPUSD", 1.3000)

        stats = panic_hedge.get_statistics()

        assert "is_active" in stats
        assert "total_triggers" in stats
        assert "pairs_monitored" in stats
        assert stats["pairs_monitored"] == 2

    def test_statistics_after_trigger(self, panic_hedge):
        """Statistics should reflect triggered state."""
        panic_hedge.manual_halt("Test")

        stats = panic_hedge.get_statistics()

        assert stats["is_active"] is True
        assert stats["current_trigger"] == PanicTrigger.MANUAL_HALT.value
        assert stats["total_triggers"] == 1


class TestBaselines:
    """Tests for baseline setting."""

    def test_set_baseline_spread(self, panic_hedge):
        """Should set baseline spread."""
        panic_hedge.set_baseline_spread("EURUSD", 0.0002)
        # Internal state check - just ensure no errors
        assert True

    def test_set_baseline_atr(self, panic_hedge):
        """Should set baseline ATR."""
        panic_hedge.set_baseline_atr("EURUSD", 0.005)
        # Internal state check - just ensure no errors
        assert True


class TestPanicState:
    """Tests for PanicState dataclass."""

    def test_default_state(self):
        """Default state should be inactive."""
        state = PanicState()
        assert not state.is_active
        assert state.trigger == PanicTrigger.NONE
        assert state.triggered_at is None
        assert state.actions_taken == []
