"""
Tests for Signal Gate Consensus Engine
======================================

Tests the multi-gate validation system for trade signals.
"""

import pytest
from datetime import datetime, timezone, timedelta
from shared.archon_core.signal_gate import (
    GateResult,
    GateType,
    GateDecision,
    SignalGateConfig,
    Signal,
    ConsensusResult,
    SignalGate,
)


@pytest.fixture
def signal_gate():
    """Create a Signal Gate with default config."""
    return SignalGate()


@pytest.fixture
def valid_signal():
    """Create a valid test signal."""
    return Signal(
        signal_id="test_001",
        pair="EURUSD",
        direction=1,
        strategy="TSM",
        z_score=2.5,
        confidence=0.75,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def expired_signal():
    """Create an expired signal."""
    return Signal(
        signal_id="test_expired",
        pair="EURUSD",
        direction=1,
        strategy="TSM",
        z_score=2.0,
        confidence=0.7,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )


def passing_gate(signal: Signal) -> GateDecision:
    """A gate validator that always passes."""
    return GateDecision(
        gate=GateType.STRATEGY,
        result=GateResult.PASS,
        reason="Test pass",
        confidence=0.9,
    )


def failing_gate(signal: Signal) -> GateDecision:
    """A gate validator that always fails."""
    return GateDecision(
        gate=GateType.RISK_ENGINE,
        result=GateResult.FAIL,
        reason="Test fail",
        confidence=0.0,
    )


def skipping_gate(signal: Signal) -> GateDecision:
    """A gate validator that skips."""
    return GateDecision(
        gate=GateType.NEWS_FILTER,
        result=GateResult.SKIP,
        reason="Not applicable",
        confidence=0.0,
    )


class TestSignalExpiry:
    """Tests for signal expiration."""

    def test_valid_signal_not_expired(self, valid_signal):
        """Fresh signal should not be expired."""
        assert not valid_signal.is_expired(300)

    def test_old_signal_is_expired(self, expired_signal):
        """Old signal should be expired."""
        assert expired_signal.is_expired(300)

    def test_signal_gate_rejects_expired(self, signal_gate, expired_signal):
        """Signal Gate should reject expired signals."""
        result = signal_gate.validate(expired_signal)
        assert not result.approved
        assert "expired" in result.rejection_reason.lower()


class TestGateRegistration:
    """Tests for gate registration."""

    def test_register_gate(self, signal_gate):
        """Should register a gate."""
        signal_gate.register_gate(GateType.STRATEGY, passing_gate)
        stats = signal_gate.get_statistics()
        assert "STRATEGY" in stats["registered_gates"]

    def test_register_required_gate(self, signal_gate):
        """Should register a required gate."""
        signal_gate.register_gate(GateType.AI_GUARDIAN, passing_gate, required=True)
        stats = signal_gate.get_statistics()
        assert "AI_GUARDIAN" in stats["required_gates"]

    def test_unregister_gate(self, signal_gate):
        """Should unregister a gate."""
        signal_gate.register_gate(GateType.NEWS_FILTER, passing_gate)
        signal_gate.unregister_gate(GateType.NEWS_FILTER)
        stats = signal_gate.get_statistics()
        assert "NEWS_FILTER" not in stats["registered_gates"]


class TestValidation:
    """Tests for signal validation."""

    def test_validation_with_all_passing_gates(self, signal_gate, valid_signal):
        """Signal should be approved when all gates pass."""
        # Register passing gates for required gates
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.9,
            ),
        )
        signal_gate.register_gate(
            GateType.PANIC_HEDGE,
            lambda s: GateDecision(
                gate=GateType.PANIC_HEDGE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.95,
            ),
        )

        # Disable AI consensus for this test
        signal_gate.cfg.require_ai_consensus = False

        result = signal_gate.validate(valid_signal)
        assert result.approved
        assert result.overall_confidence > 0

    def test_validation_fails_on_required_gate_fail(self, signal_gate, valid_signal):
        """Signal should be rejected when required gate fails."""
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.FAIL,
                reason="Risk too high",
                confidence=0.0,
            ),
        )

        result = signal_gate.validate(valid_signal)
        assert not result.approved
        assert "RISK_ENGINE" in result.rejection_reason

    def test_validation_fails_on_panic_hedge_fail(self, signal_gate, valid_signal):
        """Signal should be rejected when panic hedge fails."""
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.9,
            ),
        )
        signal_gate.register_gate(
            GateType.PANIC_HEDGE,
            lambda s: GateDecision(
                gate=GateType.PANIC_HEDGE,
                result=GateResult.FAIL,
                reason="Panic mode active",
                confidence=0.0,
            ),
        )

        result = signal_gate.validate(valid_signal)
        assert not result.approved
        assert "PANIC_HEDGE" in result.rejection_reason

    def test_ai_consensus_rejection(self, signal_gate, valid_signal):
        """Signal should be rejected when AI Guardian fails with consensus enabled."""
        signal_gate.cfg.require_ai_consensus = True

        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.9,
            ),
        )
        signal_gate.register_gate(
            GateType.PANIC_HEDGE,
            lambda s: GateDecision(
                gate=GateType.PANIC_HEDGE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.9,
            ),
        )
        signal_gate.register_gate(
            GateType.AI_GUARDIAN,
            lambda s: GateDecision(
                gate=GateType.AI_GUARDIAN,
                result=GateResult.FAIL,
                reason="AI rejected",
                confidence=0.0,
            ),
        )

        result = signal_gate.validate(valid_signal)
        assert not result.approved
        assert "AI Guardian" in result.rejection_reason


