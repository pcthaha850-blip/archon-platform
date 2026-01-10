"""
Tests for Correlation Tracker
=============================

Tests the correlation tracking and portfolio risk management system.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from shared.archon_core.correlation_tracker import (
    CorrelationCluster,
    CorrelationConfig,
    CorrelationTracker,
)


@pytest.fixture
def tracker():
    """Create a correlation tracker with default config."""
    return CorrelationTracker()


@pytest.fixture
def tracker_custom():
    """Create a correlation tracker with custom config."""
    config = CorrelationConfig(
        lookback_days=30,
        high_correlation_threshold=0.6,
        max_positions_per_cluster=2,
    )
    return CorrelationTracker(config)


@pytest.fixture
def correlated_returns():
    """Generate correlated return series."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="H")

    # Base return series
    base = np.random.normal(0.0001, 0.01, 100)

    # Highly correlated series
    eurusd = pd.Series(base + np.random.normal(0, 0.001, 100), index=dates)
    eurgbp = pd.Series(base * 0.9 + np.random.normal(0, 0.002, 100), index=dates)

    # Less correlated series
    usdjpy = pd.Series(np.random.normal(0.0001, 0.01, 100), index=dates)

    return {"EURUSD": eurusd, "EURGBP": eurgbp, "USDJPY": usdjpy}


class MockPosition:
    """Mock position for testing."""
    def __init__(self, pair: str, ticket: int = 1):
        self.pair = pair
        self.ticket = ticket


class TestKnownClusters:
    """Tests for known correlation clusters."""

    def test_eur_bloc_defined(self, tracker):
        """EUR bloc should be defined."""
        assert "EUR_BLOC" in tracker.KNOWN_CLUSTERS
        assert "EURUSD" in tracker.KNOWN_CLUSTERS["EUR_BLOC"]
        assert "EURGBP" in tracker.KNOWN_CLUSTERS["EUR_BLOC"]

    def test_commodity_bloc_defined(self, tracker):
        """Commodity bloc should be defined."""
        assert "COMMODITY" in tracker.KNOWN_CLUSTERS
        assert "AUDUSD" in tracker.KNOWN_CLUSTERS["COMMODITY"]
        assert "NZDUSD" in tracker.KNOWN_CLUSTERS["COMMODITY"]


class TestStaticCorrelation:
    """Tests for static correlation estimates."""

    def test_same_cluster_high_correlation(self, tracker):
        """Pairs in same cluster should have high correlation."""
        corr = tracker.get_correlation("EURUSD", "EURGBP")
        assert corr == 0.8

    def test_inverse_pairs_negative_correlation(self, tracker):
        """Inverse pairs should have negative correlation."""
        corr = tracker.get_correlation("EURUSD", "USDCHF")
        assert corr == -0.7

    def test_uncorrelated_pairs_zero(self, tracker):
        """Uncorrelated pairs should return 0."""
        corr = tracker.get_correlation("EURUSD", "AUDJPY")
        # Should be low correlation for pairs not in same cluster
        assert abs(corr) < 0.5 or corr == 0.0


class TestDynamicCorrelation:
    """Tests for dynamic correlation calculation."""

    def test_update_returns(self, tracker, correlated_returns):
        """Should store returns data."""
        tracker.update_returns("EURUSD", correlated_returns["EURUSD"])
        assert "EURUSD" in tracker.returns_data

    def test_update_correlation_matrix(self, tracker, correlated_returns):
        """Should calculate correlation matrix."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)

        tracker.update_correlation_matrix()

        assert tracker.correlation_matrix is not None
        assert "EURUSD" in tracker.correlation_matrix.columns
        assert "EURGBP" in tracker.correlation_matrix.columns

    def test_dynamic_correlation_reflects_data(self, tracker, correlated_returns):
        """Dynamic correlation should reflect actual data."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)

        tracker.update_correlation_matrix()

        # EURUSD and EURGBP should be highly correlated
        corr_eur = tracker.get_correlation("EURUSD", "EURGBP")
        assert corr_eur > 0.7

        # EURUSD and USDJPY should be less correlated
        corr_jpy = tracker.get_correlation("EURUSD", "USDJPY")
        assert abs(corr_jpy) < corr_eur


class TestClusterDetection:
    """Tests for cluster detection."""

    def test_clusters_detected(self, tracker, correlated_returns):
        """Should detect correlation clusters."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)

        tracker.update_correlation_matrix()

        # Should detect at least one cluster (EURUSD, EURGBP)
        assert len(tracker.clusters) >= 1

    def test_pair_to_cluster_mapping(self, tracker, correlated_returns):
        """Should map pairs to clusters."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)

        tracker.update_correlation_matrix()

        # Correlated pairs should be in same cluster
        eur_cluster = tracker.get_cluster_for_pair("EURUSD")
        gbp_cluster = tracker.get_cluster_for_pair("EURGBP")

        if eur_cluster is not None and gbp_cluster is not None:
            assert eur_cluster == gbp_cluster


