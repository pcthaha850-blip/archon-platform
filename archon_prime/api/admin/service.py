"""
Admin Service

Business logic for admin dashboard and management.
"""

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from archon_prime.api.db.models import User, MT5Profile, Position, SystemEvent
from archon_prime.api.admin.schemas import (
    SystemStatsResponse,
    TierBreakdownResponse,
    DashboardResponse,
    AdminUserResponse,
    AdminProfileResponse,
    AlertResponse,
    ProfileFilterRequest,
    AlertFilterRequest,
)


class AdminService:
    """Service for admin operations."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self._start_time = datetime.now(timezone.utc)

    # ==================== Dashboard ====================

    async def get_dashboard(self) -> DashboardResponse:
        """Get complete dashboard data."""
        stats = await self.get_system_stats()
        tier_breakdown = await self.get_tier_breakdown()
        recent_alerts = await self.get_recent_alerts(limit=10)

        # Get WebSocket connection stats
        from archon_prime.api.websocket.manager import get_connection_manager
        ws_manager = get_connection_manager()
        ws_stats = ws_manager.get_stats()

        return DashboardResponse(
            stats=stats,
            tier_breakdown=tier_breakdown,
            recent_alerts=recent_alerts,
            active_connections=ws_stats.get("connections_per_profile", {}),
            server_time=datetime.now(timezone.utc),
        )

    async def get_system_stats(self) -> SystemStatsResponse:
        """Get system-wide statistics."""
        # Total users
        total_users = await self.db.scalar(
            select(func.count(User.id))
        )

        # Active users (with connected profiles)
        active_users = await self.db.scalar(
            select(func.count(func.distinct(MT5Profile.user_id))).where(
                MT5Profile.connection_status == "connected"
            )
        )

        # Profile counts
        total_profiles = await self.db.scalar(
            select(func.count(MT5Profile.id))
        )

        connected_profiles = await self.db.scalar(
            select(func.count(MT5Profile.id)).where(
                MT5Profile.connection_status == "connected"
            )
        )

        trading_profiles = await self.db.scalar(
            select(func.count(MT5Profile.id)).where(
                MT5Profile.is_trading_enabled == True
            )
        )

        # Position counts and profit
        total_positions = await self.db.scalar(
            select(func.count(Position.id))
        )

        total_profit = await self.db.scalar(
            select(func.sum(Position.unrealized_pnl))
        ) or Decimal("0")

        # WebSocket connections
        from archon_prime.api.websocket.manager import get_connection_manager
        ws_manager = get_connection_manager()
        ws_connections = ws_manager.get_total_connections()

        # Uptime
        uptime = (datetime.now(timezone.utc) - self._start_time).seconds

        return SystemStatsResponse(
            total_users=total_users or 0,
            active_users=active_users or 0,
            total_profiles=total_profiles or 0,
            connected_profiles=connected_profiles or 0,
            trading_profiles=trading_profiles or 0,
            total_positions=total_positions or 0,
            total_profit=total_profit,
            websocket_connections=ws_connections,
            uptime_seconds=uptime,
        )

    async def get_tier_breakdown(self) -> TierBreakdownResponse:
        """Get user count by subscription tier."""
        result = await self.db.execute(
            select(User.subscription_tier, func.count(User.id))
            .group_by(User.subscription_tier)
        )
        tiers = dict(result.all())

        return TierBreakdownResponse(
            free=tiers.get("free", 0),
            starter=tiers.get("starter", 0),
            pro=tiers.get("pro", 0),
            enterprise=tiers.get("enterprise", 0),
        )

    # ==================== User Management ====================

    async def get_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        tier: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[AdminUserResponse], int]:
        """Get paginated list of users with filters."""
        query = select(User)

        # Apply filters
        if search:
            search_filter = or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)

        if tier:
            query = query.where(User.subscription_tier == tier)

        if is_active is not None:
            query = query.where(User.is_active == is_active)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(desc(User.created_at))
        query = query.limit(page_size).offset(offset)

        result = await self.db.execute(query)
        users = result.scalars().all()

        # Build response with profile counts
        user_responses = []
        for user in users:
            # Get profile counts
            profile_count = await self.db.scalar(
                select(func.count(MT5Profile.id)).where(
                    MT5Profile.user_id == user.id
                )
            )
            connected_count = await self.db.scalar(
                select(func.count(MT5Profile.id)).where(
                    and_(
                        MT5Profile.user_id == user.id,
                        MT5Profile.is_connected == True,
                    )
                )
            )
            total_balance = await self.db.scalar(
                select(func.sum(MT5Profile.balance)).where(
                    MT5Profile.user_id == user.id
                )
            ) or Decimal("0")

            user_responses.append(
                AdminUserResponse(
                    id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    phone=user.phone,
                    subscription_tier=user.subscription_tier,
                    is_active=user.is_active,
                    is_admin=user.is_admin,
                    email_verified=user.email_verified,
                    profile_count=profile_count or 0,
                    connected_profile_count=connected_count or 0,
                    total_balance=total_balance,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    last_login_at=user.last_login_at,
                )
            )

        return user_responses, total

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_user(
        self,
        user: User,
        tier: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_admin: Optional[bool] = None,
    ) -> User:
        """Update user settings."""
        if tier is not None:
            user.subscription_tier = tier
        if is_active is not None:
            user.is_active = is_active
        if is_admin is not None:
            user.is_admin = is_admin

        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ==================== Profile Management ====================

    async def get_profiles(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[ProfileFilterRequest] = None,
    ) -> Tuple[List[AdminProfileResponse], int]:
        """Get paginated list of all profiles."""
        query = select(MT5Profile).options(selectinload(MT5Profile.user))

        # Apply filters
        if filters:
            if filters.user_id:
                query = query.where(MT5Profile.user_id == filters.user_id)
            if filters.is_connected is not None:
                query = query.where(MT5Profile.is_connected == filters.is_connected)
            if filters.is_trading_enabled is not None:
                query = query.where(
                    MT5Profile.is_trading_enabled == filters.is_trading_enabled
                )
            if filters.account_type:
                query = query.where(MT5Profile.account_type == filters.account_type)
            if filters.broker_name:
                query = query.where(
                    MT5Profile.broker_name.ilike(f"%{filters.broker_name}%")
                )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(desc(MT5Profile.created_at))
        query = query.limit(page_size).offset(offset)

        result = await self.db.execute(query)
        profiles = result.scalars().all()

        # Build response
        profile_responses = []
        for profile in profiles:
            # Get position count and profit
            position_count = await self.db.scalar(
                select(func.count(Position.id)).where(
                    Position.profile_id == profile.id
                )
            )
            total_profit = await self.db.scalar(
                select(func.sum(Position.profit)).where(
                    Position.profile_id == profile.id
                )
            )

            profile_responses.append(
                AdminProfileResponse(
                    id=profile.id,
                    user_id=profile.user_id,
                    user_email=profile.user.email if profile.user else "",
                    name=profile.name,
                    mt5_login=profile.mt5_login,
                    mt5_server=profile.mt5_server,
                    broker_name=profile.broker_name,
                    account_type=profile.account_type,
                    is_connected=profile.is_connected,
                    is_trading_enabled=profile.is_trading_enabled,
                    balance=profile.balance,
                    equity=profile.equity,
                    profit=total_profit,
                    open_positions=position_count or 0,
                    last_connected_at=profile.last_connected_at,
                    last_sync_at=profile.last_sync_at,
                    created_at=profile.created_at,
                )
            )

        return profile_responses, total

    async def force_disconnect_profile(self, profile_id: UUID) -> bool:
        """Force disconnect a profile."""
        result = await self.db.execute(
            select(MT5Profile).where(MT5Profile.id == profile_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return False

        # Disable trading and disconnect
        profile.is_trading_enabled = False
        profile.is_connected = False
        profile.updated_at = datetime.now(timezone.utc)

        await self.db.commit()

        # TODO: Actually disconnect from MT5 pool
        # from archon_prime.api.services.mt5_pool import get_mt5_pool
        # pool = get_mt5_pool()
        # await pool.disconnect(profile_id)

        return True

    # ==================== Alert Management ====================

    async def get_alerts(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[AlertFilterRequest] = None,
    ) -> Tuple[List[AlertResponse], int, int]:
        """Get paginated list of alerts."""
        query = select(SystemEvent)

        # Apply filters
        if filters:
            if filters.severity:
                query = query.where(SystemEvent.severity == filters.severity)
            if filters.event_type:
                query = query.where(SystemEvent.event_type == filters.event_type)
            if filters.user_id:
                query = query.where(SystemEvent.user_id == filters.user_id)
            if filters.profile_id:
                query = query.where(SystemEvent.profile_id == filters.profile_id)
            if filters.acknowledged is not None:
                query = query.where(SystemEvent.acknowledged == filters.acknowledged)
            if filters.from_date:
                query = query.where(SystemEvent.created_at >= filters.from_date)
            if filters.to_date:
                query = query.where(SystemEvent.created_at <= filters.to_date)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get unacknowledged count
        unack_count = await self.db.scalar(
            select(func.count(SystemEvent.id)).where(
                SystemEvent.acknowledged == False
            )
        ) or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(desc(SystemEvent.created_at))
        query = query.limit(page_size).offset(offset)

        result = await self.db.execute(query)
        events = result.scalars().all()

        # Build response with user/profile info
        alert_responses = []
        for event in events:
            user_email = None
            profile_name = None

            if event.user_id:
                user = await self.get_user_by_id(event.user_id)
                if user:
                    user_email = user.email

            if event.profile_id:
                profile_result = await self.db.execute(
                    select(MT5Profile).where(MT5Profile.id == event.profile_id)
                )
                profile = profile_result.scalar_one_or_none()
                if profile:
                    profile_name = profile.name

            ack_email = None
            if event.acknowledged_by:
                ack_user = await self.get_user_by_id(event.acknowledged_by)
                if ack_user:
                    ack_email = ack_user.email

            alert_responses.append(
                AlertResponse(
                    id=event.id,
                    event_type=event.event_type,
                    severity=event.severity,
                    source=event.source,
                    user_id=event.user_id,
                    user_email=user_email,
                    profile_id=event.profile_id,
                    profile_name=profile_name,
                    message=event.message,
                    details=event.details,
                    acknowledged=event.acknowledged,
                    acknowledged_by=event.acknowledged_by,
                    acknowledged_by_email=ack_email,
                    acknowledged_at=event.acknowledged_at,
                    created_at=event.created_at,
                )
            )

        return alert_responses, total, unack_count

    async def get_recent_alerts(self, limit: int = 10) -> List[AlertResponse]:
        """Get recent unacknowledged alerts."""
        alerts, _, _ = await self.get_alerts(
            page=1,
            page_size=limit,
            filters=AlertFilterRequest(acknowledged=False),
        )
        return alerts

    async def acknowledge_alerts(
        self,
        alert_ids: List[UUID],
        admin_id: UUID,
    ) -> int:
        """Acknowledge multiple alerts."""
        now = datetime.now(timezone.utc)
        count = 0

        for alert_id in alert_ids:
            result = await self.db.execute(
                select(SystemEvent).where(SystemEvent.id == alert_id)
            )
            event = result.scalar_one_or_none()

            if event and not event.acknowledged:
                event.acknowledged = True
                event.acknowledged_by = admin_id
                event.acknowledged_at = now
                count += 1

        await self.db.commit()
        return count

    async def create_alert(
        self,
        event_type: str,
        severity: str,
        source: str,
        message: str,
        user_id: Optional[UUID] = None,
        profile_id: Optional[UUID] = None,
        details: Optional[dict] = None,
    ) -> SystemEvent:
        """Create a new system alert."""
        event = SystemEvent(
            event_type=event_type,
            severity=severity,
            source=source,
            message=message,
            user_id=user_id,
            profile_id=profile_id,
            details=details,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event
