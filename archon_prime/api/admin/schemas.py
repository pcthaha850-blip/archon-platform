"""
Admin Schemas

Pydantic models for admin dashboard and management.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ==================== Dashboard ====================


class SystemStatsResponse(BaseModel):
    """Overall system statistics."""

    total_users: int = 0
    active_users: int = 0  # Users with at least one connected profile
    total_profiles: int = 0
    connected_profiles: int = 0
    trading_profiles: int = 0  # Profiles with trading enabled
    total_positions: int = 0
    total_profit: Decimal = Decimal("0")
    websocket_connections: int = 0
    uptime_seconds: int = 0


class TierBreakdownResponse(BaseModel):
    """User breakdown by subscription tier."""

    free: int = 0
    starter: int = 0
    pro: int = 0
    enterprise: int = 0


class DashboardResponse(BaseModel):
    """Complete admin dashboard data."""

    stats: SystemStatsResponse
    tier_breakdown: TierBreakdownResponse
    recent_alerts: List["AlertResponse"] = []
    active_connections: Dict[str, int] = {}  # profile_id -> connection count
    server_time: datetime


# ==================== User Management ====================


class AdminUserResponse(BaseModel):
    """User details for admin view."""

    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    subscription_tier: str
    is_active: bool
    is_admin: bool
    email_verified: bool
    profile_count: int = 0
    connected_profile_count: int = 0
    total_balance: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserListResponse(BaseModel):
    """Paginated list of users."""

    users: List[AdminUserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserUpdateRequest(BaseModel):
    """Admin request to update user."""

    subscription_tier: Optional[str] = Field(
        None, pattern="^(free|starter|pro|enterprise)$"
    )
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


# ==================== Profile Management ====================


class AdminProfileResponse(BaseModel):
    """MT5 profile details for admin view."""

    id: UUID
    user_id: UUID
    user_email: str
    name: str
    mt5_login: str
    mt5_server: str
    broker_name: Optional[str] = None
    account_type: str
    is_connected: bool
    is_trading_enabled: bool
    balance: Optional[Decimal] = None
    equity: Optional[Decimal] = None
    profit: Optional[Decimal] = None
    open_positions: int = 0
    last_connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminProfileListResponse(BaseModel):
    """Paginated list of profiles."""

    profiles: List[AdminProfileResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProfileFilterRequest(BaseModel):
    """Filter options for profile listing."""

    user_id: Optional[UUID] = None
    is_connected: Optional[bool] = None
    is_trading_enabled: Optional[bool] = None
    account_type: Optional[str] = None
    broker_name: Optional[str] = None


# ==================== Alert Management ====================


class AlertResponse(BaseModel):
    """System alert/event."""

    id: UUID
    event_type: str
    severity: str
    source: str
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    profile_id: Optional[UUID] = None
    profile_name: Optional[str] = None
    message: str
    details: Optional[Dict[str, Any]] = None
    acknowledged: bool
    acknowledged_by: Optional[UUID] = None
    acknowledged_by_email: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    """Paginated list of alerts."""

    alerts: List[AlertResponse]
    total: int
    unacknowledged_count: int
    page: int
    page_size: int


class AlertFilterRequest(BaseModel):
    """Filter options for alerts."""

    severity: Optional[str] = Field(None, pattern="^(info|warning|error|critical)$")
    event_type: Optional[str] = None
    user_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    acknowledged: Optional[bool] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class AcknowledgeAlertRequest(BaseModel):
    """Request to acknowledge alerts."""

    alert_ids: List[UUID] = Field(..., min_length=1)
    note: Optional[str] = None


# ==================== System Events ====================


class CreateAlertRequest(BaseModel):
    """Request to create a system alert."""

    event_type: str
    severity: str = Field(..., pattern="^(info|warning|error|critical)$")
    source: str
    message: str
    user_id: Optional[UUID] = None
    profile_id: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None


class SystemActionResponse(BaseModel):
    """Response for system actions."""

    success: bool
    action: str
    target_id: Optional[UUID] = None
    message: str
    details: Optional[Dict[str, Any]] = None


# Forward reference update
DashboardResponse.model_rebuild()
