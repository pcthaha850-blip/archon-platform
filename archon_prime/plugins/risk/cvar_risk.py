# ARCHON_FEAT: cvar-risk-001
"""
ARCHON PRIME - CVaR Risk Manager Plugin
=======================================

Conditional Value at Risk management for tail risk control.

Features:
- Portfolio CVaR calculation
- Risk budgeting per strategy
- Tail risk monitoring
- Dynamic position limits

Author: ARCHON Development Team
Version: 1.0.0
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from archon_prime.core.plugin_base import RiskPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_CVaR")


@dataclass
class CVaRConfig:
    """CVaR risk configuration."""

    confidence_level: float = 0.95
    max_cvar_pct: float = 5.0  # Maximum CVaR as % of equity
    lookback_days: int = 252
    min_observations: int = 50
    position_limit_multiplier: float = 0.5  # Reduce positions at high CVaR


class CVaRRiskManager(RiskPlugin):
    """
    Conditional Value at Risk Manager.

    CVaR (Expected Shortfall) measures the expected loss
    in the worst X% of scenarios.

    Features:
    - Historical CVaR calculation
    - Portfolio-level risk budgeting
    - Position limit adjustments
    - Risk alerts
    """

    def __init__(self, config: Optional[CVaRConfig] = None):
        super().__init__(PluginConfig(
            name="cvar_risk",
            version="1.0.0",
            category=PluginCategory.RISK,
            settings=config.__dict__ if config else CVaRConfig().__dict__,
        ))

        self.cvar_config = config or CVaRConfig()

        # Return history
        self._returns: List[float] = []
        self._current_cvar: float = 0.0
        self._current_equity: float = 10000.0
        self._risk_budget_used: float = 0.0

    async def evaluate_risk(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate signal against CVaR limits.

        Args:
            signal_data: Signal data

        Returns:
            Risk evaluation with CVaR analysis
        """
        symbol = signal_data.get("symbol")
        risk_pct = signal_data.get("risk_pct", 1.0)

        # Calculate current CVaR
        cvar = self._calculate_cvar()

        # Check if CVaR budget allows new position
        potential_cvar = cvar + risk_pct
        max_cvar = self.cvar_config.max_cvar_pct

        if potential_cvar > max_cvar:
            # Apply position limit multiplier
            adjusted_risk = risk_pct * self.cvar_config.position_limit_multiplier

            if cvar + adjusted_risk > max_cvar:
                await self._publish(Event(
                    event_type=EventType.RISK_ALERT,
                    data={
                        "alert_type": "CVAR_LIMIT",
                        "current_cvar": cvar,
                        "max_cvar": max_cvar,
                        "symbol": symbol,
                    },
                    source=self.name,
                ))

                return {
                    "approved": False,
                    "reason": f"CVaR limit exceeded: {cvar:.1f}% / {max_cvar:.1f}%",
                    "current_cvar": cvar,
                    "max_cvar": max_cvar,
                }

            # Approved with reduced size
            return {
                "approved": True,
                "adjusted": True,
                "original_risk_pct": risk_pct,
                "adjusted_risk_pct": adjusted_risk,
                "current_cvar": cvar,
                "reason": "Position reduced due to CVaR",
            }

        # Fully approved
        self._risk_budget_used += risk_pct

        return {
            "approved": True,
            "current_cvar": cvar,
            "risk_budget_remaining": max_cvar - potential_cvar,
        }

    def _calculate_cvar(self) -> float:
        """Calculate CVaR from return history."""
        if len(self._returns) < self.cvar_config.min_observations:
            return 0.0

        # Sort returns (worst to best)
        sorted_returns = sorted(self._returns)

        # Calculate VaR index
        var_index = int((1 - self.cvar_config.confidence_level) * len(sorted_returns))
        var_index = max(1, var_index)

        # CVaR is average of worst returns
        worst_returns = sorted_returns[:var_index]

        if worst_returns:
            cvar = -sum(worst_returns) / len(worst_returns) * 100
            self._current_cvar = cvar
            return cvar

        return 0.0

    def add_return(self, daily_return: float) -> None:
        """Add daily return to history."""
        self._returns.append(daily_return)

        # Trim to lookback
        max_obs = self.cvar_config.lookback_days
        if len(self._returns) > max_obs:
            self._returns = self._returns[-max_obs:]

        # Recalculate CVaR
        self._calculate_cvar()

    def update_equity(self, equity: float) -> None:
        """Update current equity."""
        if self._current_equity > 0:
            daily_return = (equity - self._current_equity) / self._current_equity
            self.add_return(daily_return)

        self._current_equity = equity

    def reset_risk_budget(self) -> None:
        """Reset daily risk budget."""
        self._risk_budget_used = 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get risk statistics."""
        return {
            **super().get_stats(),
            "current_cvar": round(self._current_cvar, 2),
            "max_cvar": self.cvar_config.max_cvar_pct,
            "risk_budget_used": round(self._risk_budget_used, 2),
            "observations": len(self._returns),
            "current_equity": self._current_equity,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CVaRConfig",
    "CVaRRiskManager",
]
