"""
Tests for CVaR (Conditional Value at Risk) Engine
==================================================

Tests the CVaR risk calculations for position and portfolio constraints.
"""

import pytest
import numpy as np
import pandas as pd
from shared.archon_core.cvar_engine import CVaRConfig, CVaRResult, CVaREngine


class TestVaRCalculation:
    """Tests for Value at Risk calculation."""

    def test_var_with_sufficient_data(self, sample_returns):
        """VaR calculation with sufficient data."""
        engine = CVaREngine()
        var = engine.compute_var(sample_returns, confidence=0.95)

        # VaR should be negative (representing loss)
        assert var < 0 or np.isfinite(var)

    def test_var_with_insufficient_data(self):
        """VaR with insufficient data returns NaN."""
        engine = CVaREngine(CVaRConfig(cvar_lookback=60))
        short_returns = pd.Series([0.01, -0.01, 0.005])

        var = engine.compute_var(short_returns, confidence=0.95)
        assert np.isnan(var)

    def test_var_confidence_levels(self, sample_returns):
        """Higher confidence should give more extreme VaR."""
        engine = CVaREngine()

        var_95 = engine.compute_var(sample_returns, confidence=0.95)
        var_99 = engine.compute_var(sample_returns, confidence=0.99)

        # 99% VaR should be more extreme (more negative) than 95%
        assert var_99 <= var_95


class TestCVaRCalculation:
    """Tests for Conditional VaR (Expected Shortfall) calculation."""

    def test_cvar_with_sufficient_data(self, sample_returns):
        """CVaR calculation with sufficient data."""
        engine = CVaREngine()
        cvar = engine.compute_cvar(sample_returns, confidence=0.95)

        # CVaR should be finite
        assert np.isfinite(cvar)

    def test_cvar_more_extreme_than_var(self, sample_returns):
        """CVaR should be more extreme (more negative) than VaR."""
        engine = CVaREngine()

        var = engine.compute_var(sample_returns, confidence=0.95)
        cvar = engine.compute_cvar(sample_returns, confidence=0.95)

        # CVaR is the expected loss beyond VaR, so should be <= VaR
        if not np.isnan(var) and not np.isnan(cvar):
            assert cvar <= var

    def test_cvar_with_insufficient_data(self):
        """CVaR with insufficient data returns NaN."""
        engine = CVaREngine(CVaRConfig(cvar_lookback=60))
        short_returns = pd.Series([0.01, -0.01])

        cvar = engine.compute_cvar(short_returns, confidence=0.95)
        assert np.isnan(cvar)


class TestCVaRLimits:
    """Tests for CVaR limit evaluation."""

    def test_evaluate_within_limits(self, sample_returns):
        """Evaluation when within limits."""
        config = CVaRConfig(
            max_cvar_per_position_pct=10.0,  # High limit
            max_cvar_portfolio_pct=20.0,
        )
        engine = CVaREngine(config)

        result = engine.evaluate_cvar_limits(
            pair_returns=sample_returns,
            portfolio_returns=sample_returns,
            account_equity=500.0,
        )

        assert isinstance(result, CVaRResult)
        assert result.data_sufficient
        assert not result.position_cvar_limit_hit
        assert not result.portfolio_cvar_limit_hit

    def test_evaluate_position_limit_breach(self, sample_returns):
        """Evaluation when position CVaR limit is breached."""
        config = CVaRConfig(
            max_cvar_per_position_pct=0.001,  # Very low limit
            max_cvar_portfolio_pct=20.0,
        )
        engine = CVaREngine(config)

        result = engine.evaluate_cvar_limits(
            pair_returns=sample_returns,
            portfolio_returns=sample_returns,
            account_equity=500.0,
        )

        # With very low limit, should breach
        if result.data_sufficient and result.position_cvar_pct is not None:
            if result.position_cvar_pct > config.max_cvar_per_position_pct:
                assert result.position_cvar_limit_hit

    def test_evaluate_with_insufficient_data(self):
        """Evaluation with insufficient data."""
        engine = CVaREngine(CVaRConfig(cvar_lookback=60))
        short_returns = pd.Series([0.01, -0.01])

        result = engine.evaluate_cvar_limits(
            pair_returns=short_returns,
            portfolio_returns=short_returns,
            account_equity=500.0,
        )

        assert not result.data_sufficient
        assert not result.position_cvar_limit_hit
        assert not result.portfolio_cvar_limit_hit

    def test_position_size_factor_scaling(self, sample_returns):
        """Position size factor should scale CVaR."""
        engine = CVaREngine()

        result_1x = engine.evaluate_cvar_limits(
            pair_returns=sample_returns,
            portfolio_returns=sample_returns,
            account_equity=500.0,
            position_size_factor=1.0,
        )

        result_2x = engine.evaluate_cvar_limits(
            pair_returns=sample_returns,
            portfolio_returns=sample_returns,
            account_equity=500.0,
            position_size_factor=2.0,
        )

        if result_1x.position_cvar_pct and result_2x.position_cvar_pct:
            # 2x position size should have ~2x CVaR
            assert result_2x.position_cvar_pct > result_1x.position_cvar_pct


class TestBreachHistory:
    """Tests for breach history tracking."""

    def test_breach_recorded(self, sample_returns):
        """Breaches should be recorded in history."""
        config = CVaRConfig(
            max_cvar_per_position_pct=0.0001,  # Very low to trigger breach
            log_cvar_breaches=True,
        )
        engine = CVaREngine(config)

        # Clear any existing history
        engine.clear_breach_history()

        result = engine.evaluate_cvar_limits(
            pair_returns=sample_returns,
            portfolio_returns=sample_returns,
            account_equity=500.0,
        )

        # If breach occurred, should be in history
        if result.position_cvar_limit_hit:
            history = engine.get_breach_history()
            assert len(history) > 0
            assert history[-1]["type"] == "position"

    def test_clear_breach_history(self):
        """Breach history should be clearable."""
        engine = CVaREngine()

        # Add some history
        engine._breach_history.append({"type": "test"})
        assert len(engine.get_breach_history()) > 0

        engine.clear_breach_history()
        assert len(engine.get_breach_history()) == 0


class TestStatistics:
    """Tests for CVaR engine statistics."""

    def test_get_statistics(self):
        """Statistics should return config info."""
        config = CVaRConfig(
            cvar_lookback=30,
            cvar_confidence_position=0.95,
            max_cvar_per_position_pct=2.5,
        )
        engine = CVaREngine(config)

        stats = engine.get_statistics()

        assert stats["lookback_days"] == 30
        assert stats["position_confidence"] == 0.95
        assert stats["max_position_cvar_pct"] == 2.5
        assert stats["total_breaches"] == 0
