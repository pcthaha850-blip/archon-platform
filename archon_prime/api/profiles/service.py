"""
MT5 Profile Service

Business logic for MT5 profile management.
"""

from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.models import User, MT5Profile
from archon_prime.api.services.encryption import get_encryption_service
from archon_prime.api.profiles.schemas import (
    ProfileCreateRequest,
    ProfileUpdateRequest,
    ProfileCredentialsUpdateRequest,
)


# Subscription tier limits
TIER_LIMITS = {
    "free": {"max_profiles": 1, "max_positions": 1},
    "starter": {"max_profiles": 2, "max_positions": 3},
    "pro": {"max_profiles": 5, "max_positions": 5},
    "enterprise": {"max_profiles": 20, "max_positions": 10},
}


class ProfileService:
    """Service for MT5 profile operations."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.encryption = get_encryption_service()

    async def get_user_profiles(self, user_id: UUID) -> List[MT5Profile]:
        """Get all profiles for a user."""
        result = await self.db.execute(
            select(MT5Profile)
            .where(MT5Profile.user_id == user_id)
            .order_by(MT5Profile.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_profile_by_id(self, profile_id: UUID) -> Optional[MT5Profile]:
        """Get a profile by ID."""
        result = await self.db.execute(
            select(MT5Profile).where(MT5Profile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def count_user_profiles(self, user_id: UUID) -> int:
        """Count profiles for a user."""
        result = await self.db.execute(
            select(func.count(MT5Profile.id)).where(MT5Profile.user_id == user_id)
        )
        return result.scalar() or 0

    async def can_create_profile(self, user: User) -> tuple[bool, str]:
        """Check if user can create a new profile based on subscription."""
        tier = user.subscription_tier
        limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        max_profiles = limits["max_profiles"]

        current_count = await self.count_user_profiles(user.id)

        if current_count >= max_profiles:
            return False, f"Profile limit reached ({max_profiles}) for {tier} tier"

        return True, ""

    async def create_profile(
        self, user: User, data: ProfileCreateRequest
    ) -> tuple[Optional[MT5Profile], str]:
        """
        Create a new MT5 profile.

        Returns:
            Tuple of (profile, error_message)
        """
        # Check limits
        can_create, error = await self.can_create_profile(user)
        if not can_create:
            return None, error

        # Check for duplicate login
        existing = await self.db.execute(
            select(MT5Profile).where(
                MT5Profile.user_id == user.id,
                MT5Profile.mt5_login == data.mt5_login,
                MT5Profile.mt5_server == data.mt5_server,
            )
        )
        if existing.scalar_one_or_none():
            return None, "Profile with this login and server already exists"

        # Encrypt password
        encrypted_password = self.encryption.encrypt(data.mt5_password)

        # Create profile
        profile = MT5Profile(
            user_id=user.id,
            name=data.name,
            mt5_login=data.mt5_login,
            mt5_password_encrypted=encrypted_password,
            mt5_server=data.mt5_server,
            broker_name=data.broker_name,
            account_type=data.account_type,
        )

        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)

        return profile, ""

    async def update_profile(
        self, profile: MT5Profile, data: ProfileUpdateRequest
    ) -> MT5Profile:
        """Update profile settings."""
        if data.name is not None:
            profile.name = data.name
        if data.broker_name is not None:
            profile.broker_name = data.broker_name
        if data.risk_settings is not None:
            profile.risk_settings = data.risk_settings
        if data.trading_settings is not None:
            profile.trading_settings = data.trading_settings

        profile.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(profile)

        return profile

    async def update_credentials(
        self, profile: MT5Profile, data: ProfileCredentialsUpdateRequest
    ) -> MT5Profile:
        """Update MT5 credentials (requires disconnect first)."""
        if profile.is_connected:
            raise ValueError("Cannot update credentials while connected")

        if data.mt5_login is not None:
            profile.mt5_login = data.mt5_login
        if data.mt5_password is not None:
            profile.mt5_password_encrypted = self.encryption.encrypt(data.mt5_password)
        if data.mt5_server is not None:
            profile.mt5_server = data.mt5_server

        profile.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(profile)

        return profile

    async def delete_profile(self, profile: MT5Profile) -> bool:
        """Delete a profile (must be disconnected first)."""
        if profile.is_connected:
            raise ValueError("Cannot delete connected profile")

        await self.db.delete(profile)
        await self.db.commit()
        return True

    async def set_connected(
        self, profile: MT5Profile, connected: bool
    ) -> MT5Profile:
        """Update connection status."""
        profile.is_connected = connected
        if connected:
            profile.last_connected_at = datetime.now(timezone.utc)
        profile.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def set_trading_enabled(
        self, profile: MT5Profile, enabled: bool
    ) -> MT5Profile:
        """Enable or disable trading."""
        if enabled and not profile.is_connected:
            raise ValueError("Cannot enable trading on disconnected profile")

        profile.is_trading_enabled = enabled
        profile.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def update_account_info(
        self,
        profile: MT5Profile,
        balance: float,
        equity: float,
        margin: float,
        free_margin: float,
        margin_level: float,
        leverage: int,
        currency: str,
    ) -> MT5Profile:
        """Update account information from MT5."""
        profile.balance = balance
        profile.equity = equity
        profile.margin = margin
        profile.free_margin = free_margin
        profile.margin_level = margin_level
        profile.leverage = leverage
        profile.currency = currency
        profile.last_sync_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    def get_decrypted_password(self, profile: MT5Profile) -> str:
        """Get decrypted MT5 password for connection."""
        return self.encryption.decrypt(profile.mt5_password_encrypted)
