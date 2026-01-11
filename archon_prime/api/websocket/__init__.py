"""WebSocket module for real-time updates."""

from archon_prime.api.websocket.routes import router
from archon_prime.api.websocket.manager import ConnectionManager, get_connection_manager

__all__ = ["router", "ConnectionManager", "get_connection_manager"]
