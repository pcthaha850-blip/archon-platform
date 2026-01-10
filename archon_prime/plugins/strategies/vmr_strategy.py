# ARCHON_FEAT: vmr-strategy-001
"""
ARCHON PRIME - VMR Strategy Plugin
==================================

Volatility-Momentum-Regime Strategy for adaptive signal generation.

Components:
- Volatility: ATR-based volatility assessment
- Momentum: Multi-timeframe momentum alignment
- Regime: Market regime classification (trending/ranging)

Author: ARCHON Development Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from archon_prime.core.plugin_base import StrategyPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_VMR")


class MarketRegime(Enum):
    """Market regime classification."""

    TRENDING_UP = auto()
    TRENDING_DOWN = auto()
    RANGING = auto()
    HIGH_VOLATILITY = auto()
    LOW_VOLATILITY = auto()


@dataclass
class VMRConfig:
    """VMR Strategy configuration."""

    # Volatility parameters
    atr_period: int = 14
    volatility_threshold_high: float = 1.5  # Multiplier of average ATR
    volatility_threshold_low: float = 0.5

    # Momentum parameters
    momentum_fast: int = 5
    momentum_slow: int = 20
    roc_period: int = 10
    momentum_threshold: float = 0.3

    # Regime parameters
    regime_lookback: int = 50
    adx_period: int = 14
    adx_trending_threshold: float = 25.0
    hurst_period: int = 100

    # Signal parameters
    min_momentum_alignment: int = 2  # Min timeframes aligned
    risk_per_regime: Dict[str, float] = field(default_factory=lambda: {
        "TRENDING_UP": 1.0,
        "TRENDING_DOWN": 1.0,
        "RANGING": 0.5,
        "HIGH_VOLATILITY": 0.3,
        "LOW_VOLATILITY": 0.8,
    })


class VMRStrategy(StrategyPlugin):
    """
    Volatility-Momentum-Regime Adaptive Strategy.

    Trading Logic:
    1. VOLATILITY: Assess current vs historical volatility
    2. MOMENTUM: Check multi-timeframe momentum alignment
    3. REGIME: Classify market regime and adapt

    Regime Adaptations:
    - Trending: Trend-following entries
    - Ranging: Mean-reversion entries
    - High Vol: Reduced size, wider stops
    - Low Vol: Normal size, tighter stops

    Entry Conditions:
    - Regime identified and stable
    - Momentum aligned across 2+ timeframes
    - Volatility within acceptable range
    """

    def __init__(self, config: Optional[VMRConfig] = None):
        super().__init__(PluginConfig(
            name="vmr_strategy",
            version="1.0.0",
            category=PluginCategory.STRATEGY,
            settings=config.__dict__ if config else VMRConfig().__dict__,
        ))

        self.vmr_config = config or VMRConfig()

        # State tracking
        self._regime: Dict[str, MarketRegime] = {}
        self._volatility: Dict[str, float] = {}
        self._momentum: Dict[str, Dict[str, float]] = {}  # symbol -> {tf: value}
        self._signals_generated = 0

    async def on_tick(self, event: Event) -> None:
        """Handle tick event - not used for VMR (bar-based)."""
        pass

    async def on_bar(self, event: Event) -> None:
        """Handle bar event - main strategy logic."""
        symbol = event.data.get("symbol")
        timeframe = event.data.get("timeframe")
        bar = event.data.get("bar", {})

        if not symbol or not bar:
            return

        # Update volatility
        await self._update_volatility(symbol, bar)

        # Update momentum for this timeframe
        await self._update_momentum(symbol, timeframe, bar)

        # Update regime
        await self._update_regime(symbol, bar)

        # Check for signals on entry timeframe
        if timeframe in ["M15", "M30", "H1"]:
            await self._check_entry(symbol, bar, timeframe)

    async def _update_volatility(self, symbol: str, bar: Dict[str, Any]) -> None:
        """Update volatility state."""
        atr = bar.get("atr", 0)
        avg_atr = bar.get("avg_atr", atr)

        if avg_atr > 0:
            self._volatility[symbol] = atr / avg_atr
        else:
            self._volatility[symbol] = 1.0

    async def _update_momentum(
        self, symbol: str, timeframe: str, bar: Dict[str, Any]
    ) -> None:
        """Update momentum for symbol/timeframe."""
        if symbol not in self._momentum:
            self._momentum[symbol] = {}

        close = bar.get("close", 0)
        ma_fast = bar.get("ma_fast", close)
        ma_slow = bar.get("ma_slow", close)
        roc = bar.get("roc", 0)

        # Calculate momentum score
        if ma_fast > ma_slow and roc > 0:
            momentum = 1.0
        elif ma_fast < ma_slow and roc < 0:
            momentum = -1.0
        else:
            momentum = 0.0

        self._momentum[symbol][timeframe] = momentum

    async def _update_regime(self, symbol: str, bar: Dict[str, Any]) -> None:
        """Update market regime classification."""
        adx = bar.get("adx", 20)
        volatility = self._volatility.get(symbol, 1.0)
        plus_di = bar.get("plus_di", 0)
        minus_di = bar.get("minus_di", 0)

        # Classify regime
        if volatility > self.vmr_config.volatility_threshold_high:
            regime = MarketRegime.HIGH_VOLATILITY
        elif volatility < self.vmr_config.volatility_threshold_low:
            regime = MarketRegime.LOW_VOLATILITY
        elif adx >= self.vmr_config.adx_trending_threshold:
            if plus_di > minus_di:
                regime = MarketRegime.TRENDING_UP
            else:
                regime = MarketRegime.TRENDING_DOWN
        else:
            regime = MarketRegime.RANGING

        self._regime[symbol] = regime

    async def _check_entry(
        self, symbol: str, bar: Dict[str, Any], timeframe: str
    ) -> None:
        """Check for entry signals based on regime."""
        regime = self._regime.get(symbol)
        if not regime:
            return

        momentum = self._momentum.get(symbol, {})
        aligned_count = sum(1 for v in momentum.values() if v != 0)
        direction = sum(momentum.values())

        if aligned_count < self.vmr_config.min_momentum_alignment:
            return

        close = bar.get("close", 0)
        atr = bar.get("atr", 0)

        # Generate signal based on regime
        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            # Trend-following
            if (regime == MarketRegime.TRENDING_UP and direction > 0) or \
               (regime == MarketRegime.TRENDING_DOWN and direction < 0):
                await self._generate_signal(
                    symbol=symbol,
                    direction=1 if direction > 0 else -1,
                    entry=close,
                    atr=atr,
                    regime=regime,
                    reason="VMR_TREND_FOLLOW",
                )

        elif regime == MarketRegime.RANGING:
            # Mean reversion
            rsi = bar.get("rsi", 50)
            if rsi < 30 and direction > 0:
                await self._generate_signal(
                    symbol=symbol,
                    direction=1,
                    entry=close,
                    atr=atr,
                    regime=regime,
                    reason="VMR_MEAN_REVERT_LONG",
                )
            elif rsi > 70 and direction < 0:
                await self._generate_signal(
                    symbol=symbol,
                    direction=-1,
                    entry=close,
                    atr=atr,
                    regime=regime,
                    reason="VMR_MEAN_REVERT_SHORT",
                )

    async def _generate_signal(
        self,
        symbol: str,
        direction: int,
        entry: float,
        atr: float,
        regime: MarketRegime,
        reason: str,
    ) -> None:
        """Generate trading signal."""
        # Adjust stops based on regime
        if regime == MarketRegime.HIGH_VOLATILITY:
            sl_mult = 2.0
            tp_mult = 4.0
        elif regime == MarketRegime.LOW_VOLATILITY:
            sl_mult = 1.0
            tp_mult = 2.0
        else:
            sl_mult = 1.5
            tp_mult = 3.0

        if direction == 1:
            sl = entry - atr * sl_mult
            tp = entry + atr * tp_mult
        else:
            sl = entry + atr * sl_mult
            tp = entry - atr * tp_mult

        # Get risk multiplier for regime
        risk_mult = self.vmr_config.risk_per_regime.get(regime.name, 1.0)

        signal_data = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "strategy": "VMR",
            "regime": regime.name,
            "risk_multiplier": risk_mult,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self._publish(Event(
            event_type=EventType.SIGNAL_GENERATED,
            data=signal_data,
            source=self.name,
        ))

        self._signals_generated += 1
        self._logger.info(
            f"VMR Signal: {symbol} {'LONG' if direction == 1 else 'SHORT'} "
            f"Regime:{regime.name} @ {entry:.5f}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
        return {
            **super().get_stats(),
            "signals_generated": self._signals_generated,
            "current_regimes": {k: v.name for k, v in self._regime.items()},
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "MarketRegime",
    "VMRConfig",
    "VMRStrategy",
]
