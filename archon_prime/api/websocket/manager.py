"""
WebSocket Connection Manager

Manages WebSocket connections for real-time updates.
Handles multiple clients per profile with authentication.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from archon_prime.api.websocket.events import (
    BaseEvent,
    EventType,
    ConnectionEvent,
    ErrorEvent,
    Severity,
)

logger = logging.getLogger(__name__)


class ClientConnection:
    """Represents a single WebSocket client connection."""

    def __init__(
        self,
        websocket: WebSocket,
        user_id: UUID,
        profile_id: UUID,
        client_id: str,
    ):
        self.websocket = websocket
        self.user_id = user_id
        self.profile_id = profile_id
        self.client_id = client_id
        self.connected_at = datetime.now(timezone.utc)
        self.last_ping = datetime.now(timezone.utc)
        self.subscriptions: Set[str] = set()  # Event types to receive

    async def send_event(self, event: BaseEvent) -> bool:
        """Send an event to this client."""
        try:
            await self.websocket.send_json(event.model_dump(mode="json"))
            return True
        except Exception as e:
            logger.error(f"Failed to send to client {self.client_id}: {e}")
            return False

    async def send_json(self, data: dict) -> bool:
        """Send raw JSON data."""
        try:
            await self.websocket.send_json(data)
            return True
        except Exception:
            return False


class ConnectionManager:
    """
    Manages all WebSocket connections.

    Features:
    - Multiple clients per profile
    - User-based access control
    - Event broadcasting
    - Heartbeat monitoring
    - Subscription filtering
    """

    def __init__(self):
        # profile_id -> list of connections
        self._connections: Dict[UUID, List[ClientConnection]] = {}
        # user_id -> set of profile_ids they're connected to
        self._user_profiles: Dict[UUID, Set[UUID]] = {}
        # client_id -> connection (for direct access)
        self._clients: Dict[str, ClientConnection] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start the connection manager."""
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WebSocket connection manager started")

    async def stop(self):
        """Stop the connection manager and close all connections."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._lock:
            for profile_connections in self._connections.values():
                for conn in profile_connections:
                    try:
                        await conn.websocket.close()
                    except Exception:
                        pass
            self._connections.clear()
            self._user_profiles.clear()
            self._clients.clear()

        logger.info("WebSocket connection manager stopped")

    async def connect(
        self,
        websocket: WebSocket,
        user_id: UUID,
        profile_id: UUID,
        client_id: str,
    ) -> ClientConnection:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            user_id: Authenticated user ID
            profile_id: MT5 profile ID
            client_id: Unique client identifier

        Returns:
            ClientConnection instance
        """
        await websocket.accept()

        connection = ClientConnection(
            websocket=websocket,
            user_id=user_id,
            profile_id=profile_id,
            client_id=client_id,
        )

        async with self._lock:
            # Add to profile connections
            if profile_id not in self._connections:
                self._connections[profile_id] = []
            self._connections[profile_id].append(connection)

            # Track user's profiles
            if user_id not in self._user_profiles:
                self._user_profiles[user_id] = set()
            self._user_profiles[user_id].add(profile_id)

            # Add to clients dict
            self._clients[client_id] = connection

        logger.info(f"Client {client_id} connected to profile {profile_id}")

        # Send connected event
        await connection.send_event(
            ConnectionEvent(
                type=EventType.CONNECTED,
                profile_id=profile_id,
                message="Connected to ARCHON PRIME",
            )
        )

        return connection

    async def disconnect(self, client_id: str):
        """Remove a client connection."""
        async with self._lock:
            if client_id not in self._clients:
                return

            connection = self._clients[client_id]
            profile_id = connection.profile_id
            user_id = connection.user_id

            # Remove from profile connections
            if profile_id in self._connections:
                self._connections[profile_id] = [
                    c for c in self._connections[profile_id]
                    if c.client_id != client_id
                ]
                if not self._connections[profile_id]:
                    del self._connections[profile_id]

            # Update user profiles
            if user_id in self._user_profiles:
                # Check if user has other connections to this profile
                has_other = any(
                    c.profile_id == profile_id
                    for c in self._clients.values()
                    if c.user_id == user_id and c.client_id != client_id
                )
                if not has_other:
                    self._user_profiles[user_id].discard(profile_id)
                if not self._user_profiles[user_id]:
                    del self._user_profiles[user_id]

            # Remove from clients
            del self._clients[client_id]

        logger.info(f"Client {client_id} disconnected")

    async def broadcast_to_profile(
        self,
        profile_id: UUID,
        event: BaseEvent,
        exclude_client: Optional[str] = None,
    ):
        """
        Broadcast an event to all clients connected to a profile.

        Args:
            profile_id: Target profile ID
            event: Event to broadcast
            exclude_client: Optional client ID to exclude
        """
        async with self._lock:
            connections = self._connections.get(profile_id, [])

        failed_clients = []
        for conn in connections:
            if exclude_client and conn.client_id == exclude_client:
                continue

            success = await conn.send_event(event)
            if not success:
                failed_clients.append(conn.client_id)

        # Clean up failed connections
        for client_id in failed_clients:
            await self.disconnect(client_id)

    async def broadcast_to_user(self, user_id: UUID, event: BaseEvent):
        """Broadcast an event to all connections for a user."""
        async with self._lock:
            profile_ids = self._user_profiles.get(user_id, set())

        for profile_id in profile_ids:
            await self.broadcast_to_profile(profile_id, event)

    async def broadcast_to_all(self, event: BaseEvent):
        """Broadcast an event to all connected clients."""
        async with self._lock:
            all_clients = list(self._clients.values())

        failed_clients = []
        for conn in all_clients:
            success = await conn.send_event(event)
            if not success:
                failed_clients.append(conn.client_id)

        for client_id in failed_clients:
            await self.disconnect(client_id)

    async def send_to_client(self, client_id: str, event: BaseEvent) -> bool:
        """Send an event to a specific client."""
        async with self._lock:
            connection = self._clients.get(client_id)

        if not connection:
            return False

        return await connection.send_event(event)

    def get_profile_client_count(self, profile_id: UUID) -> int:
        """Get number of clients connected to a profile."""
        return len(self._connections.get(profile_id, []))

    def get_total_connections(self) -> int:
        """Get total number of active connections."""
        return len(self._clients)

    def get_stats(self) -> dict:
        """Get connection statistics."""
        return {
            "total_connections": len(self._clients),
            "active_profiles": len(self._connections),
            "active_users": len(self._user_profiles),
            "connections_per_profile": {
                str(pid): len(conns)
                for pid, conns in self._connections.items()
            },
        }

    async def _heartbeat_loop(self):
        """Background task to check connection health."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                async with self._lock:
                    all_clients = list(self._clients.items())

                now = datetime.now(timezone.utc)
                stale_clients = []

                for client_id, conn in all_clients:
                    # Check if connection is stale (no ping in 2 minutes)
                    if (now - conn.last_ping).seconds > 120:
                        stale_clients.append(client_id)
                    else:
                        # Send ping
                        try:
                            await conn.websocket.send_json({
                                "type": "ping",
                                "timestamp": now.isoformat(),
                            })
                        except Exception:
                            stale_clients.append(client_id)

                # Disconnect stale clients
                for client_id in stale_clients:
                    logger.info(f"Disconnecting stale client: {client_id}")
                    await self.disconnect(client_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")


# Global connection manager instance
_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


async def init_websocket_manager():
    """Initialize and start the WebSocket manager."""
    manager = get_connection_manager()
    await manager.start()


async def close_websocket_manager():
    """Stop and clean up the WebSocket manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
