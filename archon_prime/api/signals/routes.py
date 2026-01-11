"""
Signal Routes

Authoritative ingress for all trade signals.
This is the ONLY path for signals to enter the system.

Invariants enforced:
1. Every signal carries origin, timestamp, decision hash, idempotency key
2. Signals are evaluated, not trusted
3. Admin and risk layers remain upstream of execution
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.session import get_db
from archon_prime.api.db.models import User, MT5Profile
from archon_prime.api.dependencies import get_current_user, get_profile_with_access
from archon_prime.api.auth.schemas import MessageResponse
from archon_prime.api.signals.schemas import (
    SignalSubmitRequest,
    SignalBatchRequest,
    SignalResponse,
    SignalListResponse,
    SignalStatsResponse,
    SignalDecision,
    RateLimitStatus,
    GateConfigResponse,
    GateConfigUpdateRequest,
)
from archon_prime.api.signals.service import SignalGateService


router = APIRouter()


# ==================== Signal Submission ====================


@router.post(
    "/{profile_id}/submit",
    response_model=SignalResponse,
    summary="Submit signal",
)
async def submit_signal(
    data: SignalSubmitRequest,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    """
    Submit a trade signal through the Signal Gate.

    This is the AUTHORITATIVE ingress point for all signals.
    Every signal is:
    - Validated for idempotency (same key = same response)
    - Rate-limited (except CRITICAL priority)
    - Evaluated through gate checks
    - Decision-hashed for provenance
    - Logged for audit

    Use idempotency_key to safely retry failed requests.
    The same key within 24 hours returns the cached decision.
    """
    service = SignalGateService(db)
    return await service.submit_signal(profile, data)


@router.post(
    "/{profile_id}/submit/batch",
    response_model=list[SignalResponse],
    summary="Submit batch signals",
)
async def submit_batch(
    data: SignalBatchRequest,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> list[SignalResponse]:
    """
    Submit multiple signals in a batch.

    Each signal is processed independently through the Gate.
    Rate limits apply to the batch as a whole.
    Max 10 signals per batch.
    """
    service = SignalGateService(db)
    results = []

    for signal in data.signals:
        result = await service.submit_signal(profile, signal)
        results.append(result)

    return results


# ==================== Signal Query ====================


@router.get(
    "/{profile_id}",
    response_model=SignalListResponse,
    summary="List signals",
)
async def list_signals(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    decision: Optional[str] = Query(
        None,
        description="Filter by decision (approved, rejected, executed, etc.)",
    ),
) -> SignalListResponse:
    """Get paginated list of signals for a profile."""
    service = SignalGateService(db)

    decision_enum = None
    if decision:
        try:
            decision_enum = SignalDecision(decision)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid decision filter: {decision}",
            )

    signals, total = await service.get_signals(
        profile.id,
        page=page,
        page_size=page_size,
        decision=decision_enum,
    )

    return SignalListResponse(
        signals=signals,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{profile_id}/{signal_id}",
    response_model=SignalResponse,
    summary="Get signal",
)
async def get_signal(
    signal_id: UUID,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    """Get a specific signal by ID."""
    service = SignalGateService(db)
    signal = await service.get_signal_by_id(profile.id, signal_id)

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    return signal


# ==================== Statistics ====================


@router.get(
    "/{profile_id}/stats",
    response_model=SignalStatsResponse,
    summary="Get signal statistics",
)
async def get_stats(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze"),
) -> SignalStatsResponse:
    """
    Get signal processing statistics.

    Returns approval rate, execution rate, rejection reasons, etc.
    """
    service = SignalGateService(db)
    return await service.get_stats(profile.id, hours=hours)


@router.get(
    "/{profile_id}/rate-limit",
    response_model=RateLimitStatus,
    summary="Get rate limit status",
)
async def get_rate_limit(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> RateLimitStatus:
    """Get current rate limit status for this profile."""
    service = SignalGateService(db)
    return service.check_rate_limit(profile.id)


# ==================== Gate Configuration ====================


@router.get(
    "/{profile_id}/config",
    response_model=GateConfigResponse,
    summary="Get gate configuration",
)
async def get_gate_config(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> GateConfigResponse:
    """
    Get Signal Gate configuration for this profile.

    Returns thresholds, limits, and risk parameters.
    """
    service = SignalGateService(db)
    return await service.get_gate_config(profile.id)


@router.patch(
    "/{profile_id}/config",
    response_model=GateConfigResponse,
    summary="Update gate configuration",
)
async def update_gate_config(
    data: GateConfigUpdateRequest,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> GateConfigResponse:
    """
    Update Signal Gate configuration.

    Only provided fields are updated.
    """
    service = SignalGateService(db)
    return await service.update_gate_config(
        profile.id,
        data.model_dump(exclude_unset=True),
    )


# ==================== Execution (Reserved) ====================


@router.post(
    "/{profile_id}/{signal_id}/execute",
    response_model=SignalResponse,
    summary="Execute approved signal",
)
async def execute_signal(
    signal_id: UUID,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    """
    Execute an approved signal.

    Only signals with decision=APPROVED can be executed.
    This triggers the actual trade placement via MT5.
    """
    service = SignalGateService(db)
    signal = await service.get_signal_by_id(profile.id, signal_id)

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    if signal.decision != SignalDecision.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute signal with decision: {signal.decision}",
        )

    if not profile.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile not connected",
        )

    if not profile.is_trading_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trading not enabled",
        )

    # TODO: Execute via MT5 connection pool
    # This would:
    # 1. Get connection from pool
    # 2. Calculate position size (Kelly if configured)
    # 3. Place order
    # 4. Update signal status to EXECUTED or FAILED
    # 5. Create position record

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Signal execution via MT5 not yet implemented",
    )


@router.post(
    "/{profile_id}/{signal_id}/cancel",
    response_model=MessageResponse,
    summary="Cancel pending signal",
)
async def cancel_signal(
    signal_id: UUID,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Cancel a pending or approved signal.

    Cannot cancel already executed signals.
    """
    service = SignalGateService(db)
    signal = await service.get_signal_by_id(profile.id, signal_id)

    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )

    if signal.decision in [SignalDecision.EXECUTED, SignalDecision.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel signal with decision: {signal.decision}",
        )

    # TODO: Update signal status to EXPIRED/CANCELLED
    # For now, just acknowledge

    return MessageResponse(message=f"Signal {signal_id} cancellation noted")
