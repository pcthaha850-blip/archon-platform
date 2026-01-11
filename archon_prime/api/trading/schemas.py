"""
Trading Schemas

Pydantic models for positions and trade history.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class PositionResponse(BaseModel):
    """Open position details."""

    id: UUID
    profile_id: UUID
    ticket: int
    symbol: str
    position_type: str  # "buy" or "sell"
    volume: Decimal
    open_price: Decimal
    current_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    swap: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    profit: Optional[Decimal] = None
    magic_number: Optional[int] = None
    comment: Optional[str] = None
    open_time: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PositionListResponse(BaseModel):
    """List of positions."""

    positions: List[PositionResponse]
    total: int
    total_profit: Decimal = Decimal("0")


class ClosePositionRequest(BaseModel):
    """Request to close a position."""

    volume: Optional[Decimal] = Field(
        None, description="Volume to close. If None, closes entire position"
    )


class ModifyPositionRequest(BaseModel):
    """Request to modify position SL/TP."""

    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None


class TradeHistoryResponse(BaseModel):
    """Closed trade record."""

    id: UUID
    profile_id: UUID
    ticket: int
    order_ticket: Optional[int] = None
    symbol: str
    deal_type: str  # "buy", "sell", "deposit", "withdrawal", etc.
    direction: str  # "in" or "out"
    volume: Decimal
    price: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    swap: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    profit: Decimal
    magic_number: Optional[int] = None
    comment: Optional[str] = None
    deal_time: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TradeHistoryListResponse(BaseModel):
    """List of trade history records."""

    trades: List[TradeHistoryResponse]
    total: int
    total_profit: Decimal = Decimal("0")


class TradeHistoryFilterRequest(BaseModel):
    """Filter parameters for trade history."""

    symbol: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class EquitySnapshotResponse(BaseModel):
    """Equity snapshot for charts."""

    timestamp: datetime
    balance: Decimal
    equity: Decimal
    profit: Decimal
    margin_level: Optional[Decimal] = None


class EquityCurveResponse(BaseModel):
    """Equity curve data for charting."""

    profile_id: UUID
    snapshots: List[EquitySnapshotResponse]
    period_start: datetime
    period_end: datetime
    initial_balance: Decimal
    current_equity: Decimal
    total_profit: Decimal
    max_drawdown: Decimal
    profit_factor: Optional[Decimal] = None


class TradingStatsResponse(BaseModel):
    """Trading statistics summary."""

    profile_id: UUID
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: Decimal = Decimal("0")
    total_profit: Decimal = Decimal("0")
    total_loss: Decimal = Decimal("0")
    net_profit: Decimal = Decimal("0")
    average_profit: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    profit_factor: Optional[Decimal] = None
    max_drawdown: Decimal = Decimal("0")
    sharpe_ratio: Optional[Decimal] = None
