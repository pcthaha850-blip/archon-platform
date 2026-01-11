"""
WebSocket Routes

WebSocket endpoint for real-time updates.
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.websockets import WebSocketState

from archon_prime.api.auth.jwt import verify_token
from archon_prime.api.websocket.manager import (
    get_connection_manager,
    ClientConnection,
)
from archon_prime.api.websocket.handlers import MessageHandler
from archon_prime.api.websocket.events import (
    EventType,
    ErrorEvent,
    ConnectionEvent,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = None,
) -> Optional[dict]:
    """
    Authenticate WebSocket connection using JWT token.

    Token can be passed as:
    - Query parameter: ?token=xxx
    - First message after connection

    Returns:
        User payload if authenticated, None otherwise
    """
    if token:
        payload = verify_token(token, "access")
        if payload:
            return payload

    return None


@router.websocket("/ws/{profile_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    profile_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time profile updates.

    Authentication:
    - Pass JWT token as query param: /ws/{profile_id}?token=xxx
    - Or send as first message: {"type": "auth", "token": "xxx"}

    Message Types (Client -> Server):
    - ping: Heartbeat
    - subscribe: Subscribe to event types
    - unsubscribe: Unsubscribe from events
    - request_positions: Get current positions
    - request_account: Get account info

    Event Types (Server -> Client):
    - connected: Connection established
    - position_update: Position price/profit changed
    - positions_sync: Full positions list
    - account_update: Account balance/equity changed
    - signal_*: Signal Gate events
    - risk_alert: Risk warnings
    - panic_hedge_triggered: Emergency hedge activated
    - error: Error occurred
    """
    manager = get_connection_manager()
    handler = MessageHandler(manager)
    connection: Optional[ClientConnection] = None

    try:
        # Parse profile_id
        try:
            profile_uuid = uuid.UUID(profile_id)
        except ValueError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Authenticate
        user_payload = await authenticate_websocket(websocket, token)

        if not user_payload:
            # Accept connection to receive auth message
            await websocket.accept()

            try:
                # Wait for auth message (5 second timeout)
                auth_data = await websocket.receive_json()

                if auth_data.get("type") != "auth" or not auth_data.get("token"):
                    await websocket.send_json({
                        "type": "error",
                        "code": "AUTH_REQUIRED",
                        "message": "Authentication required",
                    })
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

                user_payload = verify_token(auth_data["token"], "access")
                if not user_payload:
                    await websocket.send_json({
                        "type": "error",
                        "code": "AUTH_FAILED",
                        "message": "Invalid or expired token",
                    })
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return

            except Exception as e:
                logger.error(f"WebSocket auth error: {e}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Already accepted above, create connection without re-accepting
            client_id = str(uuid.uuid4())
            connection = ClientConnection(
                websocket=websocket,
                user_id=uuid.UUID(user_payload["sub"]),
                profile_id=profile_uuid,
                client_id=client_id,
            )

            # Register with manager manually
            async with manager._lock:
                if profile_uuid not in manager._connections:
                    manager._connections[profile_uuid] = []
                manager._connections[profile_uuid].append(connection)

                user_id = connection.user_id
                if user_id not in manager._user_profiles:
                    manager._user_profiles[user_id] = set()
                manager._user_profiles[user_id].add(profile_uuid)

                manager._clients[client_id] = connection

            # Send connected event
            await connection.send_event(
                ConnectionEvent(
                    type=EventType.CONNECTED,
                    profile_id=profile_uuid,
                    message="Connected to ARCHON PRIME",
                )
            )
        else:
            # Token provided in query, use manager.connect
            client_id = str(uuid.uuid4())
            user_id = uuid.UUID(user_payload["sub"])

            connection = await manager.connect(
                websocket=websocket,
                user_id=user_id,
                profile_id=profile_uuid,
                client_id=client_id,
            )

        # TODO: Verify user has access to this profile
        # This would check the database to ensure the authenticated user
        # owns the profile or is an admin

        logger.info(f"WebSocket connected: {connection.client_id} -> {profile_id}")

        # Main message loop
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle message
                response = await handler.handle_message(connection, message)

                # Send response if any
                if response:
                    await connection.send_json(response)

            except json.JSONDecodeError:
                await connection.send_event(
                    ErrorEvent(
                        type=EventType.ERROR,
                        profile_id=profile_uuid,
                        code="INVALID_JSON",
                        message="Invalid JSON format",
                    )
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {profile_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        # Clean up connection
        if connection:
            await manager.disconnect(connection.client_id)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_connection_manager()
    return manager.get_stats()
