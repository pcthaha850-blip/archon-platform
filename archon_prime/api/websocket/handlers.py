"""
WebSocket Message Handlers

Processes incoming WebSocket messages and triggers appropriate actions.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from archon_prime.api.websocket.events import (
    EventType,
    ErrorEvent,
    Severity,
)
from archon_prime.api.websocket.manager import ClientConnection, ConnectionManager

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles incoming WebSocket messages."""

    def __init__(self, manager: ConnectionManager):
        self.manager = manager
        self._handlers = {
            "ping": self._handle_ping,
            "pong": self._handle_pong,
            "subscribe": self._handle_subscribe,
            "unsubscribe": self._handle_unsubscribe,
            "request_positions": self._handle_request_positions,
            "request_account": self._handle_request_account,
        }

    async def handle_message(
        self,
        connection: ClientConnection,
        message: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Process an incoming WebSocket message.

        Args:
            connection: Client connection
            message: Parsed message dict

        Returns:
            Optional response dict
        """
        msg_type = message.get("type")

        if not msg_type:
            return await self._send_error(
                connection, "INVALID_MESSAGE", "Message type required"
            )

        handler = self._handlers.get(msg_type)
        if handler:
            return await handler(connection, message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
            return await self._send_error(
                connection, "UNKNOWN_TYPE", f"Unknown message type: {msg_type}"
            )

    async def _handle_ping(
        self, connection: ClientConnection, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle ping message."""
        connection.last_ping = datetime.now(timezone.utc)
        return {
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client_id": connection.client_id,
        }

    async def _handle_pong(
        self, connection: ClientConnection, message: Dict[str, Any]
    ) -> None:
        """Handle pong response."""
        connection.last_ping = datetime.now(timezone.utc)
        return None

    async def _handle_subscribe(
        self, connection: ClientConnection, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Subscribe to specific event types."""
        events = message.get("events", [])

        if not isinstance(events, list):
            return await self._send_error(
                connection, "INVALID_FORMAT", "Events must be a list"
            )

        valid_events = []
        for event in events:
            try:
                EventType(event)
                valid_events.append(event)
                connection.subscriptions.add(event)
            except ValueError:
                pass  # Ignore invalid event types

        return {
            "type": "subscribed",
            "events": valid_events,
            "total_subscriptions": list(connection.subscriptions),
        }

    async def _handle_unsubscribe(
        self, connection: ClientConnection, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Unsubscribe from specific event types."""
        events = message.get("events", [])

        if not isinstance(events, list):
            return await self._send_error(
                connection, "INVALID_FORMAT", "Events must be a list"
            )

        for event in events:
            connection.subscriptions.discard(event)

        return {
            "type": "unsubscribed",
            "events": events,
            "remaining_subscriptions": list(connection.subscriptions),
        }

    async def _handle_request_positions(
        self, connection: ClientConnection, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request current positions snapshot."""
        # This would typically fetch from the trading service
        # For now, return a placeholder response
        return {
            "type": "positions_snapshot",
            "profile_id": str(connection.profile_id),
            "positions": [],
            "total_profit": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _handle_request_account(
        self, connection: ClientConnection, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request current account info."""
        # This would typically fetch from the profile service
        return {
            "type": "account_snapshot",
            "profile_id": str(connection.profile_id),
            "balance": 0,
            "equity": 0,
            "margin": 0,
            "free_margin": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _send_error(
        self,
        connection: ClientConnection,
        code: str,
        message: str,
    ) -> Dict[str, Any]:
        """Send error response."""
        error = ErrorEvent(
            type=EventType.ERROR,
            profile_id=connection.profile_id,
            code=code,
            message=message,
        )
        await connection.send_event(error)
        return error.model_dump(mode="json")


class EventBroadcaster:
    """
    Helper class for broadcasting events to WebSocket clients.

    Use this from other services to push updates.
    """

    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    async def position_update(
        self,
        profile_id: UUID,
        ticket: int,
        current_price: float,
        profit: float,
        swap: float = 0,
    ):
        """Broadcast position price update."""
        from archon_prime.api.websocket.events import PositionUpdateEvent
        from decimal import Decimal

        event = PositionUpdateEvent(
            profile_id=profile_id,
            ticket=ticket,
            current_price=Decimal(str(current_price)),
            profit=Decimal(str(profit)),
            swap=Decimal(str(swap)),
        )
        await self.manager.broadcast_to_profile(profile_id, event)

    async def account_update(
        self,
        profile_id: UUID,
        balance: float,
        equity: float,
        margin: float,
        free_margin: float,
        profit: float,
        margin_level: float = None,
    ):
        """Broadcast account info update."""
        from archon_prime.api.websocket.events import AccountUpdateEvent
        from decimal import Decimal

        event = AccountUpdateEvent(
            profile_id=profile_id,
            balance=Decimal(str(balance)),
            equity=Decimal(str(equity)),
            margin=Decimal(str(margin)),
            free_margin=Decimal(str(free_margin)),
            profit=Decimal(str(profit)),
            margin_level=Decimal(str(margin_level)) if margin_level else None,
        )
        await self.manager.broadcast_to_profile(profile_id, event)

    async def signal_notification(
        self,
        profile_id: UUID,
        signal_id: str,
        symbol: str,
        direction: str,
        confidence: float,
        sources: list,
        decision: str = None,
        reason: str = None,
    ):
        """Broadcast signal gate notification."""
        from archon_prime.api.websocket.events import SignalEvent, EventType
        from decimal import Decimal

        event_type = EventType.SIGNAL_GENERATED
        if decision == "approved":
            event_type = EventType.SIGNAL_APPROVED
        elif decision == "rejected":
            event_type = EventType.SIGNAL_REJECTED

        event = SignalEvent(
            type=event_type,
            profile_id=profile_id,
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            confidence=Decimal(str(confidence)),
            sources=sources,
            decision=decision,
            reason=reason,
        )
        await self.manager.broadcast_to_profile(profile_id, event)

    async def risk_alert(
        self,
        profile_id: UUID,
        severity: str,
        alert_type: str,
        message: str,
        current_value: float = None,
        threshold: float = None,
        action_taken: str = None,
    ):
        """Broadcast risk alert."""
        from archon_prime.api.websocket.events import RiskAlertEvent, Severity
        from decimal import Decimal

        event = RiskAlertEvent(
            profile_id=profile_id,
            severity=Severity(severity),
            alert_type=alert_type,
            message=message,
            current_value=Decimal(str(current_value)) if current_value else None,
            threshold=Decimal(str(threshold)) if threshold else None,
            action_taken=action_taken,
        )
        await self.manager.broadcast_to_profile(profile_id, event)

    async def panic_hedge(
        self,
        profile_id: UUID,
        trigger_reason: str,
        positions_hedged: int,
        hedge_details: dict = None,
    ):
        """Broadcast panic hedge activation."""
        from archon_prime.api.websocket.events import PanicHedgeEvent

        event = PanicHedgeEvent(
            profile_id=profile_id,
            trigger_reason=trigger_reason,
            positions_hedged=positions_hedged,
            hedge_details=hedge_details,
        )
        await self.manager.broadcast_to_profile(profile_id, event)

    async def system_message(
        self,
        profile_id: UUID,
        title: str,
        message: str,
        severity: str = "info",
        action_required: bool = False,
    ):
        """Broadcast system message."""
        from archon_prime.api.websocket.events import SystemMessageEvent, Severity

        event = SystemMessageEvent(
            profile_id=profile_id,
            severity=Severity(severity),
            title=title,
            message=message,
            action_required=action_required,
        )
        await self.manager.broadcast_to_profile(profile_id, event)


# Global broadcaster instance
_broadcaster: Optional[EventBroadcaster] = None


def get_broadcaster() -> EventBroadcaster:
    """Get the global event broadcaster."""
    global _broadcaster
    if _broadcaster is None:
        from archon_prime.api.websocket.manager import get_connection_manager
        _broadcaster = EventBroadcaster(get_connection_manager())
    return _broadcaster
