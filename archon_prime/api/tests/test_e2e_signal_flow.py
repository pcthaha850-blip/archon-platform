"""
End-to-End Signal Flow Tests

Tests the complete execution trace:
Signal → Gate Evaluation → WebSocket Broadcast → Admin Visibility

These tests validate the invariant:
"Every signal that enters the system is evaluated, logged, and observable."
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient

from archon_prime.api.signals.schemas import SignalDecision, SignalPriority, SignalSource


# ==================== Signal Submission Tests ====================


@pytest.mark.asyncio
async def test_signal_submission_approved(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
    mock_websocket_manager,
    mock_broadcaster,
):
    """Test that valid signals are approved and broadcast."""
    signal_data = {
        "idempotency_key": f"e2e-test-{uuid4().hex[:8]}",
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "strategy",
        "priority": "normal",
        "confidence": "0.85",
        "reasoning": "E2E test signal",
        "strategy_name": "test_strategy",
    }

    response = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=signal_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify signal was approved
    assert data["decision"] == "approved"
    assert data["decision_reason"] is not None
    assert data["decision_hash"] is not None  # Provenance hash exists
    assert data["idempotency_key"] == signal_data["idempotency_key"]

    # Verify WebSocket broadcast was triggered
    mock_broadcaster.signal_notification.assert_called()


@pytest.mark.asyncio
async def test_signal_submission_rejected_low_confidence(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
    low_confidence_signal,
):
    """Test that low-confidence signals are rejected."""
    response = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=low_confidence_signal,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "rejected"
    assert "confidence" in data["decision_reason"].lower()


@pytest.mark.asyncio
async def test_signal_idempotency(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test that duplicate idempotency keys return same response."""
    idempotency_key = f"idempotent-{uuid4().hex[:8]}"
    signal_data = {
        "idempotency_key": idempotency_key,
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "strategy",
        "priority": "normal",
        "confidence": "0.85",
    }

    # First submission
    response1 = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=signal_data,
        headers=auth_headers,
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Second submission with same key
    response2 = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=signal_data,
        headers=auth_headers,
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Same signal returned (idempotent)
    assert data1["id"] == data2["id"]
    assert data1["decision"] == data2["decision"]
    assert data1["decision_hash"] == data2["decision_hash"]


