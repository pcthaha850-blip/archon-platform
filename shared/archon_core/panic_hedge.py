"""
ARCHON RI v6.3 - Panic Hedge System
=====================================

Emergency protection system that monitors for extreme market conditions
and triggers protective actions when thresholds are breached.

Panic Triggers:
    1. Flash Crash: 2% drop in 60 seconds
    2. Volatility Spike: 3x normal ATR
    3. Spread Explosion: 10x normal spread
    4. Drawdown Breach: Kill switch at threshold

Actions:
    - Hedge all open positions
    - Halt new trade entries
    - Close limit orders
    - Activate kill switch

Author: ARCHON RI Development Team
Version: 6.3.0
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ARCHON_PanicHedge")


class PanicTrigger(Enum):
    """Types of panic triggers."""

    NONE = "NONE"
    FLASH_CRASH = "FLASH_CRASH"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    SPREAD_EXPLOSION = "SPREAD_EXPLOSION"
    DRAWDOWN_BREACH = "DRAWDOWN_BREACH"
    MANUAL_HALT = "MANUAL_HALT"


class PanicAction(Enum):
    """Actions to take during panic."""

    HEDGE_ALL = "HEDGE_ALL"
    HALT_NEW_TRADES = "HALT_NEW_TRADES"
    CLOSE_LIMITS = "CLOSE_LIMITS"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass
class PanicConfig:
    """Configuration for panic hedge system."""

    # Flash crash detection
    flash_crash_pct: float = 2.0  # 2% drop triggers hedge
    flash_crash_window_sec: int = 60  # Within 60 seconds

    # Volatility spike
    volatility_spike_atr_mult: float = 3.0  # 3x ATR triggers halt
    atr_period: int = 14  # ATR calculation period

    # Spread explosion
    spread_explosion_mult: float = 10.0  # 10x normal spread

    # Drawdown kill switch
    drawdown_kill_switch_pct: float = 5.0  # 5% drawdown triggers kill

    # Cooldown after trigger
    cooldown_minutes: int = 30

    # Logging
    log_triggers: bool = True


@dataclass
class PricePoint:
    """A price observation with timestamp."""

    price: float
    timestamp: datetime
    spread: float = 0.0


@dataclass
class PanicState:
    """Current state of the panic hedge system."""

    is_active: bool = False
    trigger: PanicTrigger = PanicTrigger.NONE
    triggered_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    actions_taken: List[PanicAction] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class PanicHedge:
    """
    Emergency protection system for extreme market conditions.

    Monitors price movements, volatility, spreads, and account drawdown
    to detect dangerous conditions and trigger protective actions.

    Example:
        hedge = PanicHedge(config)

        # Register callbacks for panic actions
        hedge.on_panic(callback_function)

        # Update with each price tick
        hedge.update_price("EURUSD", 1.0850, spread=0.0002)

        # Check if trading should be halted
        if hedge.should_halt_trading():
            print("Trading halted due to panic condition!")
    """

    def __init__(self, config: Optional[PanicConfig] = None):
        self.cfg = config or PanicConfig()

        # Price history for flash crash detection
        self._price_history: Dict[str, deque] = {}

        # Baseline values
        self._baseline_spreads: Dict[str, float] = {}
        self._baseline_atr: Dict[str, float] = {}

        # Current state
        self._state = PanicState()

        # Callbacks
        self._panic_callbacks: List[Callable[[PanicState], None]] = []

        # Event history
        self._trigger_history: List[Dict[str, Any]] = []

        logger.info(
            f"PanicHedge initialized: flash={self.cfg.flash_crash_pct}%/{self.cfg.flash_crash_window_sec}s, "
            f"vol_spike={self.cfg.volatility_spike_atr_mult}x ATR, "
            f"spread={self.cfg.spread_explosion_mult}x, "
            f"dd_kill={self.cfg.drawdown_kill_switch_pct}%"
        )

    def on_panic(self, callback: Callable[[PanicState], None]) -> None:
        """Register a callback for panic events."""
        self._panic_callbacks.append(callback)

    def set_baseline_spread(self, pair: str, spread: float) -> None:
        """Set the baseline spread for a pair."""
        self._baseline_spreads[pair] = spread
        logger.debug(f"Baseline spread set for {pair}: {spread}")

    def set_baseline_atr(self, pair: str, atr: float) -> None:
        """Set the baseline ATR for a pair."""
        self._baseline_atr[pair] = atr
        logger.debug(f"Baseline ATR set for {pair}: {atr}")

    def update_price(
        self, pair: str, price: float, spread: float = 0.0
    ) -> Optional[PanicTrigger]:
        """
        Update price and check for panic conditions.

        Args:
            pair: Currency pair
            price: Current price
            spread: Current spread

        Returns:
            PanicTrigger if triggered, None otherwise
        """
        now = datetime.now(timezone.utc)

        # Initialize history if needed
        if pair not in self._price_history:
            self._price_history[pair] = deque(maxlen=1000)

        # Add price point
        self._price_history[pair].append(
            PricePoint(price=price, timestamp=now, spread=spread)
        )

        # Check if in cooldown
        if self._in_cooldown(now):
            return None

        # Check for flash crash
        trigger = self._check_flash_crash(pair, price, now)
        if trigger:
            return trigger

        # Check for spread explosion
        trigger = self._check_spread_explosion(pair, spread, now)
        if trigger:
            return trigger

        return None

    def check_volatility(self, pair: str, current_atr: float) -> Optional[PanicTrigger]:
        """
        Check for volatility spike.

        Args:
            pair: Currency pair
            current_atr: Current ATR value

        Returns:
            PanicTrigger if triggered, None otherwise
        """
        now = datetime.now(timezone.utc)

        if self._in_cooldown(now):
            return None

        baseline = self._baseline_atr.get(pair)
        if baseline is None or baseline <= 0:
            return None

        ratio = current_atr / baseline
        if ratio >= self.cfg.volatility_spike_atr_mult:
            return self._trigger_panic(
                PanicTrigger.VOLATILITY_SPIKE,
                f"{pair} ATR spike: {ratio:.1f}x baseline",
                now,
                {"pair": pair, "current_atr": current_atr, "baseline": baseline, "ratio": ratio},
            )

        return None

    def check_drawdown(
        self, current_equity: float, peak_equity: float
    ) -> Optional[PanicTrigger]:
        """
        Check for drawdown breach.

        Args:
            current_equity: Current account equity
            peak_equity: Peak account equity

        Returns:
            PanicTrigger if triggered, None otherwise
        """
        now = datetime.now(timezone.utc)

        if self._in_cooldown(now):
            return None

        if peak_equity <= 0:
            return None

        dd_pct = ((peak_equity - current_equity) / peak_equity) * 100

        if dd_pct >= self.cfg.drawdown_kill_switch_pct:
            return self._trigger_panic(
                PanicTrigger.DRAWDOWN_BREACH,
                f"Drawdown {dd_pct:.1f}% >= {self.cfg.drawdown_kill_switch_pct}%",
                now,
                {"drawdown_pct": dd_pct, "current": current_equity, "peak": peak_equity},
            )

        return None

    def _check_flash_crash(
        self, pair: str, current_price: float, now: datetime
    ) -> Optional[PanicTrigger]:
        """Check for flash crash condition."""
        history = self._price_history.get(pair)
        if not history or len(history) < 2:
            return None

        # Get price from window seconds ago
        window_start = now - timedelta(seconds=self.cfg.flash_crash_window_sec)

        # Find oldest price in window
        oldest_price = None
        for point in history:
            if point.timestamp >= window_start:
                oldest_price = point.price
                break

        if oldest_price is None or oldest_price <= 0:
            return None

        # Calculate percentage change
        pct_change = ((current_price - oldest_price) / oldest_price) * 100

        if pct_change <= -self.cfg.flash_crash_pct:
            return self._trigger_panic(
                PanicTrigger.FLASH_CRASH,
                f"{pair} flash crash: {pct_change:.2f}% in {self.cfg.flash_crash_window_sec}s",
                now,
                {"pair": pair, "pct_change": pct_change, "from": oldest_price, "to": current_price},
            )

        return None

    def _check_spread_explosion(
        self, pair: str, current_spread: float, now: datetime
    ) -> Optional[PanicTrigger]:
        """Check for spread explosion condition."""
        baseline = self._baseline_spreads.get(pair)
        if baseline is None or baseline <= 0:
            return None

        ratio = current_spread / baseline
        if ratio >= self.cfg.spread_explosion_mult:
            return self._trigger_panic(
                PanicTrigger.SPREAD_EXPLOSION,
                f"{pair} spread explosion: {ratio:.1f}x baseline",
                now,
                {"pair": pair, "current": current_spread, "baseline": baseline, "ratio": ratio},
            )

        return None

    def _trigger_panic(
        self,
        trigger: PanicTrigger,
        detail: str,
        now: datetime,
        metadata: Dict[str, Any],
    ) -> PanicTrigger:
        """Trigger panic state and execute callbacks."""
        # Update state
        self._state = PanicState(
            is_active=True,
            trigger=trigger,
            triggered_at=now,
            cooldown_until=now + timedelta(minutes=self.cfg.cooldown_minutes),
            actions_taken=[PanicAction.HALT_NEW_TRADES],
            details=metadata,
        )

        # Add to history
        self._trigger_history.append(
            {
                "trigger": trigger.value,
                "detail": detail,
                "timestamp": now.isoformat(),
                "metadata": metadata,
            }
        )

        # Log
        if self.cfg.log_triggers:
            logger.warning(f"PANIC TRIGGERED: {trigger.value} - {detail}")

        # Execute callbacks
        for callback in self._panic_callbacks:
            try:
                callback(self._state)
            except Exception as e:
                logger.error(f"Panic callback error: {e}")

        return trigger

    def _in_cooldown(self, now: datetime) -> bool:
        """Check if system is in cooldown period."""
        if self._state.cooldown_until is None:
            return False
        return now < self._state.cooldown_until

    def should_halt_trading(self) -> bool:
        """Check if trading should be halted."""
        return self._state.is_active

    def reset(self) -> None:
        """Reset panic state (use with caution)."""
        self._state = PanicState()
        logger.info("PanicHedge state reset")

    def manual_halt(self, reason: str = "Manual intervention") -> None:
        """Manually trigger trading halt."""
        now = datetime.now(timezone.utc)
        self._trigger_panic(
            PanicTrigger.MANUAL_HALT,
            reason,
            now,
            {"manual": True, "reason": reason},
        )

    def get_state(self) -> PanicState:
        """Get current panic state."""
        return self._state

    def get_trigger_history(self) -> List[Dict[str, Any]]:
        """Get history of panic triggers."""
        return self._trigger_history.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get panic hedge statistics."""
        return {
            "is_active": self._state.is_active,
            "current_trigger": self._state.trigger.value if self._state.trigger else None,
            "triggered_at": (
                self._state.triggered_at.isoformat() if self._state.triggered_at else None
            ),
            "cooldown_until": (
                self._state.cooldown_until.isoformat() if self._state.cooldown_until else None
            ),
            "total_triggers": len(self._trigger_history),
            "pairs_monitored": len(self._price_history),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PanicTrigger",
    "PanicAction",
    "PanicConfig",
    "PanicState",
    "PanicHedge",
]
