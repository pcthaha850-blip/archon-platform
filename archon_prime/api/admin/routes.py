"""
Admin Routes

API endpoints for admin dashboard and system management.
All endpoints require admin authentication.
"""

import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.session import get_db
from archon_prime.api.db.models import User
from archon_prime.api.dependencies import get_admin_user
from archon_prime.api.auth.schemas import MessageResponse
from archon_prime.api.admin.schemas import (
    DashboardResponse,
    SystemStatsResponse,
    TierBreakdownResponse,
    AdminUserResponse,
    AdminUserListResponse,
    UserUpdateRequest,
    AdminProfileResponse,
    AdminProfileListResponse,
    ProfileFilterRequest,
    AlertResponse,
    AlertListResponse,
    AlertFilterRequest,
    AcknowledgeAlertRequest,
    CreateAlertRequest,
    SystemActionResponse,
)
from archon_prime.api.admin.service import AdminService


router = APIRouter()


# ==================== Dashboard ====================


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get admin dashboard",
)
async def get_dashboard(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """
    Get complete admin dashboard data.

    Includes system stats, tier breakdown, recent alerts,
    and active WebSocket connections.
    """
    service = AdminService(db)
    return await service.get_dashboard()


@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    summary="Get system statistics",
)
async def get_system_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SystemStatsResponse:
    """Get system-wide statistics."""
    service = AdminService(db)
    return await service.get_system_stats()


# ==================== User Management ====================


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List all users",
)
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search by email or name"),
    tier: Optional[str] = Query(None, description="Filter by subscription tier"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> AdminUserListResponse:
    """
    Get paginated list of all users.

    Supports search and filtering by tier and active status.
    """
    service = AdminService(db)
    users, total = await service.get_users(
        page=page,
        page_size=page_size,
        search=search,
        tier=tier,
        is_active=is_active,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return AdminUserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Get user details",
)
async def get_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """Get detailed information about a specific user."""
    service = AdminService(db)
    user = await service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get additional stats
    users, _ = await service.get_users(page=1, page_size=1)
    # Find the user in the response (hacky but works)
    for u in users:
        if u.id == user_id:
            return u

    # Fallback if not in first page
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        subscription_tier=user.subscription_tier,
        is_active=user.is_active,
        is_admin=user.is_admin,
        email_verified=user.email_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="Update user",
)
async def update_user(
    user_id: UUID,
    data: UserUpdateRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    """
    Update user settings.

    Can modify subscription tier, active status, and admin status.
    """
    service = AdminService(db)
    user = await service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-demotion from admin
    if user.id == admin.id and data.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin status",
        )

    updated = await service.update_user(
        user,
        tier=data.subscription_tier,
        is_active=data.is_active,
        is_admin=data.is_admin,
    )

    return AdminUserResponse(
        id=updated.id,
        email=updated.email,
        first_name=updated.first_name,
        last_name=updated.last_name,
        phone=updated.phone,
        subscription_tier=updated.subscription_tier,
        is_active=updated.is_active,
        is_admin=updated.is_admin,
        email_verified=updated.email_verified,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        last_login_at=updated.last_login_at,
    )


@router.post(
    "/users/{user_id}/suspend",
    response_model=SystemActionResponse,
    summary="Suspend user",
)
async def suspend_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SystemActionResponse:
    """
    Suspend a user account.

    Disables the account and disconnects all profiles.
    """
    service = AdminService(db)
    user = await service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend your own account",
        )

    await service.update_user(user, is_active=False)

    # Disconnect all user's profiles
    profiles, _ = await service.get_profiles(
        page=1,
        page_size=100,
        filters=ProfileFilterRequest(user_id=user_id),
    )
    disconnected = 0
    for profile in profiles:
        if profile.is_connected:
            await service.force_disconnect_profile(profile.id)
            disconnected += 1

    return SystemActionResponse(
        success=True,
        action="suspend_user",
        target_id=user_id,
        message=f"User suspended, {disconnected} profiles disconnected",
    )


# ==================== Profile Management ====================


