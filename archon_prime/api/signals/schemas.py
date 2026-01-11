"""
Signal Schemas

Pydantic models for signal ingress and processing.
Supports idempotency, provenance tracking, and decision auditing.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class SignalDirection(str, Enum):
    """Trade signal direction."""
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class SignalSource(str, Enum):
    """Origin of the signal."""
    STRATEGY = "strategy"  # ML/Strategy generated
    MANUAL = "manual"      # Human override
    SYSTEM = "system"      # System-generated (rebalance, hedge)
    EXTERNAL = "external"  # External API


class SignalDecision(str, Enum):
    """Signal Gate decision."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class SignalPriority(str, Enum):
    """Signal urgency level."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"  # Bypass rate limits


# ==================== Request Models ====================


class SignalSubmitRequest(BaseModel):
    """
    Request to submit a new trade signal.

    Idempotency: Use idempotency_key to prevent duplicate processing.
    The same key within 24 hours returns the original decision.
    """

    idempotency_key: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Unique key to prevent duplicate signals",
    )
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: SignalDirection
    source: SignalSource = SignalSource.STRATEGY
    priority: SignalPriority = SignalPriority.NORMAL

    # Signal strength and reasoning
    confidence: Decimal = Field(..., ge=0, le=1, description="Confidence 0-1")
    reasoning: Optional[str] = Field(None, max_length=500)

    # Position parameters (optional - Gate may override)
    suggested_volume: Optional[Decimal] = Field(None, gt=0)
    suggested_sl: Optional[Decimal] = None
    suggested_tp: Optional[Decimal] = None

    # Metadata
    strategy_name: Optional[str] = Field(None, max_length=100)
    model_version: Optional[str] = Field(None, max_length=50)
    features: Optional[Dict[str, Any]] = None  # Feature values that triggered signal

    # Timing
    valid_until: Optional[datetime] = None  # Signal expires after this time


class SignalBatchRequest(BaseModel):
    """Batch of signals for bulk processing."""

    signals: List[SignalSubmitRequest] = Field(..., min_length=1, max_length=10)


# ==================== Response Models ====================


class GateCheckResult(BaseModel):
    """Result of individual gate check."""

    gate_name: str
    passed: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SignalResponse(BaseModel):
    """Response after signal processing."""

    id: UUID
    idempotency_key: str
    profile_id: UUID
    symbol: str
    direction: SignalDirection
    source: SignalSource
    priority: SignalPriority
    confidence: Decimal

    # Decision
    decision: SignalDecision
    decision_reason: Optional[str] = None
    decision_at: Optional[datetime] = None

    # Gate checks
    gate_checks: List[GateCheckResult] = []

    # Execution (if approved and executed)
    executed_at: Optional[datetime] = None
    ticket: Optional[int] = None
    executed_volume: Optional[Decimal] = None
    executed_price: Optional[Decimal] = None

    # Timing
    created_at: datetime
    valid_until: Optional[datetime] = None
    processing_time_ms: Optional[int] = None

    # Provenance
    strategy_name: Optional[str] = None
    model_version: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SignalListResponse(BaseModel):
    """List of signals with pagination."""

    signals: List[SignalResponse]
    total: int
    page: int
    page_size: int


class SignalStatsResponse(BaseModel):
    """Signal processing statistics."""

    profile_id: UUID
    period_hours: int = 24

    # Counts
    total_signals: int = 0
    approved: int = 0
    rejected: int = 0
    expired: int = 0
    executed: int = 0
    failed: int = 0

    # Rates
    approval_rate: Decimal = Decimal("0")
    execution_rate: Decimal = Decimal("0")

    # Performance
    avg_confidence: Decimal = Decimal("0")
    avg_processing_time_ms: int = 0

    # By source
    by_source: Dict[str, int] = {}

    # Recent rejections
    top_rejection_reasons: List[Dict[str, Any]] = []


class RateLimitStatus(BaseModel):
    """Current rate limit status for a profile."""

    profile_id: UUID
    window_seconds: int
    max_signals: int
    current_count: int
    remaining: int
    reset_at: datetime
    is_limited: bool


# ==================== Gate Configuration ====================


class GateConfigResponse(BaseModel):
    """Signal Gate configuration for a profile."""

    profile_id: UUID

    # Thresholds
    min_confidence: Decimal = Decimal("0.7")
    max_daily_signals: int = 50
    max_concurrent_positions: int = 2

    # Risk checks
    require_positive_expectancy: bool = True
    require_regime_alignment: bool = True
    max_correlation_exposure: Decimal = Decimal("0.7")
    max_drawdown_to_trade: Decimal = Decimal("0.15")  # 15%

    # Timing
    no_trade_before_news_minutes: int = 30
    no_trade_after_news_minutes: int = 30
    allowed_trading_hours: Optional[Dict[str, str]] = None

    # Overrides
    allow_manual_override: bool = True
    require_guardian_approval: bool = True


class GateConfigUpdateRequest(BaseModel):
    """Request to update Gate configuration."""

    min_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    max_daily_signals: Optional[int] = Field(None, ge=1, le=200)
    max_concurrent_positions: Optional[int] = Field(None, ge=1, le=20)
    require_positive_expectancy: Optional[bool] = None
    require_regime_alignment: Optional[bool] = None
    max_correlation_exposure: Optional[Decimal] = Field(None, ge=0, le=1)
    max_drawdown_to_trade: Optional[Decimal] = Field(None, ge=0, le=0.5)
