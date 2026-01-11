"""
MT5 Connection Pool

Manages MT5 terminal connections for multiple profiles.
Provides connection pooling, auto-reconnection, and health monitoring.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Callable, Awaitable
from uuid import UUID

from archon_prime.api.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MT5Connection:
    """Represents a single MT5 connection."""

    profile_id: UUID
    login: str
    server: str
    connected: bool = False
    last_heartbeat: Optional[datetime] = None
    reconnect_attempts: int = 0
    error_message: Optional[str] = None

    # Account info cache
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    free_margin: float = 0.0
    margin_level: float = 0.0
    leverage: int = 0
    currency: str = ""


@dataclass
class PoolStats:
    """Connection pool statistics."""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    total_reconnects: int = 0


class MT5ConnectionPool:
    """
    Connection pool for MT5 terminals.

    Features:
    - One connection per MT5 account
    - Automatic reconnection on failure
    - Idle connection cleanup
    - Health monitoring
    - Connection statistics
    """

    def __init__(
        self,
        max_connections: int = None,
        idle_timeout: int = None,
        reconnect_interval: int = None,
    ):
        """
        Initialize connection pool.

        Args:
            max_connections: Maximum concurrent connections
            idle_timeout: Seconds before idle connection is closed
            reconnect_interval: Seconds between reconnection attempts
        """
        self.max_connections = max_connections or settings.MT5_MAX_CONNECTIONS
        self.idle_timeout = idle_timeout or settings.MT5_IDLE_TIMEOUT
        self.reconnect_interval = reconnect_interval or settings.MT5_RECONNECT_INTERVAL

        self._connections: Dict[UUID, MT5Connection] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Callbacks
        self._on_connect: Optional[Callable[[UUID], Awaitable[None]]] = None
        self._on_disconnect: Optional[Callable[[UUID], Awaitable[None]]] = None
        self._on_account_update: Optional[
            Callable[[UUID, MT5Connection], Awaitable[None]]
        ] = None

    async def start(self):
        """Start the connection pool manager."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("MT5 connection pool started")

    async def stop(self):
        """Stop the connection pool and close all connections."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._lock:
            for profile_id in list(self._connections.keys()):
                await self._close_connection(profile_id)

        logger.info("MT5 connection pool stopped")

    async def connect(
        self,
        profile_id: UUID,
        login: str,
        password: str,
        server: str,
    ) -> tuple[bool, str]:
        """
        Connect to MT5 terminal.

        Args:
            profile_id: Profile UUID
            login: MT5 login
            password: MT5 password (decrypted)
            server: MT5 server address

        Returns:
            Tuple of (success, message)
        """
        async with self._lock:
            # Check if already connected
            if profile_id in self._connections:
                conn = self._connections[profile_id]
                if conn.connected:
                    return True, "Already connected"

            # Check pool capacity
            active_count = sum(
                1 for c in self._connections.values() if c.connected
            )
            if active_count >= self.max_connections:
                return False, f"Connection pool full ({self.max_connections})"

            # Create connection
            conn = MT5Connection(
                profile_id=profile_id,
                login=login,
                server=server,
            )

            # TODO: Actual MT5 connection logic
            # This would use the MT5 adapter to establish connection
            # For now, simulate successful connection
            try:
                # Simulate connection
                conn.connected = True
                conn.last_heartbeat = datetime.now(timezone.utc)
                conn.reconnect_attempts = 0
                conn.error_message = None

                # Simulate account info fetch
                conn.balance = 10000.0
                conn.equity = 10000.0
                conn.margin = 0.0
                conn.free_margin = 10000.0
                conn.margin_level = 0.0
                conn.leverage = 100
                conn.currency = "USD"

                self._connections[profile_id] = conn

                logger.info(f"Connected to MT5: {login}@{server}")

                # Notify callback
                if self._on_connect:
                    asyncio.create_task(self._on_connect(profile_id))

                return True, "Connected successfully"

            except Exception as e:
                conn.connected = False
                conn.error_message = str(e)
                self._connections[profile_id] = conn
                logger.error(f"Failed to connect to MT5: {e}")
                return False, str(e)

    async def disconnect(self, profile_id: UUID) -> tuple[bool, str]:
        """
        Disconnect from MT5 terminal.

        Args:
            profile_id: Profile UUID

        Returns:
            Tuple of (success, message)
        """
        async with self._lock:
            if profile_id not in self._connections:
                return True, "Not connected"

            await self._close_connection(profile_id)
            return True, "Disconnected successfully"

    async def _close_connection(self, profile_id: UUID):
        """Close a specific connection (internal)."""
        if profile_id not in self._connections:
            return

        conn = self._connections[profile_id]

        # TODO: Actual MT5 disconnection logic
        conn.connected = False
        del self._connections[profile_id]

        logger.info(f"Disconnected from MT5: {conn.login}@{conn.server}")

        # Notify callback
        if self._on_disconnect:
            asyncio.create_task(self._on_disconnect(profile_id))

    def get_connection(self, profile_id: UUID) -> Optional[MT5Connection]:
        """Get connection for a profile."""
        return self._connections.get(profile_id)

    def is_connected(self, profile_id: UUID) -> bool:
        """Check if profile is connected."""
        conn = self._connections.get(profile_id)
        return conn is not None and conn.connected

    def get_stats(self) -> PoolStats:
        """Get connection pool statistics."""
        connections = list(self._connections.values())
        return PoolStats(
            total_connections=len(connections),
            active_connections=sum(1 for c in connections if c.connected),
            idle_connections=sum(
                1 for c in connections
                if c.connected and c.last_heartbeat
                and (datetime.now(timezone.utc) - c.last_heartbeat).seconds > 60
            ),
            failed_connections=sum(
                1 for c in connections if not c.connected and c.error_message
            ),
            total_reconnects=sum(c.reconnect_attempts for c in connections),
        )

    def get_all_connections(self) -> Dict[UUID, MT5Connection]:
        """Get all connections (for admin monitoring)."""
        return dict(self._connections)

    async def _cleanup_loop(self):
        """Background task for connection cleanup and health checks."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                async with self._lock:
                    now = datetime.now(timezone.utc)

                    for profile_id, conn in list(self._connections.items()):
                        # Check for idle connections
                        if (
                            conn.connected
                            and conn.last_heartbeat
                            and (now - conn.last_heartbeat).seconds > self.idle_timeout
                        ):
                            logger.info(
                                f"Closing idle connection: {conn.login}@{conn.server}"
                            )
                            await self._close_connection(profile_id)

                        # Check for failed connections needing reconnect
                        elif not conn.connected and conn.reconnect_attempts < 5:
                            # TODO: Attempt reconnection
                            pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    # Callback setters
    def on_connect(self, callback: Callable[[UUID], Awaitable[None]]):
        """Set callback for connection events."""
        self._on_connect = callback

    def on_disconnect(self, callback: Callable[[UUID], Awaitable[None]]):
        """Set callback for disconnection events."""
        self._on_disconnect = callback

    def on_account_update(
        self, callback: Callable[[UUID, MT5Connection], Awaitable[None]]
    ):
        """Set callback for account update events."""
        self._on_account_update = callback


# Global pool instance
_pool: Optional[MT5ConnectionPool] = None


def get_mt5_pool() -> MT5ConnectionPool:
    """Get the global MT5 connection pool."""
    global _pool
    if _pool is None:
        _pool = MT5ConnectionPool()
    return _pool


async def init_mt5_pool():
    """Initialize and start the MT5 connection pool."""
    pool = get_mt5_pool()
    await pool.start()


async def close_mt5_pool():
    """Stop and close the MT5 connection pool."""
    global _pool
    if _pool:
        await _pool.stop()
        _pool = None
