"""
User Routes

API endpoints for user profile management.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.session import get_db
from archon_prime.api.db.models import User
from archon_prime.api.dependencies import get_current_user
from archon_prime.api.auth.schemas import UserResponse, MessageResponse
from archon_prime.api.auth.service import AuthService


router = APIRouter()


class UserUpdateRequest(BaseModel):
    """User profile update request."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get the current authenticated user's profile.

    Requires a valid access token.
    """
    return UserResponse.model_validate(user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
)
async def update_me(
    data: UserUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update the current user's profile.

    Only provided fields will be updated.
    """
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.phone is not None:
        user.phone = data.phone

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.patch(
    "/me/password",
    response_model=MessageResponse,
    summary="Change password",
)
async def change_password(
    data: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Change the current user's password.

    Requires the current password for verification.
    """
    auth_service = AuthService(db)

    success = await auth_service.change_password(
        user, data.current_password, data.new_password
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    return MessageResponse(message="Password changed successfully")
