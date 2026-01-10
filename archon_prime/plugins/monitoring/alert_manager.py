# ARCHON_FEAT: alerts-001
"""
ARCHON PRIME - Alert Manager Plugin
===================================

System alerting and notification management.

Features:
- Multi-channel alerts (log, email, webhook)
- Alert severity levels
- Rate limiting
- Alert history

Author: ARCHON Development Team
Version: 1.0.0
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from archon_prime.core.plugin_base import MonitoringPlugin, PluginConfig, PluginCategory
from archon_prime.core.event_bus import Event, EventType

logger = logging.getLogger("ARCHON_Alerts")


class AlertLevel(Enum):
    """Alert severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """Alert record."""

    level: AlertLevel
    message: str
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    sent_channels: List[str] = field(default_factory=list)


@dataclass
class AlertConfig:
    """Alert manager configuration."""

    min_level: AlertLevel = AlertLevel.WARNING
    rate_limit_sec: int = 60
    max_alerts_per_period: int = 10
    log_alerts: bool = True
    email_enabled: bool = False
    email_recipient: str = ""
    webhook_enabled: bool = False
    webhook_url: str = ""


class AlertManager(MonitoringPlugin):
    """
    Alert Manager Plugin.

    Handles system alerts and notifications:
    - Receives alerts from all plugins
    - Rate limits to prevent alert storms
    - Routes to configured channels
    - Maintains alert history

    Alert Channels:
    - Log: Always logged
    - Email: Optional email notifications
    - Webhook: Optional webhook calls
    """

    def __init__(self, config: Optional[AlertConfig] = None):
        super().__init__(PluginConfig(
            name="alert_manager",
            version="1.0.0",
            category=PluginCategory.MONITORING,
            settings=config.__dict__ if config else AlertConfig().__dict__,
        ))

        self.alert_config = config or AlertConfig()

        # Alert storage
        self._alerts: List[Alert] = []
        self._active_alerts: List[Alert] = []

        # Rate limiting
        self._rate_counters: Dict[str, int] = defaultdict(int)
        self._rate_window_start: Dict[str, datetime] = {}

    async def record_metric(
        self, name: str, value: float, tags: Dict[str, str]
    ) -> None:
        """Not used by alert manager."""
        pass

    async def send_alert(
        self, level: str, message: str, context: Dict[str, Any]
    ) -> None:
        """
        Send an alert.

        Args:
            level: Alert level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Alert message
            context: Additional context
        """
        try:
            alert_level = AlertLevel[level.upper()]
        except KeyError:
            alert_level = AlertLevel.WARNING

        # Check minimum level
        if self._get_level_priority(alert_level) < self._get_level_priority(self.alert_config.min_level):
            return

        # Rate limiting
        source = context.get("source", "unknown")
        if not self._check_rate_limit(source):
            self._logger.debug(f"Alert rate limited for {source}")
            return

        alert = Alert(
            level=alert_level,
            message=message,
            source=source,
            context=context,
        )

        # Store alert
        self._alerts.append(alert)
        self._active_alerts.append(alert)

        # Send to channels
        await self._send_to_channels(alert)

    async def _setup_subscriptions(self) -> None:
        """Setup alert subscriptions."""
        from archon_prime.core.event_bus import EventType

        self._subscribe(
            {
                EventType.RISK_ALERT,
                EventType.DRAWDOWN_WARNING,
                EventType.DRAWDOWN_HALT,
                EventType.PANIC_HEDGE,
                EventType.SYSTEM_ERROR,
            },
            self._handle_alert_event
        )

    async def _handle_alert_event(self, event: Event) -> None:
        """Handle alert events from other plugins."""
        level_map = {
            EventType.RISK_ALERT: "WARNING",
            EventType.DRAWDOWN_WARNING: "WARNING",
            EventType.DRAWDOWN_HALT: "ERROR",
            EventType.PANIC_HEDGE: "CRITICAL",
            EventType.SYSTEM_ERROR: "ERROR",
        }

        level = level_map.get(event.event_type, "WARNING")
        message = event.data.get("message", event.event_type.name)

        await self.send_alert(
            level=level,
            message=message,
            context={
                "source": event.source,
                "event_type": event.event_type.name,
                **event.data,
            }
        )

        self._stats["events_processed"] += 1

    def _check_rate_limit(self, source: str) -> bool:
        """Check if source is within rate limit."""
        now = datetime.now(timezone.utc)
        window_start = self._rate_window_start.get(source)

        # Reset window if expired
        if not window_start or (now - window_start).total_seconds() > self.alert_config.rate_limit_sec:
            self._rate_window_start[source] = now
            self._rate_counters[source] = 0

        # Check limit
        if self._rate_counters[source] >= self.alert_config.max_alerts_per_period:
            return False

        self._rate_counters[source] += 1
        return True

    async def _send_to_channels(self, alert: Alert) -> None:
        """Send alert to configured channels."""
        # Always log
        if self.alert_config.log_alerts:
            self._log_alert(alert)
            alert.sent_channels.append("log")

        # Email
        if self.alert_config.email_enabled and self.alert_config.email_recipient:
            await self._send_email(alert)
            alert.sent_channels.append("email")

        # Webhook
        if self.alert_config.webhook_enabled and self.alert_config.webhook_url:
            await self._send_webhook(alert)
            alert.sent_channels.append("webhook")

    def _log_alert(self, alert: Alert) -> None:
        """Log alert to logger."""
        log_func = {
            AlertLevel.DEBUG: self._logger.debug,
            AlertLevel.INFO: self._logger.info,
            AlertLevel.WARNING: self._logger.warning,
            AlertLevel.ERROR: self._logger.error,
            AlertLevel.CRITICAL: self._logger.critical,
        }.get(alert.level, self._logger.warning)

        log_func(f"[{alert.source}] {alert.message}")

    async def _send_email(self, alert: Alert) -> None:
        """Send alert via email."""
        # Implementation would use SMTP
        self._logger.debug(f"Email alert would be sent to {self.alert_config.email_recipient}")

    async def _send_webhook(self, alert: Alert) -> None:
        """Send alert via webhook."""
        # Implementation would use aiohttp
        self._logger.debug(f"Webhook alert would be sent to {self.alert_config.webhook_url}")

    def _get_level_priority(self, level: AlertLevel) -> int:
        """Get numeric priority for level."""
        priorities = {
            AlertLevel.DEBUG: 0,
            AlertLevel.INFO: 1,
            AlertLevel.WARNING: 2,
            AlertLevel.ERROR: 3,
            AlertLevel.CRITICAL: 4,
        }
        return priorities.get(level, 2)

    def acknowledge_alert(self, index: int) -> bool:
        """Acknowledge an active alert."""
        if 0 <= index < len(self._active_alerts):
            self._active_alerts[index].acknowledged = True
            return True
        return False

    def clear_acknowledged(self) -> int:
        """Clear acknowledged alerts."""
        before = len(self._active_alerts)
        self._active_alerts = [a for a in self._active_alerts if not a.acknowledged]
        return before - len(self._active_alerts)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active (unacknowledged) alerts."""
        return [
            {
                "level": a.level.value,
                "message": a.message,
                "source": a.source,
                "timestamp": a.timestamp.isoformat(),
                "acknowledged": a.acknowledged,
            }
            for a in self._active_alerts
        ]

    def get_alert_history(
        self, since: Optional[datetime] = None, level: Optional[AlertLevel] = None
    ) -> List[Dict[str, Any]]:
        """Get alert history with optional filters."""
        alerts = self._alerts

        if since:
            alerts = [a for a in alerts if a.timestamp >= since]

        if level:
            alerts = [a for a in alerts if a.level == level]

        return [
            {
                "level": a.level.value,
                "message": a.message,
                "source": a.source,
                "timestamp": a.timestamp.isoformat(),
            }
            for a in alerts
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get alert manager statistics."""
        level_counts = defaultdict(int)
        for alert in self._alerts:
            level_counts[alert.level.value] += 1

        return {
            **super().get_stats(),
            "total_alerts": len(self._alerts),
            "active_alerts": len(self._active_alerts),
            "alerts_by_level": dict(level_counts),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AlertLevel",
    "Alert",
    "AlertConfig",
    "AlertManager",
]
