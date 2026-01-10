# ARCHON PRIME Strategy Plugins
"""
Strategy plugins for signal generation.

Available Strategies:
    - TSM (Trend-Structure-Momentum)
    - VMR (Volatility-Momentum-Regime)
    - RWEC (Range-Weighted Elastic Channel)
    - Neural Network Strategy
    - Mean Reversion Strategy
"""

from .tsm_strategy import TSMStrategy
from .vmr_strategy import VMRStrategy

__all__ = [
    "TSMStrategy",
    "VMRStrategy",
]
