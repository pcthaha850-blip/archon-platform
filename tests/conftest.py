"""
ARCHON Test Configuration
==========================

Pytest fixtures and configuration for ARCHON platform tests.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone


@pytest.fixture
def sample_returns():
    """Generate sample return series for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    returns = pd.Series(np.random.normal(0.0001, 0.01, 100), index=dates)
    return returns


@pytest.fixture
def sample_prices():
    """Generate sample price series for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    # Generate random walk prices starting at 1.1000
    returns = np.random.normal(0.0001, 0.005, 100)
    prices = 1.1000 * np.cumprod(1 + returns)
    return pd.Series(prices, index=dates)


@pytest.fixture
def trending_prices():
    """Generate trending price series (H > 0.5)."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    # Trending prices with momentum
    trend = np.linspace(0, 0.1, 100)
    noise = np.random.normal(0, 0.005, 100)
    prices = 1.1000 * (1 + trend + noise)
    return pd.Series(prices, index=dates)


@pytest.fixture
def mean_reverting_prices():
    """Generate mean-reverting price series (H < 0.5)."""
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    # Mean-reverting around 1.1000
    mean = 1.1000
    prices = [mean]
    for _ in range(99):
        # Mean reversion factor
        reversion = 0.3 * (mean - prices[-1])
        noise = np.random.normal(0, 0.003)
        prices.append(prices[-1] + reversion + noise)
    return pd.Series(prices, index=dates)


@pytest.fixture
def account_equity():
    """Standard test account equity."""
    return 500.0


@pytest.fixture
def pip_value():
    """Standard pip value for EURUSD."""
    return 10.0  # $10 per pip for 1 lot


@pytest.fixture
def stop_distance():
    """Standard stop distance in pips."""
    return 50.0
