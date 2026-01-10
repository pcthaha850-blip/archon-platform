"""
ARCHON RI v6.3 - Dynamic Kelly Criterion Position Sizer
========================================================

Maps signal strength (Z-score) to Kelly fraction, then converts
to risk percentage and lot size for retail accounts.

The Kelly Criterion provides optimal position sizing based on:
- Edge (expected win rate)
- Payoff ratio (win/loss ratio)

For trading signals, we use Z-score as a proxy for edge strength.

Formula:
    f = min(cap, scale * |z_score|)

Where:
    f = Kelly fraction (fraction of capital to risk)
    cap = maximum Kelly fraction (default 0.5)
    scale = scaling factor (default 0.15)
    z_score = signal strength indicator

Author: ARCHON RI Development Team
Version: 6.3.0
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger("ARCHON_KellySizer")


@dataclass
class KellyConfig:
    """Configuration for Kelly position sizing."""

    # Kelly parameters
    kelly_min_z: float = 1.25  # Minimum Z-score to trade
    kelly_scale: float = 0.15  # Kelly scaling factor: f = scale * z
    kelly_cap: float = 0.5  # Maximum Kelly fraction

    # Risk bounds
    min_risk_per_trade_pct: float = 0.25  # Minimum risk per trade (%)
    max_risk_per_trade_pct: float = 0.5  # Maximum risk per trade (%)

    # Lot size constraints (MT5 retail)
    min_lot: float = 0.01  # Minimum lot size
    lot_step: float = 0.01  # Lot size increment
    max_lot: float = 1.0  # Maximum lot size

    # Drawdown adjustment
    dd_size_reduction_factor: float = 0.5  # Reduce sizes by this factor

    # Logging
    log_kelly_decisions: bool = True


class KellyCriterion:
    """
    Dynamic Kelly Criterion Position Sizer.

    Maps signal strength (Z-score) to Kelly fraction, then converts
    to risk percentage and lot size for retail accounts.

    Example:
        kelly = KellyCriterion(config)

        # Get Kelly fraction from Z-score
        f = kelly.kelly_fraction_from_z(z_score=2.5)

        # Get full sizing
        sizing = kelly.compute_full_sizing(
            z_score=2.5,
            account_equity=500.0,
            pip_value_per_lot=10.0,
            stop_distance_pips=50.0
        )
        print(f"Lots: {sizing['lots']}")
    """

    def __init__(self, config: Optional[KellyConfig] = None):
        self.cfg = config or KellyConfig()
        logger.info(
            f"KellyCriterion initialized: min_z={self.cfg.kelly_min_z}, "
            f"scale={self.cfg.kelly_scale}, cap={self.cfg.kelly_cap}"
        )

    def kelly_fraction_from_z(self, z_score: float) -> float:
        """
        Compute Kelly fraction from signal Z-score.

        Uses continuous curve: f = min(cap, scale * z)
        Returns 0 if z_score < kelly_min_z (signal too weak)

        Args:
            z_score: Signal strength indicator

        Returns:
            Kelly fraction in range [0, kelly_cap]
        """
        abs_z = abs(z_score)

        if abs_z < self.cfg.kelly_min_z:
            return 0.0

        f = self.cfg.kelly_scale * abs_z
        return float(min(self.cfg.kelly_cap, max(f, 0.0)))

    def risk_pct_from_kelly(self, kelly_fraction: float) -> float:
        """
        Convert Kelly fraction to risk percentage of equity.

        Maps Kelly range [0, kelly_cap] to [min_risk, max_risk] linearly.

        Args:
            kelly_fraction: Kelly fraction from kelly_fraction_from_z()

        Returns:
            Risk percentage (0-100 scale)
        """
        if kelly_fraction <= 0.0:
            return 0.0

        min_r = self.cfg.min_risk_per_trade_pct
        max_r = self.cfg.max_risk_per_trade_pct

        # Linear interpolation
        scaled = min_r + (max_r - min_r) * (kelly_fraction / self.cfg.kelly_cap)
        return float(min(max_r, max(min_r, scaled)))

    def lot_size_from_risk(
        self,
        risk_pct: float,
        account_equity: float,
        pip_value_per_lot: float,
        stop_distance_pips: float,
    ) -> float:
        """
        Convert risk percentage to lot size.

        Formula: lots = (equity * risk_pct) / (pip_value * stop_distance)

        Args:
            risk_pct: Risk as percentage of equity (0-100)
            account_equity: Current account equity
            pip_value_per_lot: Value of 1 pip for 1 lot
            stop_distance_pips: Stop loss distance in pips

        Returns:
            Position size in lots (rounded to lot_step)
        """
        # Validate inputs
        if risk_pct <= 0:
            return 0.0
        if account_equity <= 0:
            logger.warning("lot_size_from_risk: account_equity must be positive")
            return 0.0
        if pip_value_per_lot <= 0:
            logger.warning("lot_size_from_risk: pip_value_per_lot must be positive")
            return 0.0
        if stop_distance_pips <= 0:
            logger.warning("lot_size_from_risk: stop_distance_pips must be positive")
            return 0.0

        # Calculate raw lot size
        risk_amount = account_equity * (risk_pct / 100.0)
        raw_lots = risk_amount / (pip_value_per_lot * stop_distance_pips)

        # Validate result
        if not np.isfinite(raw_lots):
            logger.warning("lot_size_from_risk: calculation produced non-finite result")
            return 0.0

        # Round down to lot step
        lots = np.floor(raw_lots / self.cfg.lot_step) * self.cfg.lot_step

        # Clamp to valid range
        lots = max(self.cfg.min_lot, min(self.cfg.max_lot, lots))

        # Check minimum
        if lots < self.cfg.min_lot:
            return 0.0

        return float(lots)

    def compute_full_sizing(
        self,
        z_score: float,
        account_equity: float,
        pip_value_per_lot: float,
        stop_distance_pips: float,
        scaling_factor: float = 1.0,
        dd_reduction: bool = False,
    ) -> Dict[str, float]:
        """
        Complete sizing calculation from Z-score to lots.

        Args:
            z_score: Signal strength indicator
            account_equity: Current account equity
            pip_value_per_lot: Value of 1 pip for 1 lot
            stop_distance_pips: Stop loss distance in pips
            scaling_factor: Regime-based scaling (default 1.0)
            dd_reduction: Whether to apply drawdown size reduction

        Returns:
            Dict with:
                - kelly_fraction: Computed Kelly fraction
                - risk_pct_base: Base risk percentage
                - risk_pct_scaled: Final risk percentage after scaling
                - lots: Position size in lots
                - risk_amount: Dollar amount at risk
        """
        kelly = self.kelly_fraction_from_z(z_score)
        risk_pct = self.risk_pct_from_kelly(kelly)

        # Apply regime scaling
        risk_pct *= scaling_factor

        # Apply drawdown reduction
        if dd_reduction:
            risk_pct *= self.cfg.dd_size_reduction_factor

        lots = self.lot_size_from_risk(
            risk_pct, account_equity, pip_value_per_lot, stop_distance_pips
        )

        if self.cfg.log_kelly_decisions and kelly > 0:
            logger.debug(
                f"Kelly sizing: Z={z_score:.2f} -> f={kelly:.3f} -> "
                f"risk={risk_pct:.3f}% -> lots={lots:.2f}"
            )

        return {
            "kelly_fraction": kelly,
            "risk_pct_base": self.risk_pct_from_kelly(
                self.kelly_fraction_from_z(z_score)
            ),
            "risk_pct_scaled": risk_pct,
            "lots": lots,
            "risk_amount": account_equity * (risk_pct / 100.0),
        }

    def get_statistics(self) -> Dict[str, float]:
        """Get Kelly sizer configuration statistics."""
        return {
            "kelly_min_z": self.cfg.kelly_min_z,
            "kelly_scale": self.cfg.kelly_scale,
            "kelly_cap": self.cfg.kelly_cap,
            "min_risk_pct": self.cfg.min_risk_per_trade_pct,
            "max_risk_pct": self.cfg.max_risk_per_trade_pct,
            "min_lot": self.cfg.min_lot,
            "max_lot": self.cfg.max_lot,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["KellyConfig", "KellyCriterion"]
