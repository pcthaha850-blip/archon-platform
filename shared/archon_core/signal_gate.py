"""
ARCHON RI v6.3 - Signal Gate Consensus Engine
===============================================

Validates trading signals through multiple approval layers before execution.
Implements the "Signal Gate" pattern requiring consensus between:
    1. Strategy signal generation
    2. Risk engine approval
    3. AI validation (Guardian)
    4. Market condition checks

A trade is only executed when ALL gates pass.

Author: ARCHON RI Development Team
Version: 6.3.0
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ARCHON_SignalGate")


class GateResult(Enum):
    """Result of a gate check."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"  # Gate not applicable


class GateType(Enum):
    """Types of validation gates."""

    STRATEGY = "STRATEGY"
    RISK_ENGINE = "RISK_ENGINE"
    AI_GUARDIAN = "AI_GUARDIAN"
    MARKET_CONDITIONS = "MARKET_CONDITIONS"
    CORRELATION = "CORRELATION"
    NEWS_FILTER = "NEWS_FILTER"
    PANIC_HEDGE = "PANIC_HEDGE"


@dataclass
class GateDecision:
    """Decision from a single gate."""

    gate: GateType
    result: GateResult
    reason: str
    confidence: float = 1.0  # 0-1 confidence score
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalGateConfig:
    """Configuration for Signal Gate."""

    # Consensus requirements
    require_ai_consensus: bool = True
    min_confidence: float = 0.65  # Minimum confidence to proceed
    max_signal_age_sec: int = 300  # Signal expires after 5 minutes

    # Gate weights (for weighted consensus)
    gate_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "STRATEGY": 1.0,
            "RISK_ENGINE": 1.5,  # Higher weight for risk
            "AI_GUARDIAN": 1.0,
            "MARKET_CONDITIONS": 0.8,
            "CORRELATION": 0.7,
            "NEWS_FILTER": 1.2,  # Important filter
            "PANIC_HEDGE": 2.0,  # Critical - highest weight
        }
    )

    # Logging
    log_decisions: bool = True
    log_rejections: bool = True


@dataclass
class Signal:
    """A trading signal to be validated."""

    signal_id: str
    pair: str
    direction: int  # +1 long, -1 short
    strategy: str
    z_score: float
    confidence: float
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, max_age_sec: int) -> bool:
        """Check if signal has expired."""
        now = datetime.now(timezone.utc)
        age = (now - self.created_at).total_seconds()
        return age > max_age_sec