class TestConfidenceCalculation:
    """Tests for confidence calculation."""

    def test_confidence_below_minimum_rejected(self, signal_gate, valid_signal):
        """Signal should be rejected when confidence is too low."""
        signal_gate.cfg.min_confidence = 0.8
        signal_gate.cfg.require_ai_consensus = False

        # Register low-confidence gates
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.3,
            ),
        )
        signal_gate.register_gate(
            GateType.PANIC_HEDGE,
            lambda s: GateDecision(
                gate=GateType.PANIC_HEDGE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.3,
            ),
        )

        result = signal_gate.validate(valid_signal)
        assert not result.approved
        assert "Confidence too low" in result.rejection_reason

    def test_skip_gates_excluded_from_confidence(self, signal_gate, valid_signal):
        """Skipped gates should not affect confidence."""
        signal_gate.cfg.require_ai_consensus = False

        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.9,
            ),
        )
        signal_gate.register_gate(
            GateType.PANIC_HEDGE,
            lambda s: GateDecision(
                gate=GateType.PANIC_HEDGE,
                result=GateResult.PASS,
                reason="OK",
                confidence=0.9,
            ),
        )
        signal_gate.register_gate(
            GateType.NEWS_FILTER,
            lambda s: GateDecision(
                gate=GateType.NEWS_FILTER,
                result=GateResult.SKIP,
                reason="Not applicable",
                confidence=0.0,
            ),
        )

        result = signal_gate.validate(valid_signal)
        # Should still pass despite skipped gate with 0 confidence
        assert result.approved


class TestStatistics:
    """Tests for statistics tracking."""

    def test_statistics_updated_on_approval(self, signal_gate, valid_signal):
        """Statistics should track approvals."""
        signal_gate.cfg.require_ai_consensus = False
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE, result=GateResult.PASS, reason="OK", confidence=0.9
            ),
        )
        signal_gate.register_gate(
            GateType.PANIC_HEDGE,
            lambda s: GateDecision(
                gate=GateType.PANIC_HEDGE, result=GateResult.PASS, reason="OK", confidence=0.9
            ),
        )

        signal_gate.validate(valid_signal)
        stats = signal_gate.get_statistics()

        assert stats["total_signals"] == 1
        assert stats["approved"] == 1
        assert stats["rejected"] == 0

    def test_statistics_updated_on_rejection(self, signal_gate, valid_signal):
        """Statistics should track rejections."""
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.FAIL,
                reason="Rejected",
                confidence=0.0,
            ),
        )

        signal_gate.validate(valid_signal)
        stats = signal_gate.get_statistics()

        assert stats["total_signals"] == 1
        assert stats["approved"] == 0
        assert stats["rejected"] == 1
        assert "RISK_ENGINE" in stats["rejections_by_gate"]

    def test_reset_statistics(self, signal_gate, valid_signal):
        """Should reset statistics counters."""
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE,
                result=GateResult.FAIL,
                reason="Rejected",
                confidence=0.0,
            ),
        )

        signal_gate.validate(valid_signal)
        signal_gate.reset_statistics()
        stats = signal_gate.get_statistics()

        assert stats["total_signals"] == 0
        assert stats["approved"] == 0
        assert stats["rejected"] == 0


class TestConsensusResult:
    """Tests for ConsensusResult dataclass."""

    def test_get_failed_gates(self):
        """Should return list of failed gates."""
        decisions = [
            GateDecision(
                gate=GateType.RISK_ENGINE, result=GateResult.PASS, reason="OK"
            ),
            GateDecision(
                gate=GateType.AI_GUARDIAN, result=GateResult.FAIL, reason="Failed"
            ),
            GateDecision(
                gate=GateType.NEWS_FILTER, result=GateResult.FAIL, reason="Failed"
            ),
        ]

        result = ConsensusResult(
            signal_id="test",
            approved=False,
            decisions=decisions,
            overall_confidence=0.0,
            rejection_reason="Test",
        )

        failed = result.get_failed_gates()
        assert GateType.AI_GUARDIAN in failed
        assert GateType.NEWS_FILTER in failed
        assert GateType.RISK_ENGINE not in failed


class TestGateErrors:
    """Tests for gate error handling."""

    def test_gate_exception_handled(self, signal_gate, valid_signal):
        """Gate exceptions should be handled gracefully."""
        def error_gate(signal):
            raise ValueError("Gate error")

        signal_gate.register_gate(GateType.STRATEGY, error_gate)
        signal_gate.register_gate(
            GateType.RISK_ENGINE,
            lambda s: GateDecision(
                gate=GateType.RISK_ENGINE, result=GateResult.PASS, reason="OK", confidence=0.9
            ),
        )
        signal_gate.register_gate(
            GateType.PANIC_HEDGE,
            lambda s: GateDecision(
                gate=GateType.PANIC_HEDGE, result=GateResult.PASS, reason="OK", confidence=0.9
            ),
        )

        # Should not raise, but should record failure
        result = signal_gate.validate(valid_signal)
        # The validation will complete, but STRATEGY gate will be recorded as failed
        assert isinstance(result, ConsensusResult)
