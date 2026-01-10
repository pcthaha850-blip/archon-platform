"""
ARCHON RI v6.3 - Correlation Tracker
=====================================

Tracks pair correlations for portfolio risk management.
Prevents overexposure to correlated assets.

Author: ARCHON RI Development Team
Version: 6.3.0
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("ARCHON_CorrelationTracker")


@dataclass
class CorrelationCluster:
    """A group of highly correlated pairs."""

    cluster_id: int
    pairs: Set[str]
    avg_correlation: float
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CorrelationConfig:
    """Configuration for correlation tracking."""

    lookback_days: int = 60
    high_correlation_threshold: float = 0.7
    update_frequency_hours: int = 24
    max_positions_per_cluster: int = 1
    timeframe: str = "H1"  # For proper annualization
    bars_per_day: int = 24  # H1 = 24 bars per day


class CorrelationTracker:
    """
    Tracks correlations between trading pairs.

    Features:
    - Rolling correlation matrix
    - Cluster detection for highly correlated pairs
    - Position limits per cluster
    - Regime-aware correlation adjustments
    """

    # Known correlation clusters (static baseline)
    KNOWN_CLUSTERS = {
        "EUR_BLOC": {"EURUSD", "EURGBP", "EURJPY", "EURCHF", "EURAUD"},
        "GBP_BLOC": {"GBPUSD", "EURGBP", "GBPJPY", "GBPCHF", "GBPAUD"},
        "COMMODITY": {"AUDUSD", "NZDUSD", "USDCAD"},
        "SAFE_HAVEN": {"USDJPY", "USDCHF", "XAUUSD"},
        "RISK_ON": {"AUDJPY", "NZDJPY", "CADJPY"},
    }

    def __init__(self, config: Optional[CorrelationConfig] = None):
        self.config = config or CorrelationConfig()

        # Data storage
        self.returns_data: Dict[str, pd.Series] = {}
        self.correlation_matrix: Optional[pd.DataFrame] = None
        self.clusters: List[CorrelationCluster] = []

        # Tracking
        self.last_update: Optional[datetime] = None
        self.pair_to_cluster: Dict[str, int] = {}

        # Open positions per cluster
        self.cluster_positions: Dict[int, Set[str]] = defaultdict(set)

        logger.info("CorrelationTracker initialized")

    def update_returns(self, pair: str, returns: pd.Series):
        """Update returns data for a pair."""
        self.returns_data[pair] = returns.tail(
            self.config.lookback_days * self.config.bars_per_day
        )

    def update_correlation_matrix(self):
        """Recalculate correlation matrix from returns data."""
        if len(self.returns_data) < 2:
            return

        # Build DataFrame of returns
        returns_df = pd.DataFrame(self.returns_data)

        # Calculate correlation matrix
        self.correlation_matrix = returns_df.corr()

        # Detect clusters
        self._detect_clusters()

        self.last_update = datetime.now(timezone.utc)
        logger.info(f"Correlation matrix updated: {len(self.returns_data)} pairs")

    def _detect_clusters(self):
        """Detect clusters of highly correlated pairs."""
        if self.correlation_matrix is None:
            return

        pairs = list(self.correlation_matrix.columns)
        visited: Set[str] = set()
        self.clusters = []
        cluster_id = 0

        for pair in pairs:
            if pair in visited:
                continue

            # Find all pairs correlated with this one
            cluster_pairs = {pair}

            for other_pair in pairs:
                if other_pair == pair or other_pair in visited:
                    continue

                corr = abs(self.correlation_matrix.loc[pair, other_pair])
                if corr >= self.config.high_correlation_threshold:
                    cluster_pairs.add(other_pair)

            if len(cluster_pairs) > 1:
                # Calculate average correlation within cluster
                cluster_corrs = []
                for p1 in cluster_pairs:
                    for p2 in cluster_pairs:
                        if p1 != p2:
                            cluster_corrs.append(
                                abs(self.correlation_matrix.loc[p1, p2])
                            )

                avg_corr = np.mean(cluster_corrs) if cluster_corrs else 0.0

                cluster = CorrelationCluster(
                    cluster_id=cluster_id,
                    pairs=cluster_pairs,
                    avg_correlation=avg_corr,
                )
                self.clusters.append(cluster)

                # Map pairs to cluster
                for p in cluster_pairs:
                    self.pair_to_cluster[p] = cluster_id
                    visited.add(p)

                cluster_id += 1

        logger.info(f"Detected {len(self.clusters)} correlation clusters")

    def get_correlation(self, pair1: str, pair2: str) -> float:
        """Get correlation between two pairs."""
        if self.correlation_matrix is None:
            return self._get_static_correlation(pair1, pair2)

        if (
            pair1 in self.correlation_matrix.columns
            and pair2 in self.correlation_matrix.columns
        ):
            return float(self.correlation_matrix.loc[pair1, pair2])

        return self._get_static_correlation(pair1, pair2)

    def _get_static_correlation(self, pair1: str, pair2: str) -> float:
        """Get static correlation estimate based on known clusters."""
        for cluster_name, pairs in self.KNOWN_CLUSTERS.items():
            if pair1 in pairs and pair2 in pairs:
                return 0.8  # High correlation within cluster

        # Check for inverse correlation (e.g., EURUSD vs USDCHF)
        if self._are_inverse_pairs(pair1, pair2):
            return -0.7

        return 0.0  # Default: assume uncorrelated

    def _are_inverse_pairs(self, pair1: str, pair2: str) -> bool:
        """Check if pairs are inversely correlated."""
        # Pairs with USD on opposite sides
        inverse_sets = [
            {"EURUSD", "USDCHF"},
            {"GBPUSD", "USDCHF"},
            {"AUDUSD", "USDCAD"},
        ]

        pair_set = {pair1, pair2}
        return any(pair_set == inv for inv in inverse_sets)

    def get_cluster_for_pair(self, pair: str) -> Optional[int]:
        """Get cluster ID for a pair."""
        return self.pair_to_cluster.get(pair)

    def get_cluster_pairs(self, pair: str) -> Set[str]:
        """Get all pairs in the same cluster as given pair."""
        cluster_id = self.pair_to_cluster.get(pair)

        if cluster_id is not None:
            for cluster in self.clusters:
                if cluster.cluster_id == cluster_id:
                    return cluster.pairs

        # Fallback to static clusters
        for cluster_name, pairs in self.KNOWN_CLUSTERS.items():
            if pair in pairs:
                return pairs

        return {pair}

    def can_open_position(
        self, pair: str, current_positions: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Check if a new position can be opened based on correlation limits.

        Args:
            pair: The pair to check
            current_positions: Dict of ticket -> position info

        Returns:
            Tuple of (allowed, reason)
        """
        cluster_pairs = self.get_cluster_pairs(pair)

        # Count positions in same cluster
        cluster_position_count = 0
        for pos in current_positions.values():
            if hasattr(pos, "pair") and pos.pair in cluster_pairs:
                cluster_position_count += 1

        if cluster_position_count >= self.config.max_positions_per_cluster:
            cluster_list = ", ".join(sorted(cluster_pairs))
            return False, f"Max positions in correlated cluster: {cluster_list}"

        return True, ""

    def register_position_open(self, pair: str, ticket: int):
        """Register that a position was opened."""
        cluster_id = self.get_cluster_for_pair(pair)
        if cluster_id is not None:
            self.cluster_positions[cluster_id].add(f"{pair}:{ticket}")

    def register_position_close(self, pair: str, ticket: int):
        """Register that a position was closed."""
        cluster_id = self.get_cluster_for_pair(pair)
        if cluster_id is not None:
            self.cluster_positions[cluster_id].discard(f"{pair}:{ticket}")

    def needs_update(self) -> bool:
        """Check if correlation matrix needs updating."""
        if self.last_update is None:
            return True

        age = datetime.now(timezone.utc) - self.last_update
        return age.total_seconds() > self.config.update_frequency_hours * 3600

    def get_portfolio_diversification_score(
        self, positions: Dict[str, Any]
    ) -> float:
        """
        Calculate portfolio diversification score (0-1).

        1.0 = Perfectly diversified (uncorrelated positions)
        0.0 = Highly concentrated (all positions correlated)
        """
        if len(positions) < 2:
            return 1.0

        pairs = [pos.pair for pos in positions.values() if hasattr(pos, "pair")]

        if len(pairs) < 2:
            return 1.0

        # Calculate average absolute correlation
        total_corr = 0.0
        count = 0

        for i, p1 in enumerate(pairs):
            for p2 in pairs[i + 1 :]:
                total_corr += abs(self.get_correlation(p1, p2))
                count += 1

        if count == 0:
            return 1.0

        avg_corr = total_corr / count

        # Convert to diversification score (inverse of correlation)
        return 1.0 - avg_corr

    def get_correlation_risk_multiplier(
        self, pair: str, positions: Dict[str, Any]
    ) -> float:
        """
        Get risk multiplier based on correlation with existing positions.

        Returns:
            Multiplier < 1.0 if highly correlated (reduce size)
            Multiplier = 1.0 if uncorrelated
        """
        if not positions:
            return 1.0

        max_corr = 0.0

        for pos in positions.values():
            if hasattr(pos, "pair"):
                corr = abs(self.get_correlation(pair, pos.pair))
                max_corr = max(max_corr, corr)

        # Scale down if correlated
        if max_corr > self.config.high_correlation_threshold:
            # Reduce by up to 50% for highly correlated
            reduction = (max_corr - self.config.high_correlation_threshold) / (
                1.0 - self.config.high_correlation_threshold
            )
            return 1.0 - (0.5 * reduction)

        return 1.0

    def get_statistics(self) -> Dict[str, Any]:
        """Get correlation tracker statistics."""
        return {
            "pairs_tracked": len(self.returns_data),
            "clusters_detected": len(self.clusters),
            "last_update": (
                self.last_update.isoformat() if self.last_update else None
            ),
            "cluster_details": [
                {
                    "id": c.cluster_id,
                    "pairs": list(c.pairs),
                    "avg_correlation": c.avg_correlation,
                }
                for c in self.clusters
            ],
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["CorrelationCluster", "CorrelationConfig", "CorrelationTracker"]
