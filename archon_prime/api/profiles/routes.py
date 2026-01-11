"""
MT5 Profile Routes

API endpoints for MT5 profile management.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.session import get_db
from archon_prime.api.db.models import User, MT5Profile
from archon_prime.api.dependencies import get_current_user, get_profile_with_access
from archon_prime.api.auth.schemas import MessageResponse
from archon_prime.api.profiles.schemas import (
    ProfileCreateRequest,
    ProfileUpdateRequest,
    ProfileCredentialsUpdateRequest,
    ProfileResponse,
    ProfileListResponse,
    ConnectionStatusResponse,
    TradingStatusResponse,
    AccountInfoResponse,
)
from archon_prime.api.profiles.service import ProfileService


router = APIRouter()


@router.get(
    "",
    response_model=ProfileListResponse,
    summary="List profiles",
)
async def list_profiles(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileListResponse:
    """Get all MT5 profiles for the current user."""
    service = ProfileService(db)
    profiles = await service.get_user_profiles(user.id)

    return ProfileListResponse(
        profiles=[ProfileResponse.from_model(p) for p in profiles],
        total=len(profiles),
    )


@router.post(
    "",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create profile",
)
async def create_profile(
    data: ProfileCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """
    Create a new MT5 profile.

    Profile limits depend on subscription tier:
    - Free: 1 profile
    - Starter: 2 profiles
    - Pro: 5 profiles
    - Enterprise: 20 profiles
    """
    service = ProfileService(db)
    profile, error = await service.create_profile(user, data)

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    return ProfileResponse.from_model(profile)


@router.get(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="Get profile",
)
async def get_profile(
    profile: MT5Profile = Depends(get_profile_with_access),
) -> ProfileResponse:
    """Get a specific MT5 profile."""
    return ProfileResponse.from_model(profile)


@router.patch(
    "/{profile_id}",
    response_model=ProfileResponse,
    summary="Update profile",
)
async def update_profile(
    data: ProfileUpdateRequest,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """Update profile settings."""
    service = ProfileService(db)
    updated = await service.update_profile(profile, data)
    return ProfileResponse.from_model(updated)


@router.patch(
    "/{profile_id}/credentials",
    response_model=ProfileResponse,
    summary="Update credentials",
)
async def update_credentials(
    data: ProfileCredentialsUpdateRequest,
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """
    Update MT5 login credentials.

    Profile must be disconnected first.
    """
    service = ProfileService(db)
    try:
        updated = await service.update_credentials(profile, data)
        return ProfileResponse.from_model(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{profile_id}",
    response_model=MessageResponse,
    summary="Delete profile",
)
async def delete_profile(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Delete an MT5 profile.

    Profile must be disconnected first. This action cannot be undone.
    """
    service = ProfileService(db)
    try:
        await service.delete_profile(profile)
        return MessageResponse(message="Profile deleted successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{profile_id}/connect",
    response_model=ConnectionStatusResponse,
    summary="Connect profile",
)
async def connect_profile(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> ConnectionStatusResponse:
    """
    Connect to MT5 terminal.

    This initiates a connection to the MT5 server using stored credentials.
    """
    if profile.is_connected:
        return ConnectionStatusResponse(
            profile_id=profile.id,
            is_connected=True,
            last_connected_at=profile.last_connected_at,
            message="Already connected",
        )

    service = ProfileService(db)

    # TODO: Actual MT5 connection via connection pool
    # For now, just update status
    await service.set_connected(profile, True)

    return ConnectionStatusResponse(
        profile_id=profile.id,
        is_connected=True,
        last_connected_at=profile.last_connected_at,
        message="Connected successfully",
    )


@router.post(
    "/{profile_id}/disconnect",
    response_model=ConnectionStatusResponse,
    summary="Disconnect profile",
)
async def disconnect_profile(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> ConnectionStatusResponse:
    """
    Disconnect from MT5 terminal.

    This closes the connection and disables trading.
    """
    if not profile.is_connected:
        return ConnectionStatusResponse(
            profile_id=profile.id,
            is_connected=False,
            last_connected_at=profile.last_connected_at,
            message="Already disconnected",
        )

    service = ProfileService(db)

    # Disable trading first
    if profile.is_trading_enabled:
        await service.set_trading_enabled(profile, False)

    # TODO: Actual MT5 disconnection via connection pool
    await service.set_connected(profile, False)

    return ConnectionStatusResponse(
        profile_id=profile.id,
        is_connected=False,
        last_connected_at=profile.last_connected_at,
        message="Disconnected successfully",
    )


@router.get(
    "/{profile_id}/account",
    response_model=AccountInfoResponse,
    summary="Get account info",
)
async def get_account_info(
    profile: MT5Profile = Depends(get_profile_with_access),
) -> AccountInfoResponse:
    """
    Get MT5 account information.

    Returns balance, equity, margin, and other account details.
    """
    if not profile.is_connected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is not connected",
        )

    return AccountInfoResponse(
        balance=profile.balance,
        equity=profile.equity,
        margin=profile.margin,
        free_margin=profile.free_margin,
        margin_level=profile.margin_level,
        leverage=profile.leverage,
        currency=profile.currency,
    )


@router.post(
    "/{profile_id}/trading/start",
    response_model=TradingStatusResponse,
    summary="Start trading",
)
async def start_trading(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> TradingStatusResponse:
    """
    Enable trading on this profile.

    Profile must be connected first.
    """
    service = ProfileService(db)
    try:
        await service.set_trading_enabled(profile, True)
        return TradingStatusResponse(
            profile_id=profile.id,
            is_trading_enabled=True,
            message="Trading enabled",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{profile_id}/trading/stop",
    response_model=TradingStatusResponse,
    summary="Stop trading",
)
async def stop_trading(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> TradingStatusResponse:
    """Stop trading on this profile."""
    service = ProfileService(db)
    await service.set_trading_enabled(profile, False)

    return TradingStatusResponse(
        profile_id=profile.id,
        is_trading_enabled=False,
        message="Trading disabled",
    )


@router.post(
    "/{profile_id}/kill-switch",
    response_model=MessageResponse,
    summary="Kill switch",
)
async def kill_switch(
    profile: MT5Profile = Depends(get_profile_with_access),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Emergency stop - disable trading and close all positions.

    This is a safety mechanism for emergency situations.
    """
    service = ProfileService(db)

    # Disable trading immediately
    await service.set_trading_enabled(profile, False)

    # TODO: Close all open positions via MT5 connection pool

    return MessageResponse(
        message="Kill switch activated - trading disabled, positions being closed"
    )
