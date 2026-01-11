"""
Background Sync Workers

State integrity workers that continuously answer:
"Is reality still what we think it is?"

Responsibilities:
1. Position reconciliation against MT5
2. Drift detection and correction
3. Recovery after partial failure
4. State healing after disconnects

These workers are boring, relentless, and invisible.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set
from uuid import UUID

logger = logging.getLogger(__name__)


class ReconciliationResult(str, Enum):
    """Result of reconciliation check."""
    MATCHED = "matched"
    DRIFT_DETECTED = "drift_detected"
    MISSING_LOCAL = "missing_local"    # Position exists in MT5 but not locally
    MISSING_REMOTE = "missing_remote"  # Position exists locally but not in MT5
    STALE_DATA = "stale_data"          # Local data is outdated


@dataclass
class DriftRecord:
    """Record of detected drift."""
    profile_id: UUID
    ticket: int
    field: str
    local_value: str
    remote_value: str
    detected_at: datetime
    corrected: bool = False
    corrected_at: Optional[datetime] = None


@dataclass
class ReconciliationReport:
    """Report from a reconciliation run."""
    profile_id: UUID
    timestamp: datetime
    positions_checked: int
    matched: int
    drifts: List[DriftRecord] = field(default_factory=list)
    missing_local: List[int] = field(default_factory=list)   # Tickets
    missing_remote: List[int] = field(default_factory=list)  # Tickets
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class WorkerStats:
    """Statistics for a background worker."""
    name: str
    started_at: datetime
    last_run_at: Optional[datetime] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None


class PositionReconciliationWorker:
    """
    Reconciles local position state against MT5.

    Detects and corrects drift between local database and broker.
    """

    def __init__(
        self,
        interval_seconds: int = 30,
        max_drift_age_seconds: int = 60,
    ):
        self.interval = interval_seconds
        self.max_drift_age = max_drift_age_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = WorkerStats(
            name="position_reconciliation",
            started_at=datetime.now(timezone.utc),
        )

        # Track recent drifts
        self._drift_history: Dict[UUID, List[DriftRecord]] = {}

    async def start(self) -> None:
        """Start the reconciliation worker."""
        if self._running:
            return

        self._running = True
        self._stats.started_at = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Position reconciliation worker started")

    async def stop(self) -> None:
        """Stop the reconciliation worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Position reconciliation worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._reconcile_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")
                self._stats.error_count += 1
                self._stats.last_error = str(e)

    async def _reconcile_all(self) -> None:
        """Reconcile all connected profiles."""
        from archon_prime.api.services.mt5_pool import get_mt5_pool

        pool = get_mt5_pool()
        connections = pool.get_all_connections()

        for profile_id, connection in connections.items():
            if connection.connected:
                try:
                    await self._reconcile_profile(profile_id)
                except Exception as e:
                    logger.error(f"Reconciliation failed for {profile_id}: {e}")

        self._stats.run_count += 1
        self._stats.last_run_at = datetime.now(timezone.utc)

    async def _reconcile_profile(self, profile_id: UUID) -> ReconciliationReport:
        """Reconcile a single profile."""
        import time
        start = time.monotonic()

        report = ReconciliationReport(
            profile_id=profile_id,
            timestamp=datetime.now(timezone.utc),
            positions_checked=0,
            matched=0,
        )

        # TODO: Actual reconciliation logic
        # 1. Get positions from MT5 via connection pool
        # 2. Get positions from local database
        # 3. Compare and detect drift
        # 4. Correct drift or log for manual review
        # 5. Handle missing positions

        # Placeholder - in production this would:
        # - Query MT5 for current positions
        # - Compare against Position table
        # - Update stale data
        # - Create alerts for discrepancies

        report.duration_ms = int((time.monotonic() - start) * 1000)
        return report

    def get_stats(self) -> WorkerStats:
        """Get worker statistics."""
        return self._stats

    def get_drift_history(self, profile_id: UUID) -> List[DriftRecord]:
        """Get drift history for a profile."""
        return self._drift_history.get(profile_id, [])