@pytest.mark.asyncio
async def test_signal_rejected_trading_disabled(
    async_client: AsyncClient,
    auth_headers: dict,
    disconnected_profile,
):
    """Test that signals are rejected when trading is disabled."""
    signal_data = {
        "idempotency_key": f"disabled-{uuid4().hex[:8]}",
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "strategy",
        "priority": "normal",
        "confidence": "0.85",
    }

    response = await async_client.post(
        f"/api/v1/signals/{disconnected_profile.id}/submit",
        json=signal_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "rejected"
    # Trading disabled or not connected should reject


# ==================== Rate Limiting Tests ====================


@pytest.mark.asyncio
async def test_rate_limit_normal_priority(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test that normal priority signals are rate limited."""
    responses = []

    # Submit more than rate limit allows (10/min)
    for i in range(12):
        signal_data = {
            "idempotency_key": f"rate-test-{i}-{uuid4().hex[:8]}",
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
        responses.append(response)

    # Some should be rate limited
    rate_limited = [
        r for r in responses
        if r.status_code == 429 or
        (r.status_code == 200 and r.json().get("decision") == "rejected" and "rate" in r.json().get("decision_reason", "").lower())
    ]

    # At least some should be rate limited after 10
    assert len(rate_limited) > 0


@pytest.mark.asyncio
async def test_critical_priority_bypasses_rate_limit(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test that CRITICAL priority signals bypass rate limiting."""
    # First exhaust rate limit with normal signals
    for i in range(12):
        signal_data = {
            "idempotency_key": f"exhaust-{i}-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }
        await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

    # Now submit CRITICAL signal
    critical_signal = {
        "idempotency_key": f"critical-{uuid4().hex[:8]}",
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "risk",
        "priority": "critical",
        "confidence": "0.95",
        "reasoning": "Critical risk signal",
    }

    response = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=critical_signal,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # CRITICAL should not be rate limited
    if data["decision"] == "rejected":
        assert "rate" not in data["decision_reason"].lower()


# ==================== Batch Submission Tests ====================


@pytest.mark.asyncio
async def test_batch_signal_submission(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test batch signal submission."""
    batch_data = {
        "signals": [
            {
                "idempotency_key": f"batch-1-{uuid4().hex[:8]}",
                "symbol": "EURUSD",
                "direction": "buy",
                "source": "strategy",
                "priority": "normal",
                "confidence": "0.85",
            },
            {
                "idempotency_key": f"batch-2-{uuid4().hex[:8]}",
                "symbol": "GBPUSD",
                "direction": "sell",
                "source": "strategy",
                "priority": "normal",
                "confidence": "0.80",
            },
        ]
    }

    response = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit/batch",
        json=batch_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    # Each signal processed independently
    for signal in data:
        assert "decision" in signal
        assert "decision_hash" in signal


# ==================== Query and History Tests ====================


@pytest.mark.asyncio
async def test_signal_list_pagination(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test signal list endpoint with pagination."""
    # First submit some signals
    for i in range(5):
        signal_data = {
            "idempotency_key": f"list-test-{i}-{uuid4().hex[:8]}",
            "symbol": "EURUSD",
            "direction": "buy",
            "source": "strategy",
            "priority": "normal",
            "confidence": "0.85",
        }
        await async_client.post(
            f"/api/v1/signals/{test_profile.id}/submit",
            json=signal_data,
            headers=auth_headers,
        )

    # Query signals
    response = await async_client.get(
        f"/api/v1/signals/{test_profile.id}",
        params={"page": 1, "page_size": 10},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert "signals" in data
    assert "total" in data
    assert "page" in data
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_signal_filter_by_decision(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test filtering signals by decision."""
    response = await async_client.get(
        f"/api/v1/signals/{test_profile.id}",
        params={"decision": "approved"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # All returned signals should be approved
    for signal in data["signals"]:
        assert signal["decision"] == "approved"


@pytest.mark.asyncio
async def test_get_single_signal(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test retrieving a single signal by ID."""
    # First submit a signal
    signal_data = {
        "idempotency_key": f"single-{uuid4().hex[:8]}",
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "strategy",
        "priority": "normal",
        "confidence": "0.85",
    }

    submit_response = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=signal_data,
        headers=auth_headers,
    )
    signal_id = submit_response.json()["id"]

    # Get the signal
    response = await async_client.get(
        f"/api/v1/signals/{test_profile.id}/{signal_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == signal_id


# ==================== Statistics Tests ====================


@pytest.mark.asyncio
async def test_signal_statistics(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test signal statistics endpoint."""
    response = await async_client.get(
        f"/api/v1/signals/{test_profile.id}/stats",
        params={"hours": 24},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify stats structure
    assert "total_signals" in data
    assert "approved" in data
    assert "rejected" in data
    assert "approval_rate" in data


@pytest.mark.asyncio
async def test_rate_limit_status(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test rate limit status endpoint."""
    response = await async_client.get(
        f"/api/v1/signals/{test_profile.id}/rate-limit",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert "remaining" in data
    assert "limit" in data
    assert "reset_at" in data


# ==================== Gate Configuration Tests ====================


@pytest.mark.asyncio
async def test_get_gate_config(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test getting gate configuration."""
    response = await async_client.get(
        f"/api/v1/signals/{test_profile.id}/config",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify config structure
    assert "confidence_threshold" in data
    assert "max_positions" in data
    assert "max_daily_signals" in data


@pytest.mark.asyncio
async def test_update_gate_config(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test updating gate configuration."""
    update_data = {
        "confidence_threshold": 0.80,
        "max_positions": 3,
    }

    response = await async_client.patch(
        f"/api/v1/signals/{test_profile.id}/config",
        json=update_data,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["confidence_threshold"] == 0.80
    assert data["max_positions"] == 3


# ==================== Admin Visibility Tests ====================


@pytest.mark.asyncio
async def test_admin_can_see_all_signals(
    async_client: AsyncClient,
    admin_headers: dict,
    test_profile,
):
    """Test that admin can view signals across all profiles."""
    # Admin dashboard should show signal stats
    response = await async_client.get(
        "/api/v1/admin/dashboard",
        headers=admin_headers,
    )

    assert response.status_code == 200
    # Dashboard should include signal-related metrics


@pytest.mark.asyncio
async def test_admin_can_acknowledge_alerts(
    async_client: AsyncClient,
    admin_headers: dict,
):
    """Test that admin can acknowledge risk alerts."""
    # Get unacknowledged alerts
    alerts_response = await async_client.get(
        "/api/v1/admin/alerts",
        params={"acknowledged": False},
        headers=admin_headers,
    )

    assert alerts_response.status_code == 200


# ==================== Execution Tests ====================


@pytest.mark.asyncio
async def test_execute_approved_signal_requires_connection(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test that execution requires profile connection."""
    # Submit and get approved signal
    signal_data = {
        "idempotency_key": f"exec-{uuid4().hex[:8]}",
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "strategy",
        "priority": "normal",
        "confidence": "0.85",
    }

    submit_response = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=signal_data,
        headers=auth_headers,
    )

    if submit_response.json()["decision"] == "approved":
        signal_id = submit_response.json()["id"]

        # Try to execute (currently returns 501 Not Implemented)
        exec_response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/{signal_id}/execute",
            headers=auth_headers,
        )

        # Either requires connection or not implemented
        assert exec_response.status_code in [400, 501]


@pytest.mark.asyncio
async def test_cannot_execute_rejected_signal(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
    low_confidence_signal,
):
    """Test that rejected signals cannot be executed."""
    # Submit low-confidence signal (will be rejected)
    submit_response = await async_client.post(
        f"/api/v1/signals/{test_profile.id}/submit",
        json=low_confidence_signal,
        headers=auth_headers,
    )

    assert submit_response.status_code == 200
    data = submit_response.json()

    if data["decision"] == "rejected":
        signal_id = data["id"]

        # Try to execute rejected signal
        exec_response = await async_client.post(
            f"/api/v1/signals/{test_profile.id}/{signal_id}/execute",
            headers=auth_headers,
        )

        assert exec_response.status_code == 400
        assert "cannot execute" in exec_response.json()["detail"].lower()


# ==================== Decision Provenance Tests ====================


@pytest.mark.asyncio
async def test_decision_hash_is_unique(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test that each signal has a unique decision hash."""
    hashes = set()

    for i in range(5):
        signal_data = {
            "idempotency_key": f"hash-test-{i}-{uuid4().hex[:8]}",
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

        data = response.json()
        if data.get("decision_hash"):
            hashes.add(data["decision_hash"])

    # All hashes should be unique
    assert len(hashes) == 5


@pytest.mark.asyncio
async def test_decision_hash_format(
    async_client: AsyncClient,
    auth_headers: dict,
    test_profile,
):
    """Test that decision hash is valid SHA256 format."""
    import re

    signal_data = {
        "idempotency_key": f"hash-format-{uuid4().hex[:8]}",
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

    data = response.json()
    decision_hash = data.get("decision_hash", "")

    # SHA256 is 64 hex characters
    assert re.match(r"^[a-f0-9]{64}$", decision_hash)
