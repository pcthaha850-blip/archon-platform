# ARCHON_FEAT: kelly-sizer-001
"""
ARCHON PRIME - Kelly Position Sizer Plugin
==========================================

Kelly Criterion-based position sizing with safety constraints.

Features:
- Z-score validation
- Fractional Kelly scaling
- Risk per trade limits
- Account equity tracking

Author: ARCHON Development Team
Version: 1.0.0
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from archon_prime.core.plugin_base import RiskPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_KellySizer")


@dataclass
class KellyConfig:
    """Kelly sizer configuration."""

    min_z_score: float = 1.25
    kelly_scale: float = 0.15  # Fractional Kelly (15%)
    max_risk_per_trade_pct: float = 2.0
    min_risk_per_trade_pct: float = 0.25
    min_sample_size: int = 30
    lookback_trades: int = 100


class KellySizer(RiskPlugin):
    """
    Kelly Criterion Position Sizer.

    Calculates optimal position size based on:
    - Win rate
    - Average win/loss ratio
    - Z-score for statistical significance

    Formula:
        Kelly % = W - [(1 - W) / R]

    Where:
        W = Win probability
        R = Win/Loss ratio

    Fractional Kelly is applied for safety.
    """

    def __init__(self, config: Optional[KellyConfig] = None):
        super().__init__(PluginConfig(
            name="kelly_sizer",
            version="1.0.0",
            category=PluginCategory.RISK,
            settings=config.__dict__ if config else KellyConfig().__dict__,
        ))

        self.kelly_config = config or KellyConfig()

        # Trade history for calculations
        self._trades: list = []
        self._current_equity: float = 10000.0  # Default
        self._positions_sized = 0

    async def evaluate_risk(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate signal and calculate position size.

        Args:
            signal_data: Signal data with entry, SL, TP

        Returns:
            Risk evaluation with position size
        """
        symbol = signal_data.get("symbol")
        entry = signal_data.get("entry_price", 0)
        sl = signal_data.get("stop_loss", 0)
        direction = signal_data.get("direction", 1)

        # Calculate risk in pips
        risk_pips = abs(entry - sl)
        if risk_pips == 0:
            return {"approved": False, "reason": "Invalid stop loss"}

        # Get Kelly percentage
        kelly_result = self._calculate_kelly()

        if not kelly_result["valid"]:
            return {
                "approved": False,
                "reason": kelly_result["reason"],
                "kelly_pct": 0,
            }

        kelly_pct = kelly_result["kelly_pct"]

        # Apply limits
        risk_pct = min(
            kelly_pct,
            self.kelly_config.max_risk_per_trade_pct
        )
        risk_pct = max(risk_pct, self.kelly_config.min_risk_per_trade_pct)

        # Calculate position size
        risk_amount = self._current_equity * (risk_pct / 100)
        pip_value = self._get_pip_value(symbol)

        if pip_value > 0 and risk_pips > 0:
            lot_size = risk_amount / (risk_pips * pip_value * 100000)
            lot_size = round(lot_size, 2)
        else:
            lot_size = 0.01  # Minimum

        self._positions_sized += 1

        result = {
            "approved": True,
            "symbol": symbol,
            "lot_size": lot_size,
            "risk_pct": round(risk_pct, 2),
            "kelly_pct": round(kelly_result["kelly_pct"], 2),
            "z_score": round(kelly_result["z_score"], 2),
            "win_rate": round(kelly_result["win_rate"], 2),
            "risk_amount": round(risk_amount, 2),
        }

        self._logger.info(
            f"Kelly Size: {symbol} {lot_size} lots "
            f"({risk_pct:.1f}% risk, Kelly: {kelly_result['kelly_pct']:.1f}%)"
        )

        # Publish approved signal
        await self._publish(Event(
            event_type=EventType.SIGNAL_APPROVED,
            data={**signal_data, **result},
            source=self.name,
        ))

        return result

    def _calculate_kelly(self) -> Dict[str, Any]:
        """Calculate Kelly criterion percentage."""
        if len(self._trades) < self.kelly_config.min_sample_size:
            return {
                "valid": False,
                "reason": f"Insufficient trades: {len(self._trades)}/{self.kelly_config.min_sample_size}",
                "kelly_pct": 0,
                "z_score": 0,
                "win_rate": 0,
            }

        # Use recent trades
        recent = self._trades[-self.kelly_config.lookback_trades:]

        wins = [t for t in recent if t > 0]
        losses = [t for t in recent if t < 0]

        if not wins or not losses:
            return {
                "valid": False,
                "reason": "Need both wins and losses",
                "kelly_pct": 0,
                "z_score": 0,
                "win_rate": 0,
            }

        # Calculate metrics
        win_rate = len(wins) / len(recent)
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))

        if avg_loss == 0:
            return {
                "valid": False,
                "reason": "Zero average loss",
                "kelly_pct": 0,
                "z_score": 0,
                "win_rate": win_rate,
            }

        # Win/loss ratio
        rr_ratio = avg_win / avg_loss

        # Kelly formula
        kelly_raw = win_rate - ((1 - win_rate) / rr_ratio)

        # Z-score for statistical significance
        n = len(recent)
        z_score = (win_rate - 0.5) / math.sqrt(0.25 / n)

        if z_score < self.kelly_config.min_z_score:
            return {
                "valid": False,
                "reason": f"Z-score too low: {z_score:.2f} < {self.kelly_config.min_z_score}",
                "kelly_pct": 0,
                "z_score": z_score,
                "win_rate": win_rate,
            }

        # Apply fractional Kelly
        kelly_pct = max(0, kelly_raw * 100 * self.kelly_config.kelly_scale)

        return {
            "valid": True,
            "kelly_pct": kelly_pct,
            "z_score": z_score,
            "win_rate": win_rate,
            "rr_ratio": rr_ratio,
        }

    def _get_pip_value(self, symbol: str) -> float:
        """Get pip value for symbol."""
        # Simplified - should use actual rates
        if "JPY" in symbol:
            return 0.01
        return 0.0001

    def add_trade_result(self, pnl: float) -> None:
        """Add a trade result to history."""
        self._trades.append(pnl)

        # Trim to lookback
        if len(self._trades) > self.kelly_config.lookback_trades * 2:
            self._trades = self._trades[-self.kelly_config.lookback_trades:]

    def update_equity(self, equity: float) -> None:
        """Update current account equity."""
        self._current_equity = equity

    async def _handle_position(self, event: Event) -> None:
        """Handle position close to update trade history."""
        if event.event_type == EventType.POSITION_CLOSED:
            pnl = event.data.get("realized_pnl", 0)
            self.add_trade_result(pnl)

    def get_stats(self) -> Dict[str, Any]:
        """Get sizer statistics."""
        kelly_result = self._calculate_kelly()
        return {
            **super().get_stats(),
            "positions_sized": self._positions_sized,
            "trades_tracked": len(self._trades),
            "current_kelly": kelly_result,
            "current_equity": self._current_equity,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "KellyConfig",
    "KellySizer",
]
