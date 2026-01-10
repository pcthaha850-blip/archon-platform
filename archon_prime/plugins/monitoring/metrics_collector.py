# ARCHON_FEAT: metrics-001
"""
ARCHON PRIME - Metrics Collector Plugin
=======================================

System metrics collection and aggregation.

Features:
- Real-time metric collection
- Historical metric storage
- Aggregation functions
- Export capabilities

Author: ARCHON Development Team
Version: 1.0.0
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from archon_prime.core.plugin_base import MonitoringPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_Metrics")


@dataclass
class MetricPoint:
    """Single metric data point."""

    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricsConfig:
    """Metrics collector configuration."""

    retention_hours: int = 24
    aggregation_interval_sec: int = 60
    max_points_per_metric: int = 10000


class MetricsCollector(MonitoringPlugin):
    """
    System Metrics Collector.

    Collects and aggregates metrics from all plugins:
    - Trading metrics (P&L, win rate, etc.)
    - System metrics (event counts, latency)
    - Risk metrics (drawdown, exposure)

    Provides:
    - Real-time metrics access
    - Historical queries
    - Aggregations (avg, min, max, sum)
    """

    def __init__(self, config: Optional[MetricsConfig] = None):
        super().__init__(PluginConfig(
            name="metrics_collector",
            version="1.0.0",
            category=PluginCategory.MONITORING,
            settings=config.__dict__ if config else MetricsConfig().__dict__,
        ))

        self.metrics_config = config or MetricsConfig()

        # Metric storage
        self._metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._latest: Dict[str, MetricPoint] = {}
        self._aggregates: Dict[str, Dict[str, float]] = defaultdict(dict)

        # Trading metrics
        self._trade_count = 0
        self._win_count = 0
        self._total_pnl = 0.0
        self._peak_equity = 0.0
        self._current_dd = 0.0

    async def record_metric(
        self, name: str, value: float, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags
        """
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=datetime.now(timezone.utc),
            tags=tags or {},
        )

        self._metrics[name].append(point)
        self._latest[name] = point

        # Enforce retention
        self._enforce_retention(name)

        # Update aggregates
        self._update_aggregates(name)

    async def send_alert(
        self, level: str, message: str, context: Dict[str, Any]
    ) -> None:
        """Send an alert (delegated to AlertManager)."""
        pass

    async def _setup_subscriptions(self) -> None:
        """Setup monitoring subscriptions."""
        from archon_prime.core.event_bus import EventType

        # Subscribe to all trading events
        self._subscribe(
            {
                EventType.ORDER_FILLED,
                EventType.POSITION_OPENED,
                EventType.POSITION_CLOSED,
                EventType.METRICS_UPDATE,
            },
            self._handle_trading_event
        )

        # Subscribe to risk events
        self._subscribe(
            {
                EventType.RISK_ALERT,
                EventType.DRAWDOWN_WARNING,
                EventType.DRAWDOWN_HALT,
            },
            self._handle_risk_event
        )

    async def _handle_trading_event(self, event: Event) -> None:
        """Handle trading events for metrics."""
        if event.event_type == EventType.POSITION_CLOSED:
            pnl = event.data.get("realized_pnl", 0)
            self._trade_count += 1
            self._total_pnl += pnl

            if pnl > 0:
                self._win_count += 1

            # Record metrics
            await self.record_metric("trade_pnl", pnl)
            await self.record_metric("total_pnl", self._total_pnl)
            await self.record_metric(
                "win_rate",
                (self._win_count / self._trade_count * 100) if self._trade_count > 0 else 0
            )

        elif event.event_type == EventType.METRICS_UPDATE:
            # Record any metrics in the update
            for key, value in event.data.items():
                if isinstance(value, (int, float)):
                    await self.record_metric(key, value)

        self._stats["events_processed"] += 1

    async def _handle_risk_event(self, event: Event) -> None:
        """Handle risk events for metrics."""
        if event.event_type == EventType.DRAWDOWN_WARNING:
            dd = event.data.get("drawdown_pct", 0)
            await self.record_metric("drawdown_pct", dd)
            self._current_dd = dd

        self._stats["events_processed"] += 1

    def _enforce_retention(self, name: str) -> None:
        """Remove old metric points."""
        if name not in self._metrics:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.metrics_config.retention_hours
        )

        self._metrics[name] = [
            p for p in self._metrics[name]
            if p.timestamp > cutoff
        ][-self.metrics_config.max_points_per_metric:]

    def _update_aggregates(self, name: str) -> None:
        """Update aggregate values for metric."""
        if name not in self._metrics:
            return

        values = [p.value for p in self._metrics[name]]
        if not values:
            return

        self._aggregates[name] = {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "latest": values[-1],
        }

    def get_metric(self, name: str) -> Optional[MetricPoint]:
        """Get latest value for a metric."""
        return self._latest.get(name)

    def get_metric_history(
        self, name: str, since: Optional[datetime] = None
    ) -> List[MetricPoint]:
        """Get metric history."""
        if name not in self._metrics:
            return []

        points = self._metrics[name]

        if since:
            points = [p for p in points if p.timestamp >= since]

        return points

    def get_aggregate(self, name: str) -> Dict[str, float]:
        """Get aggregate values for a metric."""
        return self._aggregates.get(name, {})

    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get all current metrics with aggregates."""
        return dict(self._aggregates)

    def get_trading_summary(self) -> Dict[str, Any]:
        """Get trading performance summary."""
        win_rate = (
            self._win_count / self._trade_count * 100
            if self._trade_count > 0 else 0
        )

        return {
            "trade_count": self._trade_count,
            "win_count": self._win_count,
            "loss_count": self._trade_count - self._win_count,
            "win_rate_pct": round(win_rate, 2),
            "total_pnl": round(self._total_pnl, 2),
            "current_drawdown_pct": round(self._current_dd, 2),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
        self._latest.clear()
        self._aggregates.clear()
        self._trade_count = 0
        self._win_count = 0
        self._total_pnl = 0.0
        self._current_dd = 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            **super().get_stats(),
            "metrics_tracked": len(self._metrics),
            "total_points": sum(len(v) for v in self._metrics.values()),
            "trading_summary": self.get_trading_summary(),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "MetricPoint",
    "MetricsConfig",
    "MetricsCollector",
]
