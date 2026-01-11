"""
MT5 Profile Schemas

Pydantic models for MT5 profile requests and responses.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ProfileCreateRequest(BaseModel):
    """Request to create a new MT5 profile."""

    name: str = Field(..., min_length=1, max_length=100, description="Profile display name")
    mt5_login: str = Field(..., min_length=1, max_length=50, description="MT5 account login")
    mt5_password: str = Field(..., min_length=1, description="MT5 account password")
    mt5_server: str = Field(..., min_length=1, max_length=255, description="MT5 server address")
    broker_name: Optional[str] = Field(None, max_length=100, description="Broker name")
    account_type: str = Field("demo", pattern="^(demo|live)$", description="Account type")


class ProfileUpdateRequest(BaseModel):
    """Request to update an MT5 profile."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    broker_name: Optional[str] = Field(None, max_length=100)
    risk_settings: Optional[Dict[str, Any]] = None
    trading_settings: Optional[Dict[str, Any]] = None


class ProfileCredentialsUpdateRequest(BaseModel):
    """Request to update MT5 credentials."""

    mt5_login: Optional[str] = Field(None, min_length=1, max_length=50)
    mt5_password: Optional[str] = Field(None, min_length=1)
    mt5_server: Optional[str] = Field(None, min_length=1, max_length=255)


class AccountInfoResponse(BaseModel):
    """MT5 account information."""

    balance: Optional[Decimal] = None
    equity: Optional[Decimal] = None
    margin: Optional[Decimal] = None
    free_margin: Optional[Decimal] = None
    margin_level: Optional[Decimal] = None
    leverage: Optional[int] = None
    currency: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProfileResponse(BaseModel):
    """MT5 profile response."""

    id: UUID
    user_id: UUID
    name: str
    mt5_login: str
    mt5_server: str
    broker_name: Optional[str] = None
    account_type: str
    is_connected: bool
    is_trading_enabled: bool
    last_connected_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    account: AccountInfoResponse
    risk_settings: Dict[str, Any]
    trading_settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_model(cls, profile) -> "ProfileResponse":
        """Create response from ORM model."""
        return cls(
            id=profile.id,
            user_id=profile.user_id,
            name=profile.name,
            mt5_login=profile.mt5_login,
            mt5_server=profile.mt5_server,
            broker_name=profile.broker_name,
            account_type=profile.account_type,
            is_connected=profile.is_connected,
            is_trading_enabled=profile.is_trading_enabled,
            last_connected_at=profile.last_connected_at,
            last_sync_at=profile.last_sync_at,
            account=AccountInfoResponse(
                balance=profile.balance,
                equity=profile.equity,
                margin=profile.margin,
                free_margin=profile.free_margin,
                margin_level=profile.margin_level,
                leverage=profile.leverage,
                currency=profile.currency,
            ),
            risk_settings=profile.risk_settings or {},
            trading_settings=profile.trading_settings or {},
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class ProfileListResponse(BaseModel):
    """List of profiles response."""

    profiles: list[ProfileResponse]
    total: int


class ConnectionStatusResponse(BaseModel):
    """Profile connection status."""

    profile_id: UUID
    is_connected: bool
    last_connected_at: Optional[datetime] = None
    message: str


class TradingStatusResponse(BaseModel):
    """Profile trading status."""

    profile_id: UUID
    is_trading_enabled: bool
    message: str
