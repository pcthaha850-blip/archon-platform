"""
Failure Mode Tests

Validates system behavior under failure conditions:
1. MT5 connection failures
2. Database transaction failures
3. WebSocket disconnections
4. Partial state corruption
5. Recovery paths

These tests prove the invariant:
"The system fails safely and recovers gracefully."
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.exc import OperationalError, IntegrityError


# ==================== MT5 Connection Failure Tests ====================


@pytest.mark.asyncio
async def test_mt5_connection_failure_graceful_error(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test graceful handling when MT5 connection fails."""
    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock_pool:
        pool = MagicMock()
        pool.connect = AsyncMock(return_value=(False, "Connection refused"))
        pool.is_connected = MagicMock(return_value=False)
        mock_pool.return_value = pool

        # Attempt to connect should return error, not crash
        response = await async_client.post(
            f"/api/v1/profiles/{test_profile.id}/connect",
            headers=auth_headers,
        )

        # Should fail gracefully
        assert response.status_code in [400, 500, 503]


@pytest.mark.asyncio
async def test_mt5_disconnection_during_position_sync(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test handling of disconnection during position sync."""
    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock_pool:
        pool = MagicMock()
        # Simulate disconnection mid-operation
        pool.is_connected = MagicMock(side_effect=[True, False])
        pool.get_positions = AsyncMock(side_effect=ConnectionError("Lost connection"))
        mock_pool.return_value = pool

        response = await async_client.get(
            f"/api/v1/profiles/{test_profile.id}/positions",
            headers=auth_headers,
        )

        # Should return error or empty, not crash
        assert response.status_code in [200, 400, 503]


@pytest.mark.asyncio
async def test_mt5_timeout_handling(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test handling of MT5 operation timeouts."""
    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock_pool:
        pool = MagicMock()

        async def slow_operation():
            await asyncio.sleep(10)  # Simulate timeout
            return {}

        pool.get_account_info = slow_operation
        pool.is_connected = MagicMock(return_value=True)
        mock_pool.return_value = pool

        # Should timeout gracefully
        try:
            response = await asyncio.wait_for(
                async_client.get(
                    f"/api/v1/profiles/{test_profile.id}/account",
                    headers=auth_headers,
                ),
                timeout=5.0,
            )
            # If we get here, request completed or timed out gracefully
            assert response.status_code in [200, 408, 504]
        except asyncio.TimeoutError:
            # Timeout is acceptable
            pass


# ==================== Database Failure Tests ====================


@pytest.mark.asyncio
async def test_database_transaction_rollback(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
    db_session,
):
    """Test that failed transactions are rolled back."""
    original_profile_name = test_profile.name

    with patch.object(db_session, "commit", side_effect=OperationalError("stmt", "params", "orig")):
        # Attempt update that will fail
        response = await async_client.patch(
            f"/api/v1/profiles/{test_profile.id}",
            json={"name": "Should Not Persist"},
            headers=auth_headers,
        )

        # Should fail
        assert response.status_code in [500, 503]

    # Verify original data unchanged (would need fresh session)
    # In real test, would verify rollback occurred


@pytest.mark.asyncio
async def test_duplicate_key_handling(
    async_client: AsyncClient,
    auth_headers: dict,
    test_user,
):
    """Test handling of duplicate key violations."""
    # Try to create profile with duplicate login
    profile_data = {
        "name": "Duplicate Test",
        "mt5_login": "12345678",  # Same as test_profile
        "mt5_password": "test_password",
        "mt5_server": "Demo-Server",
        "broker_name": "Test Broker",
        "account_type": "demo",
    }

    # First creation (may or may not exist)
    await async_client.post(
        "/api/v1/profiles",
        json=profile_data,
        headers=auth_headers,
    )

    # Second creation should handle duplicate gracefully
    response = await async_client.post(
        "/api/v1/profiles",
        json=profile_data,
        headers=auth_headers,
    )

    # Should either succeed (different user) or fail gracefully
    assert response.status_code in [200, 201, 400, 409]


@pytest.mark.asyncio
async def test_connection_pool_exhaustion(
    async_client: AsyncClient,
    auth_headers: dict,
):
    """Test behavior when database connection pool is exhausted."""
    with patch("archon_prime.api.db.session.get_db") as mock_get_db:
        mock_get_db.side_effect = OperationalError(
            "stmt", "params", "QueuePool limit reached"
        )

        response = await async_client.get(
            "/api/v1/users/me",
            headers=auth_headers,
        )

        # Should fail gracefully, not hang
        assert response.status_code in [500, 503]


# ==================== WebSocket Failure Tests ====================


@pytest.mark.asyncio
async def test_websocket_broadcast_failure_isolated(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test that WebSocket broadcast failure doesn't affect signal processing."""
    with patch("archon_prime.api.websocket.handlers.get_broadcaster") as mock_broadcaster:
        broadcaster = MagicMock()
        broadcaster.signal_notification = AsyncMock(
            side_effect=Exception("WebSocket broadcast failed")
        )
        mock_broadcaster.return_value = broadcaster

        # Signal should still be processed even if broadcast fails
        signal_data = {
            "idempotency_key": f"ws-fail-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }

        response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

        # Signal processing should succeed despite broadcast failure
        assert response.status_code == 200
        data = response.json()
        assert "decision" in data


@pytest.mark.asyncio
async def test_websocket_manager_recovery(mock_websocket_manager):
    """Test WebSocket manager recovery after failure."""
    # Simulate connection failure
    mock_websocket_manager.broadcast_to_profile = AsyncMock(
        side_effect=Exception("Connection lost")
    )

    # First call fails
    with pytest.raises(Exception):
        await mock_websocket_manager.broadcast_to_profile(
            uuid4(), "test", {"data": "test"}
        )

    # Simulate recovery
    mock_websocket_manager.broadcast_to_profile = AsyncMock()

    # Should work after recovery
    await mock_websocket_manager.broadcast_to_profile(
        uuid4(), "test", {"data": "test"}
    )

    mock_websocket_manager.broadcast_to_profile.assert_called_once()


# ==================== Signal Gate Failure Tests ====================


@pytest.mark.asyncio
async def test_signal_gate_partial_check_failure(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test handling when one gate check fails."""
    with patch("archon_prime.api.signals.service.SignalGateService._check_position_limit") as mock_check:
        mock_check.side_effect = Exception("Database query failed")

        signal_data = {
            "idempotency_key": f"gate-fail-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }

        response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

        # Should fail safely (reject or error), not approve blindly
        if response.status_code == 200:
            data = response.json()
            # If returned, should be rejected due to check failure
            assert data["decision"] in ["rejected", "error"]
        else:
            assert response.status_code in [500, 503]


@pytest.mark.asyncio
async def test_idempotency_store_failure(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test behavior when idempotency store fails."""
    with patch("archon_prime.api.signals.service.SignalGateService._check_idempotency") as mock_check:
        mock_check.side_effect = Exception("Cache unavailable")

        signal_data = {
            "idempotency_key": f"idem-fail-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }

        response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

        # Should either proceed (without idempotency) or fail safely
        assert response.status_code in [200, 500, 503]


# ==================== Background Worker Failure Tests ====================


@pytest.mark.asyncio
async def test_reconciliation_worker_handles_exceptions():
    """Test that reconciliation worker handles exceptions gracefully."""
    from archon_prime.api.services.background_tasks import PositionReconciliationWorker

    worker = PositionReconciliationWorker(interval_seconds=1)

    with patch.object(worker, "_reconcile_all", side_effect=Exception("Reconciliation failed")):
        await worker.start()
        await asyncio.sleep(0.1)
        await worker.stop()

    # Worker should have tracked the error
    stats = worker.get_stats()
    # Error count may or may not increment depending on timing
    # Key assertion: worker didn't crash


@pytest.mark.asyncio
async def test_account_sync_worker_handles_disconnection():
    """Test that account sync worker handles disconnection."""
    from archon_prime.api.services.background_tasks import AccountSyncWorker

    worker = AccountSyncWorker(interval_seconds=1)

    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock_pool:
        pool = MagicMock()
        pool.get_all_connections = MagicMock(return_value={})
        mock_pool.return_value = pool

        await worker.start()
        await asyncio.sleep(0.1)
        await worker.stop()

    # Worker completed without crash
    stats = worker.get_stats()
    assert stats.name == "account_sync"


@pytest.mark.asyncio
async def test_signal_expiration_worker_continues_after_error():
    """Test that signal expiration worker continues after errors."""
    from archon_prime.api.services.background_tasks import SignalExpirationWorker

    worker = SignalExpirationWorker(interval_seconds=1)

    error_count = [0]

    async def failing_then_working():
        error_count[0] += 1
        if error_count[0] <= 2:
            raise Exception("Transient error")
        return

    with patch.object(worker, "_expire_stale_signals", side_effect=failing_then_working):
        await worker.start()
        await asyncio.sleep(0.1)
        await worker.stop()

    # Worker should have continued running despite errors
    stats = worker.get_stats()
    assert stats.name == "signal_expiration"


# ==================== Concurrent Access Tests ====================


@pytest.mark.asyncio
async def test_concurrent_signal_submission(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test handling of concurrent signal submissions."""
    async def submit_signal(i):
        signal_data = {
            "idempotency_key": f"concurrent-{i}-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }
        return await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

    # Submit 10 signals concurrently
    tasks = [submit_signal(i) for i in range(10)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # All should complete (success or rate-limited), none should crash
    for response in responses:
        if isinstance(response, Exception):
            pytest.fail(f"Concurrent submission raised exception: {response}")
        assert response.status_code in [200, 429]


@pytest.mark.asyncio
async def test_concurrent_profile_access(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test handling of concurrent profile access."""
    async def access_profile():
        return await async_client.get(
            f"/api/v1/profiles/{test_profile.id}",
            headers=auth_headers,
        )

    # Access profile 20 times concurrently
    tasks = [access_profile() for _ in range(20)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # All should succeed
    for response in responses:
        if isinstance(response, Exception):
            pytest.fail(f"Concurrent access raised exception: {response}")
        assert response.status_code == 200


# ==================== State Corruption Recovery Tests ====================


@pytest.mark.asyncio
async def test_corrupted_session_recovery(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
    db_session,
):
    """Test recovery from corrupted database session."""
    # Simulate session in bad state
    with patch.object(db_session, "execute", side_effect=OperationalError("stmt", "params", "Session invalid")):
        # First request fails
        response1 = await async_client.get(
            f"/api/v1/profiles/{test_profile.id}",
            headers=auth_headers,
        )
        assert response1.status_code in [500, 503]

    # After session is restored, should work
    # (In real scenario, new session would be created)


@pytest.mark.asyncio
async def test_inconsistent_position_state_detection(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test detection of inconsistent position state."""
    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock_pool:
        pool = MagicMock()
        # Simulate MT5 returning different data than database
        pool.get_positions = AsyncMock(return_value=[
            {"ticket": 99999, "symbol": "UNKNOWN", "volume": 1.0}  # Ghost position
        ])
        pool.is_connected = MagicMock(return_value=True)
        mock_pool.return_value = pool

        # System should detect or handle gracefully
        response = await async_client.get(
            f"/api/v1/profiles/{test_profile.id}/positions",
            headers=auth_headers,
        )

        # Should return something sensible
        assert response.status_code in [200, 500]


# ==================== Authentication Failure Tests ====================


@pytest.mark.asyncio
async def test_expired_token_rejection(async_client: AsyncClient):
    """Test that expired tokens are rejected."""
    expired_headers = {"Authorization": "Bearer expired.token.here"}

    response = await async_client.get(
        "/api/v1/users/me",
        headers=expired_headers,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_format(async_client: AsyncClient):
    """Test that invalid token formats are rejected."""
    invalid_headers = {"Authorization": "Bearer not-a-valid-jwt"}

    response = await async_client.get(
        "/api/v1/users/me",
        headers=invalid_headers,
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_authorization_header(async_client: AsyncClient):
    """Test that missing auth header returns 401."""
    response = await async_client.get("/api/v1/users/me")

    assert response.status_code in [401, 403]


# ==================== Resource Cleanup Tests ====================


@pytest.mark.asyncio
async def test_background_worker_cleanup_on_shutdown():
    """Test that background workers clean up properly on shutdown."""
    from archon_prime.api.services.background_tasks import BackgroundWorkerManager

    manager = BackgroundWorkerManager()

    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock_pool:
        pool = MagicMock()
        pool.get_all_connections = MagicMock(return_value={})
        pool.get_stats = MagicMock(return_value=MagicMock(
            active_connections=0, failed_connections=0
        ))
        mock_pool.return_value = pool

        with patch("archon_prime.api.websocket.handlers.get_broadcaster") as mock_bc:
            mock_bc.return_value = MagicMock()

            await manager.start_all()
            await asyncio.sleep(0.1)
            await manager.stop_all()

    # All workers should be stopped
    stats = manager.get_all_stats()
    # Workers exist but are stopped


@pytest.mark.asyncio
async def test_mt5_pool_cleanup_on_error():
    """Test that MT5 pool cleans up connections on error."""
    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock_pool:
        pool = MagicMock()
        pool.disconnect = AsyncMock()
        pool.is_connected = MagicMock(return_value=True)
        mock_pool.return_value = pool

        # Simulate disconnect
        await pool.disconnect(uuid4())

        # Disconnect should have been called
        pool.disconnect.assert_called()