@dataclass
class ConsensusResult:
    """Final consensus result from all gates."""

    signal_id: str
    approved: bool
    decisions: List[GateDecision]
    overall_confidence: float
    rejection_reason: Optional[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_failed_gates(self) -> List[GateType]:
        """Get list of gates that failed."""
        return [d.gate for d in self.decisions if d.result == GateResult.FAIL]


class SignalGate:
    """
    Consensus engine for trading signal validation.

    Validates signals through multiple gates and only approves
    when all required gates pass with sufficient confidence.

    Example:
        gate = SignalGate(config)

        # Register validation gates
        gate.register_gate(GateType.RISK_ENGINE, risk_validator)
        gate.register_gate(GateType.AI_GUARDIAN, ai_validator)

        # Validate a signal
        signal = Signal(
            signal_id="sig_001",
            pair="EURUSD",
            direction=1,
            strategy="TSM",
            z_score=2.5,
            confidence=0.75,
            created_at=datetime.now(timezone.utc)
        )

        result = gate.validate(signal)

        if result.approved:
            execute_trade(signal)
        else:
            logger.info(f"Signal rejected: {result.rejection_reason}")
    """

    def __init__(self, config: Optional[SignalGateConfig] = None):
        self.cfg = config or SignalGateConfig()

        # Registered gate validators
        self._gates: Dict[GateType, Callable[[Signal], GateDecision]] = {}

        # Required gates (must pass)
        self._required_gates: set = {
            GateType.RISK_ENGINE,
            GateType.PANIC_HEDGE,
        }

        # Decision history
        self._decision_history: List[ConsensusResult] = []

        # Statistics
        self._stats = {
            "total_signals": 0,
            "approved": 0,
            "rejected": 0,
            "rejections_by_gate": {},
        }

        logger.info(
            f"SignalGate initialized: min_confidence={self.cfg.min_confidence}, "
            f"ai_consensus={self.cfg.require_ai_consensus}"
        )

    def register_gate(
        self,
        gate_type: GateType,
        validator: Callable[[Signal], GateDecision],
        required: bool = False,
    ) -> None:
        """
        Register a validation gate.

        Args:
            gate_type: Type of gate
            validator: Function that takes Signal and returns GateDecision
            required: If True, this gate must pass for approval
        """
        self._gates[gate_type] = validator
        if required:
            self._required_gates.add(gate_type)
        logger.debug(f"Gate registered: {gate_type.value} (required={required})")

    def unregister_gate(self, gate_type: GateType) -> None:
        """Remove a validation gate."""
        self._gates.pop(gate_type, None)
        self._required_gates.discard(gate_type)

    def validate(self, signal: Signal) -> ConsensusResult:
        """
        Validate a signal through all registered gates.

        Args:
            signal: The signal to validate

        Returns:
            ConsensusResult with approval status and details
        """
        self._stats["total_signals"] += 1

        # Check signal expiry
        if signal.is_expired(self.cfg.max_signal_age_sec):
            return self._create_rejection(
                signal, "Signal expired", []
            )

        # Run all gates
        decisions: List[GateDecision] = []

        for gate_type, validator in self._gates.items():
            try:
                decision = validator(signal)
                decisions.append(decision)
            except Exception as e:
                logger.error(f"Gate {gate_type.value} error: {e}")
                decisions.append(
                    GateDecision(
                        gate=gate_type,
                        result=GateResult.FAIL,
                        reason=f"Gate error: {str(e)}",
                        confidence=0.0,
                    )
                )

        # Check required gates
        for gate_type in self._required_gates:
            gate_decision = next(
                (d for d in decisions if d.gate == gate_type), None
            )
            if gate_decision and gate_decision.result == GateResult.FAIL:
                return self._create_rejection(
                    signal,
                    f"Required gate failed: {gate_type.value} - {gate_decision.reason}",
                    decisions,
                )

        # Check AI consensus if required
        if self.cfg.require_ai_consensus:
            ai_decision = next(
                (d for d in decisions if d.gate == GateType.AI_GUARDIAN), None
            )
            if ai_decision and ai_decision.result == GateResult.FAIL:
                return self._create_rejection(
                    signal,
                    f"AI Guardian rejected: {ai_decision.reason}",
                    decisions,
                )

        # Calculate weighted confidence
        overall_confidence = self._calculate_weighted_confidence(decisions)

        # Check minimum confidence
        if overall_confidence < self.cfg.min_confidence:
            return self._create_rejection(
                signal,
                f"Confidence too low: {overall_confidence:.2f} < {self.cfg.min_confidence}",
                decisions,
            )

        # All checks passed
        self._stats["approved"] += 1

        result = ConsensusResult(
            signal_id=signal.signal_id,
            approved=True,
            decisions=decisions,
            overall_confidence=overall_confidence,
            rejection_reason=None,
        )

        self._decision_history.append(result)

        if self.cfg.log_decisions:
            logger.info(
                f"Signal APPROVED: {signal.signal_id} {signal.pair} "
                f"{signal.strategy} conf={overall_confidence:.2f}"
            )

        return result

    def _create_rejection(
        self, signal: Signal, reason: str, decisions: List[GateDecision]
    ) -> ConsensusResult:
        """Create a rejection result."""
        self._stats["rejected"] += 1

        # Track rejection by gate
        for decision in decisions:
            if decision.result == GateResult.FAIL:
                gate_name = decision.gate.value
                self._stats["rejections_by_gate"][gate_name] = (
                    self._stats["rejections_by_gate"].get(gate_name, 0) + 1
                )

        result = ConsensusResult(
            signal_id=signal.signal_id,
            approved=False,
            decisions=decisions,
            overall_confidence=0.0,
            rejection_reason=reason,
        )

        self._decision_history.append(result)

        if self.cfg.log_rejections:
            logger.warning(
                f"Signal REJECTED: {signal.signal_id} {signal.pair} "
                f"{signal.strategy} - {reason}"
            )

        return result

    def _calculate_weighted_confidence(
        self, decisions: List[GateDecision]
    ) -> float:
        """Calculate weighted average confidence from all gates."""
        total_weight = 0.0
        weighted_sum = 0.0

        for decision in decisions:
            if decision.result == GateResult.SKIP:
                continue

            weight = self.cfg.gate_weights.get(decision.gate.value, 1.0)

            if decision.result == GateResult.PASS:
                weighted_sum += weight * decision.confidence
            # FAIL contributes 0

            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def get_statistics(self) -> Dict[str, Any]:
        """Get Signal Gate statistics."""
        return {
            "total_signals": self._stats["total_signals"],
            "approved": self._stats["approved"],
            "rejected": self._stats["rejected"],
            "approval_rate": (
                self._stats["approved"] / self._stats["total_signals"]
                if self._stats["total_signals"] > 0
                else 0.0
            ),
            "rejections_by_gate": self._stats["rejections_by_gate"].copy(),
            "registered_gates": [g.value for g in self._gates.keys()],
            "required_gates": [g.value for g in self._required_gates],
        }

    def get_recent_decisions(self, limit: int = 50) -> List[ConsensusResult]:
        """Get recent consensus decisions."""
        return self._decision_history[-limit:]

    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self._stats = {
            "total_signals": 0,
            "approved": 0,
            "rejected": 0,
            "rejections_by_gate": {},
        }
        logger.info("SignalGate statistics reset")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "GateResult",
    "GateType",
    "GateDecision",
    "SignalGateConfig",
    "Signal",
    "ConsensusResult",
    "SignalGate",
]
