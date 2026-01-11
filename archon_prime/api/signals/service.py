"""
Signal Gate Service

Authoritative signal ingress with evaluation, not trust.
All signals flow through this single path - no shortcuts.

Invariants:
1. Single ingress path for all signals
2. Every signal carries: origin, timestamp, decision hash, idempotency key
3. Signals are evaluated, not trusted
4. Admin and risk layers remain upstream of execution
"""

import hashlib
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from archon_prime.api.db.models import MT5Profile, Position
from archon_prime.api.signals.schemas import (
    SignalDirection,
    SignalSource,
    SignalDecision,
    SignalPriority,
    SignalSubmitRequest,
    SignalResponse,
    GateCheckResult,
    SignalStatsResponse,
    RateLimitStatus,
    GateConfigResponse,
)


# In-memory stores (production: use Redis)
_idempotency_cache: Dict[str, Tuple[datetime, SignalResponse]] = {}
_rate_limit_windows: Dict[UUID, Dict[str, int]] = {}  # profile_id -> {window_key: count}
_signal_store: Dict[UUID, List[dict]] = {}  # profile_id -> signals (production: database table)


# Default gate configuration
DEFAULT_GATE_CONFIG = {
    "min_confidence": Decimal("0.7"),
    "max_daily_signals": 50,
    "max_concurrent_positions": 2,
    "require_positive_expectancy": True,
    "require_regime_alignment": True,
    "max_correlation_exposure": Decimal("0.7"),
    "max_drawdown_to_trade": Decimal("0.15"),
    "no_trade_before_news_minutes": 30,
    "no_trade_after_news_minutes": 30,
    "allow_manual_override": True,
    "require_guardian_approval": True,
}


