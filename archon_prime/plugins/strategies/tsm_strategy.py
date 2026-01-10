# ARCHON_FEAT: tsm-strategy-001
"""
ARCHON PRIME - TSM Strategy Plugin
==================================

Trend-Structure-Momentum Strategy for signal generation.

Components:
- Trend: Higher timeframe trend direction (EMA)
- Structure: Market structure analysis (swing highs/lows)
- Momentum: Entry timing (RSI, MACD divergence)

Author: ARCHON Development Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from archon_prime.core.plugin_base import StrategyPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_TSM")


@dataclass
class TSMConfig:
    """TSM Strategy configuration."""

    # Trend parameters
    trend_ema_fast: int = 21
    trend_ema_slow: int = 50
    trend_timeframe: str = "H4"

    # Structure parameters
    swing_lookback: int = 10
    structure_confirmation: int = 2

    # Momentum parameters
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Signal parameters
    min_rr_ratio: float = 2.0
    atr_sl_multiplier: float = 1.5
    atr_tp_multiplier: float = 3.0


class TSMStrategy(StrategyPlugin):
    """
    Trend-Structure-Momentum Strategy.

    Trading Logic:
    1. TREND: Confirm higher timeframe trend direction
    2. STRUCTURE: Wait for structure break (BOS/CHOCH)
    3. MOMENTUM: Enter on momentum confirmation

    Entry Conditions (LONG):
    - H4 EMA21 > EMA50 (uptrend)
    - Price breaks above swing high (BOS)
    - RSI < 50 but turning up OR MACD bullish crossover
    - SL below recent swing low
    - TP at 2-3x risk

    Entry Conditions (SHORT):
    - H4 EMA21 < EMA50 (downtrend)
    - Price breaks below swing low (BOS)
    - RSI > 50 but turning down OR MACD bearish crossover
    - SL above recent swing high
    - TP at 2-3x risk
    """

    def __init__(self, config: Optional[TSMConfig] = None):
        super().__init__(PluginConfig(
            name="tsm_strategy",
            version="1.0.0",
            category=PluginCategory.STRATEGY,
            settings=config.__dict__ if config else TSMConfig().__dict__,
        ))

        self.tsm_config = config or TSMConfig()

        # State tracking
        self._trend_direction: Dict[str, int] = {}  # symbol -> 1/-1/0
        self._swing_highs: Dict[str, List[float]] = {}
        self._swing_lows: Dict[str, List[float]] = {}
        self._last_structure: Dict[str, str] = {}  # BOS/CHOCH
        self._signals_generated = 0

    async def on_tick(self, event: Event) -> None:
        """Handle tick event - not used for TSM (bar-based)."""
        pass

    async def on_bar(self, event: Event) -> None:
        """
        Handle bar event - main strategy logic.

        Processes completed bars to identify trading opportunities.
        """
        symbol = event.data.get("symbol")
        timeframe = event.data.get("timeframe")
        bar = event.data.get("bar", {})

        if not symbol or not bar:
            return

        # Process based on timeframe
        if timeframe == self.tsm_config.trend_timeframe:
            await self._update_trend(symbol, bar)
        elif timeframe in ["M15", "M30", "H1"]:
            await self._check_entry(symbol, bar, timeframe)

    async def _update_trend(self, symbol: str, bar: Dict[str, Any]) -> None:
        """Update trend direction from higher timeframe."""
        close = bar.get("close", 0)
        ema_fast = bar.get("ema_fast", 0)
        ema_slow = bar.get("ema_slow", 0)

        if ema_fast > ema_slow * 1.001:
            self._trend_direction[symbol] = 1  # Uptrend
        elif ema_fast < ema_slow * 0.999:
            self._trend_direction[symbol] = -1  # Downtrend
        else:
            self._trend_direction[symbol] = 0  # Neutral

    async def _check_entry(
        self, symbol: str, bar: Dict[str, Any], timeframe: str
    ) -> None:
        """Check for entry signals."""
        trend = self._trend_direction.get(symbol, 0)

        if trend == 0:
            return

        close = bar.get("close", 0)
        high = bar.get("high", 0)
        low = bar.get("low", 0)
        rsi = bar.get("rsi", 50)
        atr = bar.get("atr", 0)

        # Update swing levels
        self._update_swings(symbol, high, low)

        # Check for structure break
        swing_highs = self._swing_highs.get(symbol, [])
        swing_lows = self._swing_lows.get(symbol, [])

        if not swing_highs or not swing_lows:
            return

        # LONG signal
        if trend == 1 and close > max(swing_highs[-2:], default=0):
            if rsi < 50 or rsi < 40:
                await self._generate_signal(
                    symbol=symbol,
                    direction=1,
                    entry=close,
                    sl=min(swing_lows[-2:], default=low) - atr * 0.5,
                    tp=close + atr * self.tsm_config.atr_tp_multiplier,
                    reason="TSM_LONG_BOS",
                )

        # SHORT signal
        elif trend == -1 and close < min(swing_lows[-2:], default=float("inf")):
            if rsi > 50 or rsi > 60:
                await self._generate_signal(
                    symbol=symbol,
                    direction=-1,
                    entry=close,
                    sl=max(swing_highs[-2:], default=high) + atr * 0.5,
                    tp=close - atr * self.tsm_config.atr_tp_multiplier,
                    reason="TSM_SHORT_BOS",
                )

    def _update_swings(self, symbol: str, high: float, low: float) -> None:
        """Update swing high/low tracking."""
        if symbol not in self._swing_highs:
            self._swing_highs[symbol] = []
            self._swing_lows[symbol] = []

        self._swing_highs[symbol].append(high)
        self._swing_lows[symbol].append(low)

        # Keep only recent swings
        max_swings = self.tsm_config.swing_lookback
        if len(self._swing_highs[symbol]) > max_swings:
            self._swing_highs[symbol] = self._swing_highs[symbol][-max_swings:]
        if len(self._swing_lows[symbol]) > max_swings:
            self._swing_lows[symbol] = self._swing_lows[symbol][-max_swings:]

    async def _generate_signal(
        self,
        symbol: str,
        direction: int,
        entry: float,
        sl: float,
        tp: float,
        reason: str,
    ) -> None:
        """Generate trading signal."""
        # Calculate risk/reward
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0

        if rr_ratio < self.tsm_config.min_rr_ratio:
            return

        signal_data = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "risk_reward": round(rr_ratio, 2),
            "strategy": "TSM",
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Publish signal
        await self._publish(Event(
            event_type=EventType.SIGNAL_GENERATED,
            data=signal_data,
            source=self.name,
        ))

        self._signals_generated += 1
        self._logger.info(
            f"TSM Signal: {symbol} {'LONG' if direction == 1 else 'SHORT'} "
            f"@ {entry:.5f} SL:{sl:.5f} TP:{tp:.5f} RR:{rr_ratio:.1f}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            **super().get_stats(),
            "signals_generated": self._signals_generated,
            "symbols_tracked": list(self._trend_direction.keys()),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TSMConfig",
    "TSMStrategy",
]
