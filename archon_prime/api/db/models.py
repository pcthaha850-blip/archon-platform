"""
SQLAlchemy ORM Models

Database models for the ARCHON commercial platform.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    LargeBinary,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Subscription
    subscription_tier: Mapped[str] = mapped_column(String(50), default="free")
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    max_profiles: Mapped[int] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    profiles: Mapped[list["MT5Profile"]] = relationship(
        "MT5Profile", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class MT5Profile(Base):
    """MT5 trading profile model."""

    __tablename__ = "mt5_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Profile info
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # MT5 credentials (password is encrypted)
    broker_server: Mapped[str] = mapped_column(String(255), nullable=False)
    mt5_login: Mapped[int] = mapped_column(Integer, nullable=False)
    mt5_password_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mt5_path: Mapped[Optional[str]] = mapped_column(String(500))

    # Connection status
    connection_status: Mapped[str] = mapped_column(String(50), default="disconnected")
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    # Account info (synced from MT5)
    balance: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    equity: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    broker_name: Mapped[Optional[str]] = mapped_column(String(255))
    account_type: Mapped[Optional[str]] = mapped_column(String(50))

    # Trading configuration
    risk_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    strategy_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_positions: Mapped[int] = mapped_column(Integer, default=2)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profiles")
    positions: Mapped[list["Position"]] = relationship(
        "Position", back_populates="profile", cascade="all, delete-orphan"
    )

    # Computed properties for compatibility
    @property
    def is_connected(self) -> bool:
        """Check if profile is connected."""
        return self.connection_status == "connected"

    @property
    def mt5_server(self) -> str:
        """Alias for broker_server."""
        return self.broker_server

    def __repr__(self) -> str:
        return f"<MT5Profile {self.name} ({self.mt5_login}@{self.broker_server})>"


class Position(Base):
    """Trading position model."""

    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mt5_profiles.id", ondelete="CASCADE"), nullable=False
    )

    # MT5 position data
    ticket: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=long, -1=short
    volume: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))

    # Risk levels
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))
    take_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))
    trailing_stop: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))

    # P&L
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    swap: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    commission: Mapped[float] = mapped_column(Numeric(20, 4), default=0)

    # Metadata
    strategy: Mapped[Optional[str]] = mapped_column(String(100))
    signal_id: Mapped[Optional[str]] = mapped_column(String(100))
    magic_number: Mapped[Optional[int]] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(String(255))

    # Status
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, closed, pending
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    close_price: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))
    realized_pnl: Mapped[Optional[float]] = mapped_column(Numeric(20, 4))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    profile: Mapped["MT5Profile"] = relationship("MT5Profile", back_populates="positions")

    def __repr__(self) -> str:
        direction_str = "LONG" if self.direction == 1 else "SHORT"
        return f"<Position {self.ticket} {self.symbol} {direction_str} {self.volume}>"


class TradeHistory(Base):
    """Closed trade history model."""

    __tablename__ = "trade_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mt5_profiles.id", ondelete="CASCADE"), nullable=False
    )

    ticket: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[int] = mapped_column(Integer, nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)

    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    stop_loss: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))
    take_profit: Mapped[Optional[float]] = mapped_column(Numeric(20, 8))

    realized_pnl: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    swap: Mapped[float] = mapped_column(Numeric(20, 4), default=0)
    commission: Mapped[float] = mapped_column(Numeric(20, 4), default=0)

    strategy: Mapped[Optional[str]] = mapped_column(String(100))
    signal_id: Mapped[Optional[str]] = mapped_column(String(100))
    close_reason: Mapped[Optional[str]] = mapped_column(String(50))

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class SystemEvent(Base):
    """System event log for admin monitoring."""

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info")
    source: Mapped[str] = mapped_column(String(100), default="system")

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mt5_profiles.id")
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Acknowledgement tracking
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
