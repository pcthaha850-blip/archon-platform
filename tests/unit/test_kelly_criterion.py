"""
Tests for Kelly Criterion Position Sizer
=========================================

Tests the DynamicKellySizer module for correct position sizing
based on signal strength (Z-score).
"""

import pytest
from shared.archon_core.kelly_criterion import KellyConfig, KellyCriterion


class TestKellyFraction:
    """Tests for Kelly fraction calculation."""

    def test_zero_zscore_returns_zero(self):
        """Z-score of 0 should return 0 Kelly fraction."""
        kelly = KellyCriterion()
        assert kelly.kelly_fraction_from_z(0.0) == 0.0

    def test_below_minimum_zscore_returns_zero(self):
        """Z-score below minimum threshold returns 0."""
        kelly = KellyCriterion()
        # Default min_z is 1.25
        assert kelly.kelly_fraction_from_z(1.0) == 0.0
        assert kelly.kelly_fraction_from_z(1.24) == 0.0

    def test_at_minimum_zscore_returns_nonzero(self):
        """Z-score at minimum threshold returns non-zero."""
        kelly = KellyCriterion()
        # Default: min_z=1.25, scale=0.15
        fraction = kelly.kelly_fraction_from_z(1.25)
        expected = 0.15 * 1.25  # 0.1875
        assert fraction == pytest.approx(expected, rel=0.01)

    def test_kelly_fraction_scales_with_zscore(self):
        """Higher Z-score should give higher Kelly fraction."""
        kelly = KellyCriterion()
        f1 = kelly.kelly_fraction_from_z(1.5)
        f2 = kelly.kelly_fraction_from_z(2.0)
        f3 = kelly.kelly_fraction_from_z(2.5)
        assert f1 < f2 < f3

    def test_kelly_fraction_capped(self):
        """Kelly fraction should be capped at kelly_cap."""
        kelly = KellyCriterion()
        # Very high Z-score should hit cap
        fraction = kelly.kelly_fraction_from_z(10.0)
        assert fraction == kelly.cfg.kelly_cap

    def test_negative_zscore_uses_absolute(self):
        """Negative Z-score should use absolute value."""
        kelly = KellyCriterion()
        f_pos = kelly.kelly_fraction_from_z(2.0)
        f_neg = kelly.kelly_fraction_from_z(-2.0)
        assert f_pos == f_neg


class TestRiskPercentage:
    """Tests for risk percentage calculation."""

    def test_zero_kelly_returns_zero_risk(self):
        """Zero Kelly fraction should return zero risk."""
        kelly = KellyCriterion()
        assert kelly.risk_pct_from_kelly(0.0) == 0.0

    def test_risk_pct_in_valid_range(self):
        """Risk percentage should be between min and max."""
        kelly = KellyCriterion()
        for z in [1.5, 2.0, 2.5, 3.0]:
            f = kelly.kelly_fraction_from_z(z)
            risk = kelly.risk_pct_from_kelly(f)
            assert kelly.cfg.min_risk_per_trade_pct <= risk <= kelly.cfg.max_risk_per_trade_pct

    def test_max_kelly_gives_max_risk(self):
        """Maximum Kelly fraction should give maximum risk."""
        kelly = KellyCriterion()
        risk = kelly.risk_pct_from_kelly(kelly.cfg.kelly_cap)
        assert risk == pytest.approx(kelly.cfg.max_risk_per_trade_pct, rel=0.01)