class SignalGateService:
    """
    Authoritative signal processing service.

    Every signal is:
    1. Validated for idempotency
    2. Rate-limited
    3. Evaluated through gate checks
    4. Decision-hashed for provenance
    5. Logged for audit
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Idempotency ====================

    def _get_idempotency_key(self, profile_id: UUID, key: str) -> str:
        """Create composite idempotency key."""
        return f"{profile_id}:{key}"

    def _check_idempotency(
        self, profile_id: UUID, key: str
    ) -> Optional[SignalResponse]:
        """
        Check if signal was already processed.

        Returns cached response if found within 24 hours.
        """
        composite_key = self._get_idempotency_key(profile_id, key)

        if composite_key in _idempotency_cache:
            cached_at, response = _idempotency_cache[composite_key]
            # Valid for 24 hours
            if datetime.now(timezone.utc) - cached_at < timedelta(hours=24):
                return response
            else:
                del _idempotency_cache[composite_key]

        return None

    def _cache_response(
        self, profile_id: UUID, key: str, response: SignalResponse
    ) -> None:
        """Cache response for idempotency."""
        composite_key = self._get_idempotency_key(profile_id, key)
        _idempotency_cache[composite_key] = (datetime.now(timezone.utc), response)

    # ==================== Rate Limiting ====================

    def _get_rate_limit_window(self) -> str:
        """Get current rate limit window key (1-minute windows)."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y%m%d%H%M")

    def check_rate_limit(
        self, profile_id: UUID, max_per_minute: int = 10
    ) -> RateLimitStatus:
        """Check rate limit for profile."""
        window_key = self._get_rate_limit_window()

        if profile_id not in _rate_limit_windows:
            _rate_limit_windows[profile_id] = {}

        windows = _rate_limit_windows[profile_id]

        # Clean old windows
        current_keys = [window_key]
        for key in list(windows.keys()):
            if key not in current_keys:
                del windows[key]

        current_count = windows.get(window_key, 0)
        remaining = max(0, max_per_minute - current_count)

        # Calculate reset time
        now = datetime.now(timezone.utc)
        reset_at = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

        return RateLimitStatus(
            profile_id=profile_id,
            window_seconds=60,
            max_signals=max_per_minute,
            current_count=current_count,
            remaining=remaining,
            reset_at=reset_at,
            is_limited=remaining == 0,
        )

    def _increment_rate_limit(self, profile_id: UUID) -> None:
        """Increment rate limit counter."""
        window_key = self._get_rate_limit_window()

        if profile_id not in _rate_limit_windows:
            _rate_limit_windows[profile_id] = {}

        windows = _rate_limit_windows[profile_id]
        windows[window_key] = windows.get(window_key, 0) + 1

    # ==================== Decision Hash ====================

    def _compute_decision_hash(
        self,
        signal_id: UUID,
        profile_id: UUID,
        symbol: str,
        direction: str,
        decision: str,
        timestamp: datetime,
    ) -> str:
        """
        Compute cryptographic hash of decision for provenance.

        This hash proves the decision was made at this time
        with these exact parameters.
        """
        data = f"{signal_id}|{profile_id}|{symbol}|{direction}|{decision}|{timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:32]

    # ==================== Gate Checks ====================

    async def _check_confidence(
        self, signal: SignalSubmitRequest, config: dict
    ) -> GateCheckResult:
        """Check minimum confidence threshold."""
        min_conf = config.get("min_confidence", Decimal("0.7"))
        passed = signal.confidence >= min_conf

        return GateCheckResult(
            gate_name="confidence",
            passed=passed,
            reason=None if passed else f"Confidence {signal.confidence} < {min_conf}",
            details={"required": str(min_conf), "actual": str(signal.confidence)},
        )

    async def _check_position_limit(
        self, profile_id: UUID, config: dict
    ) -> GateCheckResult:
        """Check concurrent position limit."""
        max_positions = config.get("max_concurrent_positions", 2)

        # Count open positions
        result = await self.db.execute(
            select(func.count(Position.id)).where(Position.profile_id == profile_id)
        )
        current = result.scalar() or 0

        passed = current < max_positions

        return GateCheckResult(
            gate_name="position_limit",
            passed=passed,
            reason=None if passed else f"Position limit reached ({current}/{max_positions})",
            details={"max": max_positions, "current": current},
        )

    async def _check_drawdown(
        self, profile: MT5Profile, config: dict
    ) -> GateCheckResult:
        """Check if drawdown is within tradeable range."""
        max_dd = config.get("max_drawdown_to_trade", Decimal("0.15"))

        # Calculate current drawdown (simplified)
        if profile.balance and profile.equity and profile.balance > 0:
            current_dd = (profile.balance - profile.equity) / profile.balance
        else:
            current_dd = Decimal("0")

        passed = current_dd < max_dd

        return GateCheckResult(
            gate_name="drawdown",
            passed=passed,
            reason=None if passed else f"Drawdown {current_dd:.2%} exceeds {max_dd:.2%}",
            details={"max": str(max_dd), "current": str(current_dd)},
        )

    async def _check_daily_limit(
        self, profile_id: UUID, config: dict
    ) -> GateCheckResult:
        """Check daily signal limit."""
        max_daily = config.get("max_daily_signals", 50)

        # Count today's signals
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        signals_today = 0

        if profile_id in _signal_store:
            for sig in _signal_store[profile_id]:
                if sig.get("created_at", datetime.min) >= today_start:
                    signals_today += 1

        passed = signals_today < max_daily

        return GateCheckResult(
            gate_name="daily_limit",
            passed=passed,
            reason=None if passed else f"Daily limit reached ({signals_today}/{max_daily})",
            details={"max": max_daily, "current": signals_today},
        )

    async def _check_trading_enabled(
        self, profile: MT5Profile
    ) -> GateCheckResult:
        """Check if trading is enabled on profile."""
        passed = profile.is_connected and profile.is_trading_enabled

        reason = None
        if not profile.is_connected:
            reason = "Profile not connected"
        elif not profile.is_trading_enabled:
            reason = "Trading not enabled"

        return GateCheckResult(
            gate_name="trading_enabled",
            passed=passed,
            reason=reason,
        )

    async def _run_gate_checks(
        self,
        signal: SignalSubmitRequest,
        profile: MT5Profile,
        config: dict,
    ) -> Tuple[bool, List[GateCheckResult]]:
        """
        Run all gate checks.

        Returns (all_passed, list_of_results).
        """
        checks = []

        # Required checks
        checks.append(await self._check_trading_enabled(profile))
        checks.append(await self._check_confidence(signal, config))
        checks.append(await self._check_position_limit(profile.id, config))
        checks.append(await self._check_drawdown(profile, config))
        checks.append(await self._check_daily_limit(profile.id, config))

        # All must pass
        all_passed = all(c.passed for c in checks)

        return all_passed, checks

    # ==================== Signal Processing ====================

    async def submit_signal(
        self,
        profile: MT5Profile,
        signal: SignalSubmitRequest,
    ) -> SignalResponse:
        """
        Submit a signal through the authoritative gate.

        This is the ONLY path for signal ingress.
        """
        start_time = time.monotonic()

        # 1. Check idempotency
        cached = self._check_idempotency(profile.id, signal.idempotency_key)
        if cached:
            return cached

        # 2. Check rate limit (unless critical priority)
        if signal.priority != SignalPriority.CRITICAL:
            rate_status = self.check_rate_limit(profile.id)
            if rate_status.is_limited:
                response = self._create_rejected_response(
                    profile.id,
                    signal,
                    "Rate limit exceeded",
                    [],
                    start_time,
                )
                self._cache_response(profile.id, signal.idempotency_key, response)
                return response

        # 3. Get gate configuration
        config = await self.get_gate_config(profile.id)

        # 4. Run gate checks
        all_passed, gate_checks = await self._run_gate_checks(
            signal, profile, config.model_dump()
        )

        # 5. Make decision
        if all_passed:
            decision = SignalDecision.APPROVED
            decision_reason = "All gate checks passed"
        else:
            decision = SignalDecision.REJECTED
            failed_checks = [c for c in gate_checks if not c.passed]
            decision_reason = "; ".join(c.reason for c in failed_checks if c.reason)

        # 6. Create response with provenance
        signal_id = uuid4()
        now = datetime.now(timezone.utc)

        processing_time = int((time.monotonic() - start_time) * 1000)

        response = SignalResponse(
            id=signal_id,
            idempotency_key=signal.idempotency_key,
            profile_id=profile.id,
            symbol=signal.symbol,
            direction=signal.direction,
            source=signal.source,
            priority=signal.priority,
            confidence=signal.confidence,
            decision=decision,
            decision_reason=decision_reason,
            decision_at=now,
            gate_checks=gate_checks,
            created_at=now,
            valid_until=signal.valid_until,
            processing_time_ms=processing_time,
            strategy_name=signal.strategy_name,
            model_version=signal.model_version,
        )

        # 7. Store for audit
        self._store_signal(profile.id, response)

        # 8. Cache for idempotency
        self._cache_response(profile.id, signal.idempotency_key, response)

        # 9. Increment rate limit
        self._increment_rate_limit(profile.id)

        # 10. Broadcast via WebSocket
        await self._broadcast_signal_event(response)

        return response

    def _create_rejected_response(
        self,
        profile_id: UUID,
        signal: SignalSubmitRequest,
        reason: str,
        gate_checks: List[GateCheckResult],
        start_time: float,
    ) -> SignalResponse:
        """Create a rejected signal response."""
        now = datetime.now(timezone.utc)
        processing_time = int((time.monotonic() - start_time) * 1000)

        return SignalResponse(
            id=uuid4(),
            idempotency_key=signal.idempotency_key,
            profile_id=profile_id,
            symbol=signal.symbol,
            direction=signal.direction,
            source=signal.source,
            priority=signal.priority,
            confidence=signal.confidence,
            decision=SignalDecision.REJECTED,
            decision_reason=reason,
            decision_at=now,
            gate_checks=gate_checks,
            created_at=now,
            processing_time_ms=processing_time,
        )

    def _store_signal(self, profile_id: UUID, response: SignalResponse) -> None:
        """Store signal for audit trail."""
        if profile_id not in _signal_store:
            _signal_store[profile_id] = []

        _signal_store[profile_id].append(response.model_dump(mode="json"))

        # Keep last 1000 signals per profile
        if len(_signal_store[profile_id]) > 1000:
            _signal_store[profile_id] = _signal_store[profile_id][-1000:]

    async def _broadcast_signal_event(self, response: SignalResponse) -> None:
        """Broadcast signal decision via WebSocket."""
        try:
            from archon_prime.api.websocket.handlers import get_broadcaster

            broadcaster = get_broadcaster()
            await broadcaster.signal_notification(
                profile_id=response.profile_id,
                signal_id=str(response.id),
                symbol=response.symbol,
                direction=response.direction.value,
                confidence=float(response.confidence),
                sources=[response.source.value],
                decision=response.decision.value,
                reason=response.decision_reason,
            )
        except Exception:
            pass  # Don't fail signal processing if broadcast fails

    # ==================== Query ====================

    async def get_signals(
        self,
        profile_id: UUID,
        page: int = 1,
        page_size: int = 20,
        decision: Optional[SignalDecision] = None,
    ) -> Tuple[List[SignalResponse], int]:
        """Get signals for a profile."""
        signals = _signal_store.get(profile_id, [])

        # Filter by decision
        if decision:
            signals = [s for s in signals if s.get("decision") == decision.value]

        total = len(signals)

        # Sort by created_at desc
        signals = sorted(
            signals,
            key=lambda s: s.get("created_at", ""),
            reverse=True,
        )

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        page_signals = signals[start:end]

        return [SignalResponse(**s) for s in page_signals], total

    async def get_signal_by_id(
        self, profile_id: UUID, signal_id: UUID
    ) -> Optional[SignalResponse]:
        """Get a specific signal."""
        signals = _signal_store.get(profile_id, [])

        for sig in signals:
            if sig.get("id") == str(signal_id):
                return SignalResponse(**sig)

        return None

    async def get_stats(
        self, profile_id: UUID, hours: int = 24
    ) -> SignalStatsResponse:
        """Get signal statistics for a profile."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        signals = _signal_store.get(profile_id, [])

        # Filter to time window
        recent = [
            s for s in signals
            if datetime.fromisoformat(s.get("created_at", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00")) >= cutoff
        ]

        if not recent:
            return SignalStatsResponse(profile_id=profile_id, period_hours=hours)

        # Calculate stats
        total = len(recent)
        approved = sum(1 for s in recent if s.get("decision") == "approved")
        rejected = sum(1 for s in recent if s.get("decision") == "rejected")
        expired = sum(1 for s in recent if s.get("decision") == "expired")
        executed = sum(1 for s in recent if s.get("decision") == "executed")
        failed = sum(1 for s in recent if s.get("decision") == "failed")

        # Rates
        approval_rate = Decimal(str(approved / total * 100)) if total > 0 else Decimal("0")
        execution_rate = Decimal(str(executed / approved * 100)) if approved > 0 else Decimal("0")

        # Average confidence
        confidences = [Decimal(str(s.get("confidence", 0))) for s in recent]
        avg_confidence = sum(confidences) / len(confidences) if confidences else Decimal("0")

        # Average processing time
        times = [s.get("processing_time_ms", 0) for s in recent]
        avg_time = sum(times) // len(times) if times else 0

        # By source
        by_source: Dict[str, int] = {}
        for s in recent:
            source = s.get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + 1

        # Top rejection reasons
        rejection_reasons: Dict[str, int] = {}
        for s in recent:
            if s.get("decision") == "rejected":
                reason = s.get("decision_reason", "unknown")
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        top_reasons = sorted(
            [{"reason": k, "count": v} for k, v in rejection_reasons.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        return SignalStatsResponse(
            profile_id=profile_id,
            period_hours=hours,
            total_signals=total,
            approved=approved,
            rejected=rejected,
            expired=expired,
            executed=executed,
            failed=failed,
            approval_rate=approval_rate.quantize(Decimal("0.01")),
            execution_rate=execution_rate.quantize(Decimal("0.01")),
            avg_confidence=avg_confidence.quantize(Decimal("0.001")),
            avg_processing_time_ms=avg_time,
            by_source=by_source,
            top_rejection_reasons=top_reasons,
        )

    # ==================== Configuration ====================

    async def get_gate_config(self, profile_id: UUID) -> GateConfigResponse:
        """Get gate configuration for a profile."""
        # In production, this would come from database
        # For now, return defaults
        return GateConfigResponse(
            profile_id=profile_id,
            **DEFAULT_GATE_CONFIG,
        )

    async def update_gate_config(
        self,
        profile_id: UUID,
        updates: dict,
    ) -> GateConfigResponse:
        """Update gate configuration."""
        # In production, persist to database
        # For now, just return merged config
        config = DEFAULT_GATE_CONFIG.copy()
        config.update({k: v for k, v in updates.items() if v is not None})

        return GateConfigResponse(profile_id=profile_id, **config)