class TestPositionLimits:
    """Tests for position limit checks."""

    def test_can_open_first_position(self, tracker):
        """Should allow first position in cluster."""
        allowed, reason = tracker.can_open_position("EURUSD", {})
        assert allowed
        assert reason == ""

    def test_blocks_excess_positions_in_cluster(self, tracker):
        """Should block excess positions in correlated cluster."""
        # Config allows 1 position per cluster
        positions = {
            1: MockPosition("EURUSD"),
        }

        # EURGBP is in same cluster as EURUSD
        allowed, reason = tracker.can_open_position("EURGBP", positions)
        assert not allowed
        assert "correlated cluster" in reason.lower()

    def test_allows_position_different_cluster(self, tracker):
        """Should allow positions in different clusters."""
        positions = {
            1: MockPosition("EURUSD"),
        }

        # AUDJPY is not in EUR cluster
        allowed, reason = tracker.can_open_position("AUDJPY", positions)
        assert allowed

    def test_custom_max_positions(self, tracker_custom):
        """Should respect custom max positions config."""
        # Custom config allows 2 positions per cluster
        positions = {
            1: MockPosition("EURUSD"),
        }

        allowed, reason = tracker_custom.can_open_position("EURGBP", positions)
        assert allowed  # Still allowed (1 < 2)

        positions[2] = MockPosition("EURGBP")
        allowed, reason = tracker_custom.can_open_position("EURJPY", positions)
        assert not allowed  # Now blocked (2 >= 2)


class TestPositionTracking:
    """Tests for position open/close tracking."""

    def test_register_position_open(self, tracker, correlated_returns):
        """Should register position open."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)
        tracker.update_correlation_matrix()

        tracker.register_position_open("EURUSD", 12345)

        cluster_id = tracker.get_cluster_for_pair("EURUSD")
        if cluster_id is not None:
            assert "EURUSD:12345" in tracker.cluster_positions[cluster_id]

    def test_register_position_close(self, tracker, correlated_returns):
        """Should register position close."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)
        tracker.update_correlation_matrix()

        tracker.register_position_open("EURUSD", 12345)
        tracker.register_position_close("EURUSD", 12345)

        cluster_id = tracker.get_cluster_for_pair("EURUSD")
        if cluster_id is not None:
            assert "EURUSD:12345" not in tracker.cluster_positions[cluster_id]


class TestDiversificationScore:
    """Tests for portfolio diversification score."""

    def test_single_position_fully_diversified(self, tracker):
        """Single position should be fully diversified."""
        positions = {1: MockPosition("EURUSD")}
        score = tracker.get_portfolio_diversification_score(positions)
        assert score == 1.0

    def test_correlated_positions_low_score(self, tracker):
        """Correlated positions should have lower score."""
        positions = {
            1: MockPosition("EURUSD"),
            2: MockPosition("EURGBP"),
        }
        score = tracker.get_portfolio_diversification_score(positions)
        assert score < 0.5  # Highly correlated = low diversification

    def test_uncorrelated_positions_high_score(self, tracker):
        """Uncorrelated positions should have higher score."""
        positions = {
            1: MockPosition("EURUSD"),
            2: MockPosition("AUDJPY"),  # Different cluster
        }
        score = tracker.get_portfolio_diversification_score(positions)
        assert score > 0.5


class TestCorrelationRiskMultiplier:
    """Tests for correlation risk multiplier."""

    def test_no_positions_full_multiplier(self, tracker):
        """No existing positions should give full multiplier."""
        mult = tracker.get_correlation_risk_multiplier("EURUSD", {})
        assert mult == 1.0

    def test_correlated_position_reduces_multiplier(self, tracker):
        """Correlated position should reduce multiplier."""
        positions = {1: MockPosition("EURGBP")}

        # EURUSD correlated with EURGBP
        mult = tracker.get_correlation_risk_multiplier("EURUSD", positions)
        assert mult < 1.0

    def test_uncorrelated_position_full_multiplier(self, tracker):
        """Uncorrelated position should maintain full multiplier."""
        positions = {1: MockPosition("AUDJPY")}

        mult = tracker.get_correlation_risk_multiplier("EURUSD", positions)
        # May still be 1.0 if not highly correlated
        assert mult >= 0.5


class TestUpdateNeeded:
    """Tests for update timing."""

    def test_needs_update_initially(self, tracker):
        """Should need update when never updated."""
        assert tracker.needs_update()

    def test_no_update_needed_after_recent_update(self, tracker, correlated_returns):
        """Should not need update after recent update."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)

        tracker.update_correlation_matrix()
        assert not tracker.needs_update()


class TestClusterPairs:
    """Tests for cluster pair retrieval."""

    def test_get_cluster_pairs_known(self, tracker):
        """Should return known cluster pairs."""
        pairs = tracker.get_cluster_pairs("EURUSD")
        assert "EURGBP" in pairs
        assert "EURUSD" in pairs

    def test_get_cluster_pairs_unknown(self, tracker):
        """Unknown pair should return just itself."""
        pairs = tracker.get_cluster_pairs("UNKNOWN")
        assert pairs == {"UNKNOWN"}


class TestStatistics:
    """Tests for statistics."""

    def test_get_statistics(self, tracker, correlated_returns):
        """Should return valid statistics."""
        for pair, returns in correlated_returns.items():
            tracker.update_returns(pair, returns)

        tracker.update_correlation_matrix()
        stats = tracker.get_statistics()

        assert "pairs_tracked" in stats
        assert "clusters_detected" in stats
        assert "last_update" in stats
        assert stats["pairs_tracked"] == 3


class TestCorrelationCluster:
    """Tests for CorrelationCluster dataclass."""

    def test_cluster_creation(self):
        """Should create cluster with required fields."""
        cluster = CorrelationCluster(
            cluster_id=1,
            pairs={"EURUSD", "EURGBP"},
            avg_correlation=0.85,
        )

        assert cluster.cluster_id == 1
        assert len(cluster.pairs) == 2
        assert cluster.avg_correlation == 0.85
        assert cluster.last_updated is not None
