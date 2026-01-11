"""
Trading Service

Business logic for positions and trade history.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.models import MT5Profile, Position, TradeHistory
from archon_prime.api.trading.schemas import (
    TradingStatsResponse,
    EquityCurveResponse,
    EquitySnapshotResponse,
)


class TradingService:
    """Service for trading operations."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db

    # ==================== Positions ====================

    async def get_positions(self, profile_id: UUID) -> List[Position]:
        """Get all open positions for a profile."""
        result = await self.db.execute(
            select(Position)
            .where(Position.profile_id == profile_id)
            .order_by(Position.open_time.desc())
        )
        return list(result.scalars().all())

    async def get_position_by_ticket(
        self, profile_id: UUID, ticket: int
    ) -> Optional[Position]:
        """Get a specific position by ticket."""
        result = await self.db.execute(
            select(Position).where(
                and_(
                    Position.profile_id == profile_id,
                    Position.ticket == ticket,
                )
            )
        )
        return result.scalar_one_or_none()

    async def sync_positions(
        self, profile_id: UUID, mt5_positions: List[dict]
    ) -> Tuple[int, int, int]:
        """
        Sync positions from MT5.

        Args:
            profile_id: Profile UUID
            mt5_positions: List of position dicts from MT5

        Returns:
            Tuple of (added, updated, removed) counts
        """
        # Get current positions from database
        current_positions = await self.get_positions(profile_id)
        current_tickets = {p.ticket: p for p in current_positions}

        # Track changes
        mt5_tickets = set()
        added = 0
        updated = 0

        for pos_data in mt5_positions:
            ticket = pos_data["ticket"]
            mt5_tickets.add(ticket)

            if ticket in current_tickets:
                # Update existing position
                position = current_tickets[ticket]
                position.current_price = pos_data.get("current_price")
                position.profit = pos_data.get("profit")
                position.swap = pos_data.get("swap")
                position.updated_at = datetime.now(timezone.utc)
                updated += 1
            else:
                # Add new position
                position = Position(
                    profile_id=profile_id,
                    ticket=ticket,
                    symbol=pos_data["symbol"],
                    position_type=pos_data["type"],
                    volume=pos_data["volume"],
                    open_price=pos_data["open_price"],
                    current_price=pos_data.get("current_price"),
                    stop_loss=pos_data.get("sl"),
                    take_profit=pos_data.get("tp"),
                    swap=pos_data.get("swap"),
                    commission=pos_data.get("commission"),
                    profit=pos_data.get("profit"),
                    magic_number=pos_data.get("magic"),
                    comment=pos_data.get("comment"),
                    open_time=pos_data["open_time"],
                )
                self.db.add(position)
                added += 1

        # Remove closed positions
        removed = 0
        for ticket, position in current_tickets.items():
            if ticket not in mt5_tickets:
                await self.db.delete(position)
                removed += 1

        await self.db.commit()
        return added, updated, removed

    async def update_position_price(
        self, profile_id: UUID, ticket: int, current_price: Decimal, profit: Decimal
    ) -> Optional[Position]:
        """Update position current price and profit."""
        position = await self.get_position_by_ticket(profile_id, ticket)
        if position:
            position.current_price = current_price
            position.profit = profit
            position.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(position)
        return position

    async def close_position(
        self, profile_id: UUID, ticket: int, close_data: dict
    ) -> bool:
        """
        Close a position and record in history.

        Args:
            profile_id: Profile UUID
            ticket: Position ticket
            close_data: Close details from MT5

        Returns:
            Success status
        """
        position = await self.get_position_by_ticket(profile_id, ticket)
        if not position:
            return False

        # Create trade history record
        history = TradeHistory(
            profile_id=profile_id,
            ticket=close_data.get("deal_ticket", ticket),
            order_ticket=ticket,
            symbol=position.symbol,
            deal_type=position.position_type,
            direction="out",
            volume=close_data.get("volume", position.volume),
            price=close_data["close_price"],
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            swap=position.swap,
            commission=position.commission,
            profit=close_data["profit"],
            magic_number=position.magic_number,
            comment=close_data.get("comment", position.comment),
            deal_time=close_data.get("close_time", datetime.now(timezone.utc)),
        )
        self.db.add(history)

        # Remove position
        await self.db.delete(position)
        await self.db.commit()

        return True

    async def get_total_profit(self, profile_id: UUID) -> Decimal:
        """Get total unrealized profit for open positions."""
        result = await self.db.execute(
            select(func.sum(Position.profit)).where(
                Position.profile_id == profile_id
            )
        )
        return result.scalar() or Decimal("0")

    # ==================== Trade History ====================

    async def get_trade_history(
        self,
        profile_id: UUID,
        symbol: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[TradeHistory], int]:
        """Get trade history with filters."""
        query = select(TradeHistory).where(TradeHistory.profile_id == profile_id)

        if symbol:
            query = query.where(TradeHistory.symbol == symbol)
        if from_date:
            query = query.where(TradeHistory.deal_time >= from_date)
        if to_date:
            query = query.where(TradeHistory.deal_time <= to_date)

        # Get total count
        count_query = select(func.count(TradeHistory.id)).where(
            TradeHistory.profile_id == profile_id
        )
        if symbol:
            count_query = count_query.where(TradeHistory.symbol == symbol)
        if from_date:
            count_query = count_query.where(TradeHistory.deal_time >= from_date)
        if to_date:
            count_query = count_query.where(TradeHistory.deal_time <= to_date)

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(desc(TradeHistory.deal_time))
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        trades = list(result.scalars().all())

        return trades, total

    async def get_history_total_profit(
        self,
        profile_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Decimal:
        """Get total realized profit from history."""
        query = select(func.sum(TradeHistory.profit)).where(
            TradeHistory.profile_id == profile_id
        )
        if from_date:
            query = query.where(TradeHistory.deal_time >= from_date)
        if to_date:
            query = query.where(TradeHistory.deal_time <= to_date)

        result = await self.db.execute(query)
        return result.scalar() or Decimal("0")

    async def record_trade(self, profile_id: UUID, trade_data: dict) -> TradeHistory:
        """Record a trade from MT5."""
        trade = TradeHistory(
            profile_id=profile_id,
            ticket=trade_data["ticket"],
            order_ticket=trade_data.get("order_ticket"),
            symbol=trade_data["symbol"],
            deal_type=trade_data["type"],
            direction=trade_data["direction"],
            volume=trade_data["volume"],
            price=trade_data["price"],
            stop_loss=trade_data.get("sl"),
            take_profit=trade_data.get("tp"),
            swap=trade_data.get("swap"),
            commission=trade_data.get("commission"),
            profit=trade_data["profit"],
            magic_number=trade_data.get("magic"),
            comment=trade_data.get("comment"),
            deal_time=trade_data["time"],
        )
        self.db.add(trade)
        await self.db.commit()
        await self.db.refresh(trade)
        return trade

    # ==================== Statistics ====================

    async def get_trading_stats(
        self,
        profile_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> TradingStatsResponse:
        """Calculate trading statistics."""
        # Base query
        base_filter = TradeHistory.profile_id == profile_id
        if from_date:
            base_filter = and_(base_filter, TradeHistory.deal_time >= from_date)
        if to_date:
            base_filter = and_(base_filter, TradeHistory.deal_time <= to_date)

        # Get all trades for calculation
        result = await self.db.execute(
            select(TradeHistory).where(base_filter)
        )
        trades = list(result.scalars().all())

        if not trades:
            return TradingStatsResponse(profile_id=profile_id)

        # Calculate statistics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.profit > 0)
        losing_trades = sum(1 for t in trades if t.profit < 0)

        total_profit = sum(t.profit for t in trades if t.profit > 0) or Decimal("0")
        total_loss = abs(sum(t.profit for t in trades if t.profit < 0)) or Decimal("0")
        net_profit = total_profit - total_loss

        win_rate = Decimal(str(winning_trades / total_trades * 100)) if total_trades > 0 else Decimal("0")
        avg_profit = total_profit / winning_trades if winning_trades > 0 else Decimal("0")
        avg_loss = total_loss / losing_trades if losing_trades > 0 else Decimal("0")
        profit_factor = total_profit / total_loss if total_loss > 0 else None

        return TradingStatsResponse(
            profile_id=profile_id,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate.quantize(Decimal("0.01")),
            total_profit=total_profit,
            total_loss=total_loss,
            net_profit=net_profit,
            average_profit=avg_profit.quantize(Decimal("0.01")),
            average_loss=avg_loss.quantize(Decimal("0.01")),
            profit_factor=profit_factor.quantize(Decimal("0.01")) if profit_factor else None,
        )

    async def get_equity_curve(
        self,
        profile: MT5Profile,
        days: int = 30,
    ) -> EquityCurveResponse:
        """Get equity curve data for charting."""
        # Get historical trades for equity calculation
        from_date = datetime.now(timezone.utc) - timedelta(days=days)

        trades, _ = await self.get_trade_history(
            profile.id,
            from_date=from_date,
            limit=10000,
        )

        # Build equity curve from trades
        snapshots = []
        running_equity = profile.balance or Decimal("10000")
        initial_balance = running_equity

        # Sort trades by time
        sorted_trades = sorted(trades, key=lambda t: t.deal_time)

        for trade in sorted_trades:
            running_equity += trade.profit
            snapshots.append(
                EquitySnapshotResponse(
                    timestamp=trade.deal_time,
                    balance=running_equity,
                    equity=running_equity,
                    profit=trade.profit,
                )
            )

        # Calculate max drawdown
        max_drawdown = Decimal("0")
        peak = initial_balance
        for snap in snapshots:
            if snap.equity > peak:
                peak = snap.equity
            drawdown = (peak - snap.equity) / peak * 100 if peak > 0 else Decimal("0")
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        current_equity = profile.equity or running_equity
        total_profit = current_equity - initial_balance

        return EquityCurveResponse(
            profile_id=profile.id,
            snapshots=snapshots,
            period_start=from_date,
            period_end=datetime.now(timezone.utc),
            initial_balance=initial_balance,
            current_equity=current_equity,
            total_profit=total_profit,
            max_drawdown=max_drawdown.quantize(Decimal("0.01")),
        )