class AccountSyncWorker:
    """
    Syncs account information from MT5.

    Updates balance, equity, margin for connected profiles.
    """

    def __init__(self, interval_seconds: int = 10):
        self.interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = WorkerStats(
            name="account_sync",
            started_at=datetime.now(timezone.utc),
        )

    async def start(self) -> None:
        """Start the account sync worker."""
        if self._running:
            return

        self._running = True
        self._stats.started_at = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Account sync worker started")

    async def stop(self) -> None:
        """Stop the account sync worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Account sync worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._sync_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Account sync error: {e}")
                self._stats.error_count += 1
                self._stats.last_error = str(e)

    async def _sync_all(self) -> None:
        """Sync all connected accounts."""
        from archon_prime.api.services.mt5_pool import get_mt5_pool
        from archon_prime.api.websocket.handlers import get_broadcaster

        pool = get_mt5_pool()
        broadcaster = get_broadcaster()
        connections = pool.get_all_connections()

        for profile_id, connection in connections.items():
            if connection.connected:
                try:
                    # Broadcast account update via WebSocket
                    await broadcaster.account_update(
                        profile_id=profile_id,
                        balance=connection.balance,
                        equity=connection.equity,
                        margin=connection.margin,
                        free_margin=connection.free_margin,
                        profit=connection.equity - connection.balance,
                        margin_level=connection.margin_level,
                    )
                except Exception as e:
                    logger.error(f"Account sync failed for {profile_id}: {e}")

        self._stats.run_count += 1
        self._stats.last_run_at = datetime.now(timezone.utc)

    def get_stats(self) -> WorkerStats:
        """Get worker statistics."""
        return self._stats


class ConnectionHealthWorker:
    """
    Monitors connection health and handles recovery.

    Detects disconnections and attempts reconnection.
    """

    def __init__(
        self,
        interval_seconds: int = 15,
        max_reconnect_attempts: int = 5,
    ):
        self.interval = interval_seconds
        self.max_reconnect_attempts = max_reconnect_attempts
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = WorkerStats(
            name="connection_health",
            started_at=datetime.now(timezone.utc),
        )

        # Track reconnection attempts
        self._reconnect_attempts: Dict[UUID, int] = {}

    async def start(self) -> None:
        """Start the connection health worker."""
        if self._running:
            return

        self._running = True
        self._stats.started_at = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Connection health worker started")

    async def stop(self) -> None:
        """Stop the connection health worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Connection health worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._check_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                self._stats.error_count += 1
                self._stats.last_error = str(e)

    async def _check_health(self) -> None:
        """Check health of all connections."""
        from archon_prime.api.services.mt5_pool import get_mt5_pool

        pool = get_mt5_pool()
        stats = pool.get_stats()

        # Log connection stats
        if stats.failed_connections > 0:
            logger.warning(
                f"Connection health: {stats.active_connections} active, "
                f"{stats.failed_connections} failed"
            )

        # TODO: Implement reconnection logic
        # 1. Detect failed connections
        # 2. Attempt reconnection with backoff
        # 3. Alert after max attempts

        self._stats.run_count += 1
        self._stats.last_run_at = datetime.now(timezone.utc)

    def get_stats(self) -> WorkerStats:
        """Get worker statistics."""
        return self._stats


class SignalExpirationWorker:
    """
    Expires stale signals.

    Marks approved signals as expired if not executed in time.
    """

    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = WorkerStats(
            name="signal_expiration",
            started_at=datetime.now(timezone.utc),
        )

    async def start(self) -> None:
        """Start the signal expiration worker."""
        if self._running:
            return

        self._running = True
        self._stats.started_at = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Signal expiration worker started")

    async def stop(self) -> None:
        """Stop the signal expiration worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Signal expiration worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._expire_stale_signals()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Signal expiration error: {e}")
                self._stats.error_count += 1
                self._stats.last_error = str(e)

    async def _expire_stale_signals(self) -> None:
        """Expire signals past their valid_until time."""
        # TODO: Query signal store and expire old approved signals
        # For now, just update stats
        self._stats.run_count += 1
        self._stats.last_run_at = datetime.now(timezone.utc)

    def get_stats(self) -> WorkerStats:
        """Get worker statistics."""
        return self._stats


class BackgroundWorkerManager:
    """
    Manages all background workers.

    Provides unified start/stop and status monitoring.
    """

    def __init__(self):
        self.reconciliation = PositionReconciliationWorker()
        self.account_sync = AccountSyncWorker()
        self.connection_health = ConnectionHealthWorker()
        self.signal_expiration = SignalExpirationWorker()

        self._started = False

    async def start_all(self) -> None:
        """Start all background workers."""
        if self._started:
            return

        await self.reconciliation.start()
        await self.account_sync.start()
        await self.connection_health.start()
        await self.signal_expiration.start()

        self._started = True
        logger.info("All background workers started")

    async def stop_all(self) -> None:
        """Stop all background workers."""
        await self.reconciliation.stop()
        await self.account_sync.stop()
        await self.connection_health.stop()
        await self.signal_expiration.stop()

        self._started = False
        logger.info("All background workers stopped")

    def get_all_stats(self) -> Dict[str, WorkerStats]:
        """Get statistics for all workers."""
        return {
            "reconciliation": self.reconciliation.get_stats(),
            "account_sync": self.account_sync.get_stats(),
            "connection_health": self.connection_health.get_stats(),
            "signal_expiration": self.signal_expiration.get_stats(),
        }


# Global worker manager
_worker_manager: Optional[BackgroundWorkerManager] = None


def get_worker_manager() -> BackgroundWorkerManager:
    """Get the global worker manager."""
    global _worker_manager
    if _worker_manager is None:
        _worker_manager = BackgroundWorkerManager()
    return _worker_manager


async def init_background_workers() -> None:
    """Initialize and start all background workers."""
    manager = get_worker_manager()
    await manager.start_all()


async def close_background_workers() -> None:
    """Stop all background workers."""
    global _worker_manager
    if _worker_manager:
        await _worker_manager.stop_all()
        _worker_manager = None
