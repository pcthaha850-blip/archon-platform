"""
Trading Routes

API endpoints for positions and trade history.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.session import get_db
from archon_prime.api.db.models import MT5Profile
from archon_prime.api.dependencies import get_profile_with_access
from archon_prime.api.auth.schemas import MessageResponse
from archon_prime.api.trading.schemas import (
    PositionResponse,
    PositionListResponse,
    ClosePositionRequest,
    ModifyPositionRequest,
    TradeHistoryResponse,
    TradeHistoryListResponse,
    TradingStatsResponse,
    EquityCurveResponse,
)
from archon_prime.api.trading.service import TradingService


router = APIRouter()


# ==================== Positions ====================


@router.get(
    "/{profile_id}/positions",
    response_model=PositionListResponse,
    summary="Get open positions",
)
async def get_positions(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> PositionListResponse:
    """Get all open positions for a profile."""
    if not profile.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is not connected",
        )

    service = TradingService(db)
    positions = await service.get_positions(profile.id)
    total_profit = await service.get_total_profit(profile.id)

    return PositionListResponse(
        positions=[PositionResponse.model_validate(p) for p in positions],
        total=len(positions),
        total_profit=total_profit,
    )


@router.get(
    "/{profile_id}/positions/{ticket}",
    response_model=PositionResponse,
    summary="Get position by ticket",
)
async def get_position(
    ticket: int,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> PositionResponse:
    """Get a specific position by ticket number."""
    service = TradingService(db)
    position = await service.get_position_by_ticket(profile.id, ticket)

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    return PositionResponse.model_validate(position)


@router.post(
    "/{profile_id}/positions/{ticket}/close",
    response_model=MessageResponse,
    summary="Close position",
)
async def close_position(
    ticket: int,
    data: ClosePositionRequest,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Close an open position.

    If volume is specified, closes partial position.
    """
    if not profile.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is not connected",
        )

    if not profile.is_trading_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trading is not enabled",
        )

    service = TradingService(db)
    position = await service.get_position_by_ticket(profile.id, ticket)

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    # TODO: Execute close via MT5 connection pool
    # For now, simulate close
    close_data = {
        "close_price": position.current_price or position.open_price,
        "profit": position.profit or Decimal("0"),
        "volume": data.volume or position.volume,
    }

    success = await service.close_position(profile.id, ticket, close_data)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to close position",
        )

    return MessageResponse(message=f"Position {ticket} closed successfully")


@router.patch(
    "/{profile_id}/positions/{ticket}",
    response_model=PositionResponse,
    summary="Modify position",
)
async def modify_position(
    ticket: int,
    data: ModifyPositionRequest,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> PositionResponse:
    """Modify position stop loss or take profit."""
    if not profile.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is not connected",
        )

    service = TradingService(db)
    position = await service.get_position_by_ticket(profile.id, ticket)

    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    # TODO: Execute modify via MT5 connection pool
    # For now, update directly
    if data.stop_loss is not None:
        position.stop_loss = data.stop_loss
    if data.take_profit is not None:
        position.take_profit = data.take_profit

    await db.commit()
    await db.refresh(position)

    return PositionResponse.model_validate(position)


# ==================== Trade History ====================


@router.get(
    "/{profile_id}/history",
    response_model=TradeHistoryListResponse,
    summary="Get trade history",
)
async def get_trade_history(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    from_date: Optional[str] = Query(None, description="From date (ISO format)"),
    to_date: Optional[str] = Query(None, description="To date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> TradeHistoryListResponse:
    """Get trade history with optional filters."""
    from datetime import datetime

    # Parse dates if provided
    from_dt = None
    to_dt = None
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid from_date format",
            )
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid to_date format",
            )

    service = TradingService(db)
    trades, total = await service.get_trade_history(
        profile.id,
        symbol=symbol,
        from_date=from_dt,
        to_date=to_dt,
        limit=limit,
        offset=offset,
    )

    total_profit = await service.get_history_total_profit(
        profile.id, from_date=from_dt, to_date=to_dt
    )

    return TradeHistoryListResponse(
        trades=[TradeHistoryResponse.model_validate(t) for t in trades],
        total=total,
        total_profit=total_profit,
    )


# ==================== Statistics ====================


@router.get(
    "/{profile_id}/stats",
    response_model=TradingStatsResponse,
    summary="Get trading statistics",
)
async def get_trading_stats(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days"),
) -> TradingStatsResponse:
    """Get trading statistics for a profile."""
    from datetime import datetime, timezone, timedelta

    from_date = datetime.now(timezone.utc) - timedelta(days=days)

    service = TradingService(db)
    return await service.get_trading_stats(profile.id, from_date=from_date)


@router.get(
    "/{profile_id}/equity",
    response_model=EquityCurveResponse,
    summary="Get equity curve",
)
async def get_equity_curve(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days"),
) -> EquityCurveResponse:
    """Get equity curve data for charting."""
    service = TradingService(db)
    return await service.get_equity_curve(profile, days=days)


# ==================== Sync ====================


@router.post(
    "/{profile_id}/sync",
    response_model=MessageResponse,
    summary="Sync positions from MT5",
)
async def sync_positions(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Manually trigger position sync from MT5.

    Normally positions are synced automatically.
    """
    if not profile.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is not connected",
        )

    # TODO: Get positions from MT5 connection pool
    # For now, return success message
    service = TradingService(db)

    # Simulated MT5 positions (in production, this comes from MT5)
    mt5_positions = []

    added, updated, removed = await service.sync_positions(profile.id, mt5_positions)

    return MessageResponse(
        message=f"Sync complete: {added} added, {updated} updated, {removed} removed"
    )
