"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2026-01-11

Creates the initial ARCHON PRIME database schema with:
- users: User accounts with subscription tiers
- mt5_profiles: MT5 credentials (encrypted) per user
- positions: Live position tracking
- trade_history: Closed trade records
- system_events: Admin audit log
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("subscription_tier", sa.String(50), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_subscription_tier", "users", ["subscription_tier"])

    # MT5 Profiles table
    op.create_table(
        "mt5_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("mt5_login", sa.String(50), nullable=False),
        sa.Column("mt5_password_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("mt5_server", sa.String(255), nullable=False),
        sa.Column("broker_name", sa.String(100), nullable=True),
        sa.Column("account_type", sa.String(50), nullable=False, server_default="demo"),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_trading_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("balance", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("equity", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("margin", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("free_margin", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("margin_level", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("leverage", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("risk_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("trading_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mt5_profiles_user_id", "mt5_profiles", ["user_id"])
    op.create_index("ix_mt5_profiles_is_connected", "mt5_profiles", ["is_connected"])

    # Positions table
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("position_type", sa.String(10), nullable=False),
        sa.Column("volume", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("open_price", sa.Numeric(precision=15, scale=5), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=15, scale=5), nullable=True),
        sa.Column("stop_loss", sa.Numeric(precision=15, scale=5), nullable=True),
        sa.Column("take_profit", sa.Numeric(precision=15, scale=5), nullable=True),
        sa.Column("swap", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("commission", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("profit", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("magic_number", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(255), nullable=True),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["mt5_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "ticket", name="uq_positions_profile_ticket"),
    )
    op.create_index("ix_positions_profile_id", "positions", ["profile_id"])
    op.create_index("ix_positions_symbol", "positions", ["symbol"])
    op.create_index("ix_positions_open_time", "positions", ["open_time"])

    # Trade History table
    op.create_table(
        "trade_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket", sa.BigInteger(), nullable=False),
        sa.Column("order_ticket", sa.BigInteger(), nullable=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("deal_type", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("volume", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("price", sa.Numeric(precision=15, scale=5), nullable=False),
        sa.Column("stop_loss", sa.Numeric(precision=15, scale=5), nullable=True),
        sa.Column("take_profit", sa.Numeric(precision=15, scale=5), nullable=True),
        sa.Column("swap", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("commission", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("profit", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("magic_number", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(255), nullable=True),
        sa.Column("deal_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["mt5_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trade_history_profile_id", "trade_history", ["profile_id"])
    op.create_index("ix_trade_history_symbol", "trade_history", ["symbol"])
    op.create_index("ix_trade_history_deal_time", "trade_history", ["deal_time"])

    # System Events table
    op.create_table(
        "system_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["mt5_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_event_type", "system_events", ["event_type"])
    op.create_index("ix_system_events_severity", "system_events", ["severity"])
    op.create_index("ix_system_events_created_at", "system_events", ["created_at"])
    op.create_index("ix_system_events_acknowledged", "system_events", ["acknowledged"])


def downgrade() -> None:
    op.drop_table("system_events")
    op.drop_table("trade_history")
    op.drop_table("positions")
    op.drop_table("mt5_profiles")
    op.drop_table("users")