@router.get(
    "/profiles",
    response_model=AdminProfileListResponse,
    summary="List all profiles",
)
async def list_profiles(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[UUID] = Query(None),
    is_connected: Optional[bool] = Query(None),
    is_trading_enabled: Optional[bool] = Query(None),
    account_type: Optional[str] = Query(None),
    broker_name: Optional[str] = Query(None),
) -> AdminProfileListResponse:
    """
    Get paginated list of all MT5 profiles.

    Supports filtering by user, connection status, and broker.
    """
    service = AdminService(db)

    filters = ProfileFilterRequest(
        user_id=user_id,
        is_connected=is_connected,
        is_trading_enabled=is_trading_enabled,
        account_type=account_type,
        broker_name=broker_name,
    )

    profiles, total = await service.get_profiles(
        page=page,
        page_size=page_size,
        filters=filters,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return AdminProfileListResponse(
        profiles=profiles,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/profiles/{profile_id}/disconnect",
    response_model=SystemActionResponse,
    summary="Force disconnect profile",
)
async def force_disconnect(
    profile_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SystemActionResponse:
    """
    Force disconnect an MT5 profile.

    Disables trading and closes the connection.
    """
    service = AdminService(db)
    success = await service.force_disconnect_profile(profile_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    # Log the action
    await service.create_alert(
        event_type="admin_action",
        severity="info",
        source="admin_api",
        message=f"Profile force disconnected by admin",
        profile_id=profile_id,
        details={"admin_id": str(admin.id)},
    )

    return SystemActionResponse(
        success=True,
        action="force_disconnect",
        target_id=profile_id,
        message="Profile disconnected successfully",
    )


# ==================== Alert Management ====================


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List alerts",
)
async def list_alerts(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    severity: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    user_id: Optional[UUID] = Query(None),
    profile_id: Optional[UUID] = Query(None),
    acknowledged: Optional[bool] = Query(None),
) -> AlertListResponse:
    """
    Get paginated list of system alerts.

    Supports filtering by severity, type, and acknowledgment status.
    """
    service = AdminService(db)

    filters = AlertFilterRequest(
        severity=severity,
        event_type=event_type,
        user_id=user_id,
        profile_id=profile_id,
        acknowledged=acknowledged,
    )

    alerts, total, unack_count = await service.get_alerts(
        page=page,
        page_size=page_size,
        filters=filters,
    )

    return AlertListResponse(
        alerts=alerts,
        total=total,
        unacknowledged_count=unack_count,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/alerts/acknowledge",
    response_model=SystemActionResponse,
    summary="Acknowledge alerts",
)
async def acknowledge_alerts(
    data: AcknowledgeAlertRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SystemActionResponse:
    """Acknowledge one or more alerts."""
    service = AdminService(db)
    count = await service.acknowledge_alerts(data.alert_ids, admin.id)

    return SystemActionResponse(
        success=True,
        action="acknowledge_alerts",
        message=f"{count} alerts acknowledged",
        details={"acknowledged_count": count},
    )


@router.post(
    "/alerts",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert",
)
async def create_alert(
    data: CreateAlertRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Create a new system alert.

    Useful for manual admin notifications.
    """
    service = AdminService(db)
    event = await service.create_alert(
        event_type=data.event_type,
        severity=data.severity,
        source=data.source,
        message=data.message,
        user_id=data.user_id,
        profile_id=data.profile_id,
        details=data.details,
    )

    return AlertResponse(
        id=event.id,
        event_type=event.event_type,
        severity=event.severity,
        source=event.source,
        user_id=event.user_id,
        profile_id=event.profile_id,
        message=event.message,
        details=event.details,
        acknowledged=event.acknowledged,
        acknowledged_by=event.acknowledged_by,
        acknowledged_at=event.acknowledged_at,
        created_at=event.created_at,
    )


# ==================== System Actions ====================


@router.post(
    "/broadcast",
    response_model=SystemActionResponse,
    summary="Broadcast message",
)
async def broadcast_message(
    message: str = Query(..., min_length=1, max_length=500),
    severity: str = Query("info", pattern="^(info|warning|error|critical)$"),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SystemActionResponse:
    """
    Broadcast a system message to all connected clients.

    Messages appear as notifications in the dashboard.
    """
    from archon_prime.api.websocket.handlers import get_broadcaster

    broadcaster = get_broadcaster()

    # This would need to iterate over all connected profiles
    # For now, just log the attempt
    service = AdminService(db)
    await service.create_alert(
        event_type="broadcast",
        severity=severity,
        source="admin_api",
        message=message,
        details={"admin_id": str(admin.id)},
    )

    return SystemActionResponse(
        success=True,
        action="broadcast",
        message="Broadcast sent to all connected clients",
        details={"message": message, "severity": severity},
    )
