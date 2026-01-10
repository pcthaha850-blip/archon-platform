# ARCHON_FEAT: dashboard-002
"""
ARCHON PRIME - Dashboard Data Provider
======================================

Provides data interface for the Streamlit dashboard.

Features:
- Real-time metrics access
- Historical data queries
- Plugin status
- System health

Author: ARCHON Development Team
Version: 1.0.0
"""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import random


@dataclass
class EquityPoint:
    """Equity curve data point."""
    timestamp: datetime
    equity: float
    balance: float
    drawdown_pct: float


@dataclass
class TradeRecord:
    """Trade record for display."""
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    exit_price: Optional[float]
    pnl: float
    status: str
    open_time: datetime
    close_time: Optional[datetime]


@dataclass
class PositionRecord:
    """Open position for display."""
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    open_time: datetime


@dataclass
class StrategyStats:
    """Strategy performance statistics."""
    name: str
    enabled: bool
    trades: int
    win_rate: float
    pnl: float
    sharpe: float
    status: str


@dataclass
class RiskMetrics:
    """Risk metrics snapshot."""
    current_drawdown_pct: float
    max_drawdown_pct: float
    daily_var: float
    exposure_pct: float
    correlation_risk: float
    risk_status: str


class DashboardDataProvider:
    """
    Data provider for the ARCHON PRIME dashboard.

    Connects to the system's state store and metrics
    to provide real-time data for visualization.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or "archon_state.db"
        self._demo_mode = not Path(self.db_path).exists()

        # Cache for demo data
        self._demo_equity: List[EquityPoint] = []
        self._demo_trades: List[TradeRecord] = []
        self._demo_positions: List[PositionRecord] = []

        if self._demo_mode:
            self._generate_demo_data()

    def _generate_demo_data(self) -> None:
        """Generate demo data for testing."""
        now = datetime.now(timezone.utc)

        # Generate equity curve (last 30 days)
        equity = 10000.0
        peak = equity

        for i in range(30 * 24):  # Hourly points
            timestamp = now - timedelta(hours=30*24 - i)

            # Random walk with slight upward bias
            change = random.gauss(0.001, 0.005) * equity
            equity += change
            equity = max(equity, 5000)  # Floor

            if equity > peak:
                peak = equity

            dd = (peak - equity) / peak * 100 if peak > 0 else 0

            self._demo_equity.append(EquityPoint(
                timestamp=timestamp,
                equity=round(equity, 2),
                balance=round(equity - random.uniform(0, 200), 2),
                drawdown_pct=round(dd, 2),
            ))

        # Generate recent trades
        symbols = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]

        for i in range(20):
            symbol = random.choice(symbols)
            direction = random.choice(["BUY", "SELL"])
            entry = random.uniform(1.0, 2000.0) if symbol == "XAUUSD" else random.uniform(1.0, 1.5)

            pnl = random.gauss(50, 100)
            exit_price = entry + (pnl / 100000 if direction == "BUY" else -pnl / 100000)

            self._demo_trades.append(TradeRecord(
                ticket=1000 + i,
                symbol=symbol,
                direction=direction,
                volume=round(random.uniform(0.01, 0.1), 2),
                entry_price=round(entry, 5),
                exit_price=round(exit_price, 5),
                pnl=round(pnl, 2),
                status="CLOSED",
                open_time=now - timedelta(hours=random.randint(1, 500)),
                close_time=now - timedelta(hours=random.randint(0, 24)),
            ))

        # Generate open positions
        for i in range(3):
            symbol = random.choice(symbols)
            direction = random.choice(["BUY", "SELL"])
            entry = random.uniform(1.0, 2000.0) if symbol == "XAUUSD" else random.uniform(1.0, 1.5)
            current = entry + random.gauss(0, 0.001)

            pnl = (current - entry) * 100000 * 0.1
            if direction == "SELL":
                pnl = -pnl

            self._demo_positions.append(PositionRecord(
                ticket=2000 + i,
                symbol=symbol,
                direction=direction,
                volume=round(random.uniform(0.01, 0.1), 2),
                entry_price=round(entry, 5),
                current_price=round(current, 5),
                unrealized_pnl=round(pnl, 2),
                open_time=now - timedelta(hours=random.randint(1, 48)),
            ))

    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary."""
        if self._demo_mode:
            latest = self._demo_equity[-1] if self._demo_equity else None
            return {
                "balance": latest.balance if latest else 10000.0,
                "equity": latest.equity if latest else 10000.0,
                "margin": random.uniform(100, 500),
                "free_margin": latest.equity - random.uniform(100, 500) if latest else 9500.0,
                "margin_level_pct": random.uniform(500, 2000),
                "unrealized_pnl": sum(p.unrealized_pnl for p in self._demo_positions),
                "daily_pnl": random.uniform(-200, 500),
                "currency": "USD",
            }

        # TODO: Connect to real system
        return {}

    def get_equity_curve(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get equity curve data."""
        if self._demo_mode:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            points = [p for p in self._demo_equity if p.timestamp >= cutoff]
            return [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "equity": p.equity,
                    "balance": p.balance,
                    "drawdown_pct": p.drawdown_pct,
                }
                for p in points
            ]

        return []

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Get open positions."""
        if self._demo_mode:
            return [asdict(p) for p in self._demo_positions]

        return []

    def get_recent_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent closed trades."""
        if self._demo_mode:
            trades = sorted(
                self._demo_trades,
                key=lambda t: t.close_time or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )[:limit]
            return [asdict(t) for t in trades]

        return []

    def get_strategy_stats(self) -> List[Dict[str, Any]]:
        """Get strategy statistics."""
        strategies = [
            StrategyStats(
                name="TSM (Trend-Structure-Momentum)",
                enabled=True,
                trades=45,
                win_rate=78.5,
                pnl=1250.50,
                sharpe=2.8,
                status="RUNNING",
            ),
            StrategyStats(
                name="VMR (Volatility-Momentum-Regime)",
                enabled=True,
                trades=32,
                win_rate=72.0,
                pnl=890.25,
                sharpe=2.1,
                status="RUNNING",
            ),
            StrategyStats(
                name="Statistical Arbitrage",
                enabled=False,
                trades=0,
                win_rate=0.0,
                pnl=0.0,
                sharpe=0.0,
                status="DISABLED",
            ),
        ]

        return [asdict(s) for s in strategies]

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get current risk metrics."""
        if self._demo_mode:
            latest = self._demo_equity[-1] if self._demo_equity else None
            dd = latest.drawdown_pct if latest else 0.0

            status = "NORMAL"
            if dd > 5:
                status = "CAUTION"
            if dd > 8:
                status = "WARNING"
            if dd > 10:
                status = "CRITICAL"

            return asdict(RiskMetrics(
                current_drawdown_pct=dd,
                max_drawdown_pct=max(p.drawdown_pct for p in self._demo_equity) if self._demo_equity else 0,
                daily_var=random.uniform(100, 300),
                exposure_pct=random.uniform(10, 40),
                correlation_risk=random.uniform(0.1, 0.5),
                risk_status=status,
            ))

        return {}

    def get_plugin_status(self) -> List[Dict[str, Any]]:
        """Get all plugin statuses."""
        plugins = [
            {"name": "EventBus", "category": "CORE", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "MetricsCollector", "category": "MONITORING", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "AlertManager", "category": "MONITORING", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "TSM Strategy", "category": "STRATEGY", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "VMR Strategy", "category": "STRATEGY", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "Kelly Sizer", "category": "RISK", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "CVaR Risk", "category": "RISK", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "Drawdown Controller", "category": "RISK", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "Ghost Executor", "category": "EXECUTION", "status": "RUNNING", "health": "HEALTHY"},
            {"name": "Paper Broker", "category": "BROKER", "status": "CONNECTED", "health": "HEALTHY"},
        ]

        return plugins

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        return {
            "status": "OPERATIONAL",
            "uptime_hours": random.uniform(10, 500),
            "events_processed": random.randint(10000, 100000),
            "errors_last_hour": random.randint(0, 5),
            "latency_ms": random.uniform(5, 50),
            "memory_mb": random.uniform(200, 500),
            "cpu_pct": random.uniform(5, 30),
        }

    def trigger_kill_switch(self) -> bool:
        """Trigger emergency kill switch."""
        # In production, this would halt all trading
        return True

    def toggle_plugin(self, plugin_name: str, enabled: bool) -> bool:
        """Enable/disable a plugin."""
        # In production, this would toggle the plugin
        return True


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DashboardDataProvider",
    "EquityPoint",
    "TradeRecord",
    "PositionRecord",
    "StrategyStats",
    "RiskMetrics",
]
