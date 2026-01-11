"""
JWT Token Handling

Create and verify JWT tokens for authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from archon_prime.api.config import settings


def create_access_token(
    user_id: UUID,
    email: str,
    is_admin: bool = False,
    subscription_tier: str = "free",
) -> str:
    """
    Create a new access token.

    Args:
        user_id: User's UUID
        email: User's email
        is_admin: Whether user is admin
        subscription_tier: User's subscription level

    Returns:
        Encoded JWT access token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "email": email,
        "is_admin": is_admin,
        "subscription_tier": subscription_tier,
        "iat": now,
        "exp": expire,
        "type": "access",
    }

    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(user_id: UUID) -> str:
    """
    Create a new refresh token.

    Args:
        user_id: User's UUID

    Returns:
        Encoded JWT refresh token
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid4()),  # Unique token ID for revocation
    }

    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Verify token type
        if payload.get("type") != token_type:
            return None

        return payload

    except ExpiredSignatureError:
        return None
    except InvalidTokenError:
        return None


def get_token_expiry_seconds() -> int:
    """Get access token expiry in seconds."""
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
