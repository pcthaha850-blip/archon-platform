"""
ARCHON RI v6.3 - CVaR (Conditional Value at Risk) Engine
=========================================================

Computes tail risk measures for position and portfolio level constraints.

CVaR (also known as Expected Shortfall) is a more robust risk measure
than VaR because it accounts for the severity of losses beyond the VaR
threshold, making it better suited for fat-tailed return distributions
common in financial markets.

Formulas:
    VaR(alpha) = -percentile(returns, (1-alpha)*100)
    CVaR(alpha) = E[loss | loss > VaR(alpha)]

Example:
    At 95% confidence:
    - VaR tells you: "We're 95% sure losses won't exceed X"
    - CVaR tells you: "When losses DO exceed X, the average loss is Y"

Author: ARCHON RI Development Team
Version: 6.3.0
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("ARCHON_CVaREngine")


@dataclass
class CVaRConfig:
    """Configuration for CVaR risk calculations."""

    # Calculation parameters
    cvar_lookback: int = 60  # Rolling window for CVaR calculation (days)
    cvar_confidence_position: float = 0.95  # Per-position CVaR confidence
    cvar_confidence_portfolio: float = 0.99  # Portfolio-level CVaR confidence

    # Risk limits
    max_cvar_per_position_pct: float = 2.0  # Max CVaR per position (% of equity)
    max_cvar_portfolio_pct: float = 5.0  # Max portfolio CVaR (% of equity)

    # Logging
    log_cvar_breaches: bool = True


@dataclass
class CVaRResult:
    """Result of CVaR evaluation."""

    # Raw values
    var_position: float  # Value at Risk for position
    cvar_position: float  # CVaR for position
    cvar_portfolio: float  # CVaR for portfolio

    # As percentage of equity
    position_cvar_pct: Optional[float]
    portfolio_cvar_pct: Optional[float]

    # Limit flags
    position_cvar_limit_hit: bool
    portfolio_cvar_limit_hit: bool

    # Data quality
    data_sufficient: bool


class CVaREngine:
    """
    Conditional Value at Risk (CVaR) / Expected Shortfall Engine.

    Computes tail risk measures for position and portfolio level constraints.
    Used to prevent taking positions with excessive tail risk.

    Example:
        engine = CVaREngine(config)

        result = engine.evaluate_cvar_limits(
            pair_returns=returns_series,
            portfolio_returns=portfolio_series,
            account_equity=500.0
        )

        if result.position_cvar_limit_hit:
            print("Position CVaR exceeds limit!")
    """

    def __init__(self, config: Optional[CVaRConfig] = None):
        self.cfg = config or CVaRConfig()
        self._breach_history: List[Dict[str, Any]] = []

        logger.info(
            f"CVaREngine initialized: lookback={self.cfg.cvar_lookback}, "
            f"position_conf={self.cfg.cvar_confidence_position:.0%}, "
            f"portfolio_conf={self.cfg.cvar_confidence_portfolio:.0%}"
        )

    def compute_var(self, returns: pd.Series, confidence: float) -> float:
        """
        Compute Value at Risk at given confidence level.

        VaR answers: "What is the maximum loss at X% confidence?"

        Args:
            returns: Series of historical returns
            confidence: Confidence level (e.g., 0.95 for 95%)

        Returns:
            VaR value (typically negative, representing loss)
        """
        if len(returns) < self.cfg.cvar_lookback:
            return np.nan

        window = returns.tail(self.cfg.cvar_lookback)
        return float(np.percentile(window, (1 - confidence) * 100))

    def compute_cvar(self, returns: pd.Series, confidence: float) -> float:
        """
        Compute Conditional VaR (Expected Shortfall).

        CVaR is the expected loss given that loss exceeds VaR.
        More robust than VaR for fat-tailed distributions.

        Args:
            returns: Series of historical returns
            confidence: Confidence level (e.g., 0.95 for 95%)

        Returns:
            CVaR value (typically negative, representing expected tail loss)
        """
        if len(returns) < self.cfg.cvar_lookback:
            return np.nan

        window = returns.tail(self.cfg.cvar_lookback)
        sorted_returns = np.sort(window.values)

        # Number of observations in the tail
        alpha_index = int((1 - confidence) * len(sorted_returns))
        alpha_index = max(1, alpha_index)  # At least 1 observation

        # Average of tail losses
        tail = sorted_returns[:alpha_index]
        if len(tail) == 0:
            return np.nan

        return float(tail.mean())

    def evaluate_cvar_limits(
        self,
        pair_returns: pd.Series,
        portfolio_returns: pd.Series,
        account_equity: float,
        position_size_factor: float = 1.0,
    ) -> CVaRResult:
        """
        Evaluate CVaR constraints for proposed trade.

        Args:
            pair_returns: Historical returns for the pair
            portfolio_returns: Portfolio-level returns
            account_equity: Current account equity
            position_size_factor: Scaling factor for position

        Returns:
            CVaRResult with metrics and limit flags
        """
        # Compute CVaR values
        cvar_pos = self.compute_cvar(
            pair_returns, self.cfg.cvar_confidence_position
        )
        cvar_portfolio = self.compute_cvar(
            portfolio_returns, self.cfg.cvar_confidence_portfolio
        )
        var_pos = self.compute_var(pair_returns, self.cfg.cvar_confidence_position)

        # Check data sufficiency
        if np.isnan(cvar_pos) or np.isnan(cvar_portfolio):
            return CVaRResult(
                var_position=var_pos if not np.isnan(var_pos) else 0.0,
                cvar_position=0.0,
                cvar_portfolio=0.0,
                position_cvar_pct=None,
                portfolio_cvar_pct=None,
                position_cvar_limit_hit=False,
                portfolio_cvar_limit_hit=False,
                data_sufficient=False,
            )

        # Convert to percentage of equity (CVaR is typically negative)
        # Scale by position size factor
        position_cvar_pct = abs(cvar_pos) * position_size_factor * 100.0
        portfolio_cvar_pct = abs(cvar_portfolio) * 100.0

        # Check limits
        position_limit_hit = position_cvar_pct > self.cfg.max_cvar_per_position_pct
        portfolio_limit_hit = portfolio_cvar_pct > self.cfg.max_cvar_portfolio_pct

        # Log breaches
        if position_limit_hit and self.cfg.log_cvar_breaches:
            logger.warning(
                f"CVaR BREACH (Position): {position_cvar_pct:.2f}% "
                f"> {self.cfg.max_cvar_per_position_pct}%"
            )
            self._breach_history.append(
                {
                    "type": "position",
                    "cvar_pct": position_cvar_pct,
                    "limit": self.cfg.max_cvar_per_position_pct,
                }
            )

        if portfolio_limit_hit and self.cfg.log_cvar_breaches:
            logger.warning(
                f"CVaR BREACH (Portfolio): {portfolio_cvar_pct:.2f}% "
                f"> {self.cfg.max_cvar_portfolio_pct}%"
            )
            self._breach_history.append(
                {
                    "type": "portfolio",
                    "cvar_pct": portfolio_cvar_pct,
                    "limit": self.cfg.max_cvar_portfolio_pct,
                }
            )

        return CVaRResult(
            var_position=var_pos,
            cvar_position=cvar_pos,
            cvar_portfolio=cvar_portfolio,
            position_cvar_pct=position_cvar_pct,
            portfolio_cvar_pct=portfolio_cvar_pct,
            position_cvar_limit_hit=position_limit_hit,
            portfolio_cvar_limit_hit=portfolio_limit_hit,
            data_sufficient=True,
        )

    def get_breach_history(self) -> List[Dict[str, Any]]:
        """Return history of CVaR breaches."""
        return self._breach_history.copy()

    def clear_breach_history(self) -> None:
        """Clear the breach history."""
        self._breach_history.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get CVaR engine statistics."""
        return {
            "lookback_days": self.cfg.cvar_lookback,
            "position_confidence": self.cfg.cvar_confidence_position,
            "portfolio_confidence": self.cfg.cvar_confidence_portfolio,
            "max_position_cvar_pct": self.cfg.max_cvar_per_position_pct,
            "max_portfolio_cvar_pct": self.cfg.max_cvar_portfolio_pct,
            "total_breaches": len(self._breach_history),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["CVaRConfig", "CVaRResult", "CVaREngine"]
