"""
WebSocket Event Types

Defines all event types for real-time communication.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """WebSocket event types."""

    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_MODIFIED = "position_modified"
    POSITION_UPDATE = "position_update"  # Price/profit update
    POSITIONS_SYNC = "positions_sync"

    # Account events
    ACCOUNT_UPDATE = "account_update"
    BALANCE_CHANGE = "balance_change"

    # Trading events
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"

    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_APPROVED = "signal_approved"
    SIGNAL_REJECTED = "signal_rejected"
    SIGNAL_EXECUTED = "signal_executed"

    # Risk events
    RISK_ALERT = "risk_alert"
    PANIC_HEDGE_TRIGGERED = "panic_hedge_triggered"
    DRAWDOWN_WARNING = "drawdown_warning"
    DRAWDOWN_HALT = "drawdown_halt"
    KILL_SWITCH_ACTIVATED = "kill_switch_activated"

    # System events
    MT5_CONNECTED = "mt5_connected"
    MT5_DISCONNECTED = "mt5_disconnected"
    TRADING_ENABLED = "trading_enabled"
    TRADING_DISABLED = "trading_disabled"
    SYSTEM_MESSAGE = "system_message"


class Severity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BaseEvent(BaseModel):
    """Base event structure."""

    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    profile_id: Optional[UUID] = None


class ConnectionEvent(BaseEvent):
    """Connection status event."""

    message: str


class ErrorEvent(BaseEvent):
    """Error event."""

    type: EventType = EventType.ERROR
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class PositionEvent(BaseEvent):
    """Position update event."""

    ticket: int
    symbol: str
    position_type: str
    volume: Decimal
    open_price: Decimal
    current_price: Optional[Decimal] = None
    profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None


class PositionUpdateEvent(BaseEvent):
    """Position price/profit update (lightweight)."""

    type: EventType = EventType.POSITION_UPDATE
    ticket: int
    current_price: Decimal
    profit: Decimal
    swap: Optional[Decimal] = None


class PositionsSyncEvent(BaseEvent):
    """Full positions sync event."""

    type: EventType = EventType.POSITIONS_SYNC
    positions: List[Dict[str, Any]]
    total_profit: Decimal


class AccountUpdateEvent(BaseEvent):
    """Account information update."""

    type: EventType = EventType.ACCOUNT_UPDATE
    balance: Decimal
    equity: Decimal
    margin: Decimal
    free_margin: Decimal
    margin_level: Optional[Decimal] = None
    profit: Decimal


class SignalEvent(BaseEvent):
    """Signal Gate event."""

    signal_id: str
    symbol: str
    direction: str  # "buy" or "sell"
    confidence: Decimal
    sources: List[str]
    decision: Optional[str] = None  # "approved", "rejected"
    reason: Optional[str] = None


class RiskAlertEvent(BaseEvent):
    """Risk alert event."""

    type: EventType = EventType.RISK_ALERT
    severity: Severity
    alert_type: str
    message: str
    current_value: Optional[Decimal] = None
    threshold: Optional[Decimal] = None
    action_taken: Optional[str] = None


class PanicHedgeEvent(BaseEvent):
    """Panic hedge triggered event."""

    type: EventType = EventType.PANIC_HEDGE_TRIGGERED
    trigger_reason: str
    positions_hedged: int
    hedge_details: Optional[Dict[str, Any]] = None


class DrawdownEvent(BaseEvent):
    """Drawdown warning/halt event."""

    current_drawdown: Decimal
    threshold: Decimal
    peak_equity: Decimal
    current_equity: Decimal
    action: str  # "warning" or "halt"


class SystemMessageEvent(BaseEvent):
    """System message event."""

    type: EventType = EventType.SYSTEM_MESSAGE
    severity: Severity = Severity.INFO
    title: str
    message: str
    action_required: bool = False


def create_event(event_type: EventType, profile_id: UUID, **kwargs) -> BaseEvent:
    """Factory function to create events."""
    event_classes = {
        EventType.CONNECTED: ConnectionEvent,
        EventType.DISCONNECTED: ConnectionEvent,
        EventType.ERROR: ErrorEvent,
        EventType.POSITION_UPDATE: PositionUpdateEvent,
        EventType.POSITIONS_SYNC: PositionsSyncEvent,
        EventType.ACCOUNT_UPDATE: AccountUpdateEvent,
        EventType.SIGNAL_GENERATED: SignalEvent,
        EventType.SIGNAL_APPROVED: SignalEvent,
        EventType.SIGNAL_REJECTED: SignalEvent,
        EventType.RISK_ALERT: RiskAlertEvent,
        EventType.PANIC_HEDGE_TRIGGERED: PanicHedgeEvent,
        EventType.DRAWDOWN_WARNING: DrawdownEvent,
        EventType.DRAWDOWN_HALT: DrawdownEvent,
        EventType.SYSTEM_MESSAGE: SystemMessageEvent,
    }

    event_class = event_classes.get(event_type, BaseEvent)
    return event_class(type=event_type, profile_id=profile_id, **kwargs)
