"""
ARCHON RI v6.3 - Hurst Exponent Regime Detector
=================================================

Detects market regime using Hurst Exponent analysis.

Hurst Exponent Interpretation:
    H < 0.5: Mean-reverting (Stat Arb ON, Momentum OFF)
    H ~ 0.5: Random walk (Reduce all sizes)
    H > 0.5: Trending (Stat Arb OFF, Momentum ON)

Uses R/S (Rescaled Range) Analysis for calculation.

Author: ARCHON RI Development Team
Version: 6.3.0
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("ARCHON_HurstRegime")


class MarketRegime(Enum):
    """Market regime classification."""

    MEAN_REVERTING = "MEAN_REVERTING"
    RANDOM_WALK = "RANDOM_WALK"
    TRENDING = "TRENDING"


@dataclass
class HurstConfig:
    """Configuration for Hurst regime detection."""

    # Calculation parameters
    hurst_lookback: int = 100  # Bars for Hurst calculation

    # Regime thresholds
    hurst_trending_threshold: float = 0.55  # H > this = trending
    hurst_mean_reverting_threshold: float = 0.45  # H < this = mean reverting
    hurst_random_threshold_low: float = 0.48  # Random walk bounds
    hurst_random_threshold_high: float = 0.52

    # Size adjustments
    random_walk_size_multiplier: float = 0.5  # Reduce size in random walk


class HurstRegimeDetector:
    """
    Detect market regime using Hurst Exponent.

    The Hurst exponent H measures long-term memory in time series:
    - H < 0.5: Anti-persistent (mean-reverting)
    - H = 0.5: Random walk (no memory)
    - H > 0.5: Persistent (trending)

    Example:
        detector = HurstRegimeDetector(config)

        # Update with price data
        regime = detector.update_regime("EURUSD", prices)

        # Check strategy permissions
        if detector.should_allow_signal("EURUSD", "TSM"):
            execute_signal()
    """

    def __init__(self, config: Optional[HurstConfig] = None):
        self.cfg = config or HurstConfig()

        # Cache
        self._hurst_cache: Dict[str, float] = {}
        self._regime_cache: Dict[str, MarketRegime] = {}
        self._last_update: Dict[str, datetime] = {}

        logger.info(
            f"HurstRegimeDetector initialized: lookback={self.cfg.hurst_lookback}, "
            f"trending>{self.cfg.hurst_trending_threshold}, "
            f"mean_rev<{self.cfg.hurst_mean_reverting_threshold}"
        )

    def calculate_hurst(self, prices: pd.Series) -> float:
        """
        Calculate Hurst Exponent using R/S (Rescaled Range) Analysis.

        Args:
            prices: Price series (must be positive)

        Returns:
            Hurst exponent in range [0, 1]

        Edge Cases:
            - Insufficient data: returns 0.5 (random walk assumption)
            - Zero/negative prices: returns 0.5 with warning
            - Zero variance: returns 0.5
            - Calculation failure: returns 0.5 with warning
        """
        if len(prices) < self.cfg.hurst_lookback:
            return 0.5  # Default to random

        prices_arr = prices.tail(self.cfg.hurst_lookback).values
        n = len(prices_arr)

        # Validate prices (must be positive for log)
        if np.any(prices_arr <= 0):
            logger.warning("Hurst calculation: non-positive prices detected")
            return 0.5

        # Calculate log returns
        with np.errstate(divide="ignore", invalid="ignore"):
            log_returns = np.diff(np.log(prices_arr))

        # Check for NaN/Inf values
        if np.any(~np.isfinite(log_returns)):
            logger.warning("Hurst calculation: non-finite log returns")
            return 0.5

        # Check for zero variance (constant prices)
        if np.std(log_returns) == 0:
            logger.debug("Hurst calculation: zero variance in returns")
            return 0.5

        # R/S calculation for different lag values
        lags = range(2, min(n // 2, 50))
        rs_values = []

        for lag in lags:
            # Split into non-overlapping segments
            num_segments = n // lag
            rs_for_lag = []

            for i in range(num_segments):
                segment = log_returns[i * lag : (i + 1) * lag]
                if len(segment) < 2:
                    continue

                # Mean-adjusted cumulative sum
                mean_adj = segment - np.mean(segment)
                cumsum = np.cumsum(mean_adj)

                # Range
                R = np.max(cumsum) - np.min(cumsum)

                # Standard deviation
                S = np.std(segment, ddof=1)

                if S > 0 and np.isfinite(R) and np.isfinite(S):
                    rs_for_lag.append(R / S)

            if rs_for_lag:
                rs_values.append((lag, np.mean(rs_for_lag)))

        if len(rs_values) < 3:
            logger.debug("Hurst calculation: insufficient R/S values")
            return 0.5

        # Linear regression: log(R/S) = H * log(n) + c
        log_lags = np.log([x[0] for x in rs_values])
        log_rs = np.log([x[1] for x in rs_values])

        # Check for valid log values
        if np.any(~np.isfinite(log_lags)) or np.any(~np.isfinite(log_rs)):
            logger.warning("Hurst calculation: non-finite values in log regression")
            return 0.5

        # Linear regression
        try:
            slope, _ = np.polyfit(log_lags, log_rs, 1)
        except (np.linalg.LinAlgError, ValueError) as e:
            logger.warning(f"Hurst calculation: polyfit failed - {e}")
            return 0.5

        # Check for valid slope
        if not np.isfinite(slope):
            logger.warning("Hurst calculation: non-finite slope from polyfit")
            return 0.5

        # Bound Hurst to [0, 1]
        hurst = max(0.0, min(1.0, slope))

        return float(hurst)

    def update_regime(self, pair: str, prices: pd.Series) -> MarketRegime:
        """
        Calculate Hurst and determine regime for a pair.

        Args:
            pair: Currency pair
            prices: Price series

        Returns:
            Current market regime
        """
        hurst = self.calculate_hurst(prices)
        self._hurst_cache[pair] = hurst
        self._last_update[pair] = datetime.now(timezone.utc)

        # Determine regime
        if hurst < self.cfg.hurst_mean_reverting_threshold:
            regime = MarketRegime.MEAN_REVERTING
        elif hurst > self.cfg.hurst_trending_threshold:
            regime = MarketRegime.TRENDING
        else:
            regime = MarketRegime.RANDOM_WALK

        # Log regime change
        old_regime = self._regime_cache.get(pair)
        if old_regime != regime:
            logger.info(f"HURST REGIME: {pair} H={hurst:.3f} -> {regime.value}")

        self._regime_cache[pair] = regime
        return regime

    def get_regime(self, pair: str) -> MarketRegime:
        """Get current regime for a pair."""
        return self._regime_cache.get(pair, MarketRegime.RANDOM_WALK)

    def get_hurst(self, pair: str) -> float:
        """Get current Hurst exponent for a pair."""
        return self._hurst_cache.get(pair, 0.5)

    def get_strategy_permissions(self, pair: str) -> Dict[str, Any]:
        """
        Get which strategies are allowed for this pair.

        Returns:
            Dict with strategy permissions and size multiplier
        """
        regime = self._regime_cache.get(pair, MarketRegime.RANDOM_WALK)

        if regime == MarketRegime.MEAN_REVERTING:
            return {
                "stat_arb": True,
                "momentum": False,
                "mean_reversion": True,
                "size_multiplier": 1.0,
            }
        elif regime == MarketRegime.TRENDING:
            return {
                "stat_arb": False,
                "momentum": True,
                "mean_reversion": False,
                "size_multiplier": 1.0,
            }
        else:  # RANDOM_WALK
            return {
                "stat_arb": False,
                "momentum": False,
                "mean_reversion": False,
                "size_multiplier": self.cfg.random_walk_size_multiplier,
            }

    def should_allow_signal(self, pair: str, strategy: str) -> Tuple[bool, str]:
        """
        Check if a strategy signal should be allowed for this regime.

        Args:
            pair: Currency pair
            strategy: Strategy name

        Returns:
            Tuple of (allowed, reason)
        """
        permissions = self.get_strategy_permissions(pair)
        regime = self._regime_cache.get(pair, MarketRegime.RANDOM_WALK)
        hurst = self._hurst_cache.get(pair, 0.5)

        strategy_lower = strategy.lower()

        if "stat_arb" in strategy_lower or "csmr" in strategy_lower:
            if not permissions["stat_arb"]:
                return False, f"StatArb blocked: {regime.value} (H={hurst:.2f})"

        if "tsm" in strategy_lower or "csm" in strategy_lower or "momentum" in strategy_lower:
            if not permissions["momentum"]:
                return False, f"Momentum blocked: {regime.value} (H={hurst:.2f})"

        if "mr" in strategy_lower or "mean_rev" in strategy_lower:
            if not permissions["mean_reversion"]:
                return False, f"MR blocked: {regime.value} (H={hurst:.2f})"

        return True, ""

    def get_size_multiplier(self, pair: str) -> float:
        """Get position size multiplier based on regime."""
        permissions = self.get_strategy_permissions(pair)
        return permissions["size_multiplier"]

    def get_statistics(self) -> Dict[str, Any]:
        """Get regime detector statistics."""
        return {
            "pairs_tracked": len(self._hurst_cache),
            "regimes": {
                pair: {
                    "hurst": self._hurst_cache.get(pair, 0.5),
                    "regime": self._regime_cache.get(pair, MarketRegime.RANDOM_WALK).value,
                    "last_update": (
                        self._last_update[pair].isoformat()
                        if pair in self._last_update
                        else None
                    ),
                }
                for pair in self._hurst_cache
            },
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "MarketRegime",
    "HurstConfig",
    "HurstRegimeDetector",
]
