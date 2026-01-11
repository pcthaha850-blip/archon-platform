"""
Authentication Service

Business logic for user authentication.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.models import User
from archon_prime.api.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_token_expiry_seconds,
)
from archon_prime.api.auth.schemas import UserRegisterRequest


class AuthService:
    """Authentication service with password and JWT management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserRegisterRequest) -> User:
        """
        Register a new user.

        Args:
            data: Registration data

        Returns:
            Created user

        Raises:
            ValueError: If email already exists
        """
        # Check if email exists
        existing = await self.get_user_by_email(data.email)
        if existing:
            raise ValueError("Email already registered")

        # Hash password
        password_hash = bcrypt.hashpw(
            data.password.encode(), bcrypt.gensalt()
        ).decode()

        # Create user
        user = User(
            email=data.email,
            password_hash=password_hash,
            first_name=data.first_name,
            last_name=data.last_name,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def authenticate(
        self, email: str, password: str
    ) -> Optional[User]:
        """
        Authenticate user with email/password.

        Args:
            email: User's email
            password: Plain text password

        Returns:
            User if authenticated, None otherwise
        """
        user = await self.get_user_by_email(email)

        if not user or not user.is_active:
            return None

        # Verify password
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return None

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()

        return user

    def create_tokens(self, user: User) -> Tuple[str, str, int]:
        """
        Create access and refresh tokens for a user.

        Args:
            user: User instance

        Returns:
            Tuple of (access_token, refresh_token, expires_in_seconds)
        """
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            subscription_tier=user.subscription_tier,
        )

        refresh_token = create_refresh_token(user.id)
        expires_in = get_token_expiry_seconds()

        return access_token, refresh_token, expires_in

    async def refresh_tokens(
        self, refresh_token: str
    ) -> Optional[Tuple[str, str, int]]:
        """
        Generate new tokens from a refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New tokens if valid, None otherwise
        """
        payload = verify_token(refresh_token, "refresh")
        if not payload:
            return None

        user_id = UUID(payload["sub"])
        user = await self.get_user_by_id(user_id)

        if not user or not user.is_active:
            return None

        return self.create_tokens(user)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> bool:
        """
        Change user's password.

        Args:
            user: User instance
            current_password: Current password
            new_password: New password

        Returns:
            True if changed, False if current password wrong
        """
        # Verify current password
        if not bcrypt.checkpw(current_password.encode(), user.password_hash.encode()):
            return False

        # Hash new password
        user.password_hash = bcrypt.hashpw(
            new_password.encode(), bcrypt.gensalt()
        ).decode()

        await self.db.commit()
        return True
