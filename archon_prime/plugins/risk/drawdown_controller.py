# ARCHON_FEAT: drawdown-001
"""
ARCHON PRIME - Drawdown Controller Plugin
=========================================

Drawdown monitoring and trading halt management.

Features:
- Real-time drawdown tracking
- Tiered response (reduce/halt/panic)
- Recovery mode management
- Kill switch functionality

Author: ARCHON Development Team
Version: 1.0.0
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict, Optional

from archon_prime.core.plugin_base import RiskPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType, EventPriority

logger = logging.getLogger("ARCHON_Drawdown")


class DrawdownLevel(Enum):
    """Drawdown severity levels."""

    NORMAL = auto()
    CAUTION = auto()
    REDUCE = auto()
    HALT = auto()
    PANIC = auto()


@dataclass
class DrawdownConfig:
    """Drawdown controller configuration."""

    caution_threshold_pct: float = 3.0   # Warning level
    reduce_threshold_pct: float = 5.0    # Reduce position sizes
    halt_threshold_pct: float = 10.0     # Stop new trades
    panic_threshold_pct: float = 15.0    # Close all positions

    reduce_size_factor: float = 0.5      # Reduce sizes by 50%
    recovery_buffer_pct: float = 2.0     # Buffer before resuming


class DrawdownController(RiskPlugin):
    """
    Drawdown Controller Plugin.

    Monitors account drawdown and implements tiered responses:
    - CAUTION (3%): Log warning
    - REDUCE (5%): Reduce position sizes by 50%
    - HALT (10%): Stop all new trades
    - PANIC (15%): Close all positions

    Recovery requires drawdown to improve by buffer amount.
    """

    def __init__(self, config: Optional[DrawdownConfig] = None):
        super().__init__(PluginConfig(
            name="drawdown_controller",
            version="1.0.0",
            category=PluginCategory.RISK,
            priority=10,  # High priority
            settings=config.__dict__ if config else DrawdownConfig().__dict__,
        ))

        self.dd_config = config or DrawdownConfig()

        # State
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._current_drawdown: float = 0.0
        self._drawdown_level = DrawdownLevel.NORMAL
        self._halt_active: bool = False
        self._last_alert_time: Optional[datetime] = None

    async def evaluate_risk(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate signal against drawdown limits.

        Args:
            signal_data: Signal data

        Returns:
            Risk evaluation with drawdown state
        """
        # Check if trading is halted
        if self._halt_active:
            return {
                "approved": False,
                "reason": f"Trading halted - Drawdown: {self._current_drawdown:.1f}%",
                "drawdown_pct": self._current_drawdown,
                "drawdown_level": self._drawdown_level.name,
            }

        # Apply size reduction if in REDUCE mode
        if self._drawdown_level == DrawdownLevel.REDUCE:
            original_risk = signal_data.get("risk_pct", 1.0)
            adjusted_risk = original_risk * self.dd_config.reduce_size_factor

            return {
                "approved": True,
                "adjusted": True,
                "original_risk_pct": original_risk,
                "adjusted_risk_pct": adjusted_risk,
                "drawdown_pct": self._current_drawdown,
                "drawdown_level": self._drawdown_level.name,
                "reason": "Position reduced due to drawdown",
            }

        return {
            "approved": True,
            "drawdown_pct": self._current_drawdown,
            "drawdown_level": self._drawdown_level.name,
        }

    async def update_equity(self, equity: float) -> None:
        """
        Update equity and check drawdown levels.

        Args:
            equity: Current account equity
        """
        self._current_equity = equity

        # Update peak
        if equity > self._peak_equity:
            self._peak_equity = equity

            # Check for recovery
            if self._halt_active:
                await self._check_recovery()

        # Calculate drawdown
        if self._peak_equity > 0:
            self._current_drawdown = ((self._peak_equity - equity) / self._peak_equity) * 100
        else:
            self._current_drawdown = 0.0

        # Check levels
        await self._check_drawdown_level()

    async def _check_drawdown_level(self) -> None:
        """Check and update drawdown level."""
        dd = self._current_drawdown
        prev_level = self._drawdown_level

        if dd >= self.dd_config.panic_threshold_pct:
            self._drawdown_level = DrawdownLevel.PANIC
            self._halt_active = True
            await self._emit_panic()

        elif dd >= self.dd_config.halt_threshold_pct:
            self._drawdown_level = DrawdownLevel.HALT
            self._halt_active = True
            await self._emit_halt()

        elif dd >= self.dd_config.reduce_threshold_pct:
            self._drawdown_level = DrawdownLevel.REDUCE
            if prev_level != DrawdownLevel.REDUCE:
                await self._emit_reduce()

        elif dd >= self.dd_config.caution_threshold_pct:
            self._drawdown_level = DrawdownLevel.CAUTION
            if prev_level not in [DrawdownLevel.CAUTION, DrawdownLevel.REDUCE]:
                await self._emit_caution()

        else:
            self._drawdown_level = DrawdownLevel.NORMAL

    async def _check_recovery(self) -> None:
        """Check if recovery allows resuming trading."""
        if not self._halt_active:
            return

        # Calculate recovery threshold
        recovery_threshold = self._drawdown_level
        if self._drawdown_level == DrawdownLevel.HALT:
            threshold = self.dd_config.halt_threshold_pct - self.dd_config.recovery_buffer_pct
        elif self._drawdown_level == DrawdownLevel.PANIC:
            threshold = self.dd_config.panic_threshold_pct - self.dd_config.recovery_buffer_pct
        else:
            threshold = self.dd_config.reduce_threshold_pct

        if self._current_drawdown < threshold:
            self._halt_active = False
            self._logger.info(
                f"Trading resumed - Drawdown recovered to {self._current_drawdown:.1f}%"
            )

    async def _emit_caution(self) -> None:
        """Emit caution alert."""
        await self._publish(Event(
            event_type=EventType.DRAWDOWN_WARNING,
            data={
                "level": "CAUTION",
                "drawdown_pct": self._current_drawdown,
                "threshold_pct": self.dd_config.caution_threshold_pct,
                "peak_equity": self._peak_equity,
                "current_equity": self._current_equity,
            },
            source=self.name,
        ))
        self._logger.warning(
            f"CAUTION: Drawdown at {self._current_drawdown:.1f}%"
        )

    async def _emit_reduce(self) -> None:
        """Emit reduce alert."""
        await self._publish(Event(
            event_type=EventType.DRAWDOWN_WARNING,
            data={
                "level": "REDUCE",
                "drawdown_pct": self._current_drawdown,
                "threshold_pct": self.dd_config.reduce_threshold_pct,
                "size_factor": self.dd_config.reduce_size_factor,
            },
            source=self.name,
        ))
        self._logger.warning(
            f"REDUCE: Drawdown at {self._current_drawdown:.1f}% - "
            f"Reducing position sizes by {(1 - self.dd_config.reduce_size_factor) * 100:.0f}%"
        )

    async def _emit_halt(self) -> None:
        """Emit halt alert."""
        await self._publish(Event(
            event_type=EventType.DRAWDOWN_HALT,
            data={
                "level": "HALT",
                "drawdown_pct": self._current_drawdown,
                "threshold_pct": self.dd_config.halt_threshold_pct,
            },
            source=self.name,
            priority=EventPriority.CRITICAL,
        ))
        self._logger.error(
            f"HALT: Drawdown at {self._current_drawdown:.1f}% - Trading halted!"
        )

    async def _emit_panic(self) -> None:
        """Emit panic hedge alert."""
        await self._publish(Event(
            event_type=EventType.PANIC_HEDGE,
            data={
                "level": "PANIC",
                "drawdown_pct": self._current_drawdown,
                "threshold_pct": self.dd_config.panic_threshold_pct,
                "action": "CLOSE_ALL",
            },
            source=self.name,
            priority=EventPriority.CRITICAL,
        ))
        self._logger.critical(
            f"PANIC: Drawdown at {self._current_drawdown:.1f}% - "
            f"CLOSING ALL POSITIONS!"
        )

    def reset_peak(self) -> None:
        """Reset peak equity (start of new period)."""
        self._peak_equity = self._current_equity
        self._current_drawdown = 0.0
        self._drawdown_level = DrawdownLevel.NORMAL
        self._halt_active = False

    def get_stats(self) -> Dict[str, Any]:
        """Get drawdown statistics."""
        return {
            **super().get_stats(),
            "peak_equity": self._peak_equity,
            "current_equity": self._current_equity,
            "current_drawdown_pct": round(self._current_drawdown, 2),
            "drawdown_level": self._drawdown_level.name,
            "halt_active": self._halt_active,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DrawdownLevel",
    "DrawdownConfig",
    "DrawdownController",
]