class TestLotSizing:
    """Tests for lot size calculation."""

    def test_lot_size_from_risk(self, account_equity, pip_value, stop_distance):
        """Test basic lot size calculation."""
        kelly = KellyCriterion()
        risk_pct = 0.5  # 0.5% risk

        lots = kelly.lot_size_from_risk(
            risk_pct=risk_pct,
            account_equity=account_equity,
            pip_value_per_lot=pip_value,
            stop_distance_pips=stop_distance,
        )

        # Expected: (500 * 0.005) / (10 * 50) = 2.5 / 500 = 0.005 -> 0.01 (min lot)
        assert lots >= kelly.cfg.min_lot
        assert lots <= kelly.cfg.max_lot

    def test_zero_risk_returns_zero_lots(self, account_equity, pip_value, stop_distance):
        """Zero risk should return zero lots."""
        kelly = KellyCriterion()
        lots = kelly.lot_size_from_risk(0.0, account_equity, pip_value, stop_distance)
        assert lots == 0.0

    def test_invalid_inputs_return_zero(self):
        """Invalid inputs should return zero lots."""
        kelly = KellyCriterion()

        # Zero equity
        assert kelly.lot_size_from_risk(0.5, 0.0, 10.0, 50.0) == 0.0

        # Zero pip value
        assert kelly.lot_size_from_risk(0.5, 500.0, 0.0, 50.0) == 0.0

        # Zero stop distance
        assert kelly.lot_size_from_risk(0.5, 500.0, 10.0, 0.0) == 0.0

    def test_lot_size_respects_minimum(self, account_equity, pip_value, stop_distance):
        """Lot size should not be below minimum."""
        kelly = KellyCriterion()
        # Very small risk
        lots = kelly.lot_size_from_risk(0.01, account_equity, pip_value, stop_distance)
        # Should either be 0 or at least min_lot
        assert lots == 0.0 or lots >= kelly.cfg.min_lot


class TestFullSizing:
    """Tests for complete sizing workflow."""

    def test_compute_full_sizing(self, account_equity, pip_value, stop_distance):
        """Test complete sizing from Z-score to lots."""
        kelly = KellyCriterion()

        result = kelly.compute_full_sizing(
            z_score=2.0,
            account_equity=account_equity,
            pip_value_per_lot=pip_value,
            stop_distance_pips=stop_distance,
        )

        assert "kelly_fraction" in result
        assert "risk_pct_base" in result
        assert "risk_pct_scaled" in result
        assert "lots" in result
        assert "risk_amount" in result

        assert result["kelly_fraction"] > 0
        assert result["lots"] >= 0

    def test_scaling_factor_reduces_size(self, account_equity, pip_value, stop_distance):
        """Scaling factor should reduce position size."""
        kelly = KellyCriterion()

        result_full = kelly.compute_full_sizing(
            z_score=2.0,
            account_equity=account_equity,
            pip_value_per_lot=pip_value,
            stop_distance_pips=stop_distance,
            scaling_factor=1.0,
        )

        result_scaled = kelly.compute_full_sizing(
            z_score=2.0,
            account_equity=account_equity,
            pip_value_per_lot=pip_value,
            stop_distance_pips=stop_distance,
            scaling_factor=0.5,
        )

        assert result_scaled["risk_pct_scaled"] < result_full["risk_pct_scaled"]

    def test_dd_reduction_reduces_size(self, account_equity, pip_value, stop_distance):
        """Drawdown reduction should reduce position size."""
        kelly = KellyCriterion()

        result_normal = kelly.compute_full_sizing(
            z_score=2.0,
            account_equity=account_equity,
            pip_value_per_lot=pip_value,
            stop_distance_pips=stop_distance,
            dd_reduction=False,
        )

        result_dd = kelly.compute_full_sizing(
            z_score=2.0,
            account_equity=account_equity,
            pip_value_per_lot=pip_value,
            stop_distance_pips=stop_distance,
            dd_reduction=True,
        )

        assert result_dd["risk_pct_scaled"] < result_normal["risk_pct_scaled"]


class TestConfiguration:
    """Tests for custom configuration."""

    def test_custom_config(self):
        """Test with custom configuration."""
        config = KellyConfig(
            kelly_min_z=2.0,
            kelly_scale=0.1,
            kelly_cap=0.3,
            min_risk_per_trade_pct=0.1,
            max_risk_per_trade_pct=0.3,
        )
        kelly = KellyCriterion(config)

        # Z=1.5 should return 0 (below min_z=2.0)
        assert kelly.kelly_fraction_from_z(1.5) == 0.0

        # Z=2.5 should work
        fraction = kelly.kelly_fraction_from_z(2.5)
        assert fraction > 0
        assert fraction <= config.kelly_cap
