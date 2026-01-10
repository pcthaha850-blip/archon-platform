"""
ARCHON RI v6.3 - System Constants
==================================

Centralized constants for the ARCHON trading system.
All magic numbers and system-wide values should be defined here.

Author: ARCHON RI Development Team
Version: 6.3.0
"""

# =============================================================================
# SYSTEM IDENTIFICATION
# =============================================================================

VERSION = "6.3.0"
SYSTEM_NAME = "ARCHON RI"
SYSTEM_COMMENT_PREFIX = "ARCHON_V6"

# =============================================================================
# MT5 CONFIGURATION
# =============================================================================

# Magic number for identifying ARCHON orders in MT5
# Used to filter positions and distinguish from manual trades
MT5_MAGIC_NUMBER = 60000

# Order comments for tracking
MT5_COMMENT_OPEN = "ARCHON_V6_OPEN"
MT5_COMMENT_CLOSE = "ARCHON_V6_CLOSE"
MT5_COMMENT_ALO = "ARCHON_ALO"  # Aggressive Limit Order prefix

# Order execution slippage tolerance (points)
MT5_DEVIATION_POINTS = 20

# =============================================================================
# TIMING CONSTANTS (milliseconds unless noted)
# =============================================================================

# Mental stop monitoring interval (seconds)
MENTAL_STOP_CHECK_INTERVAL_SEC = 0.5

# Order execution timeout (milliseconds)
ORDER_TIMEOUT_MS = 5000

# Health check interval (seconds)
HEALTH_CHECK_INTERVAL_SEC = 30

# Checkpoint interval (seconds)
CHECKPOINT_INTERVAL_SEC = 300  # 5 minutes

# CVaR update check interval (seconds)
CVAR_CHECK_INTERVAL_SEC = 300  # 5 minutes

# Signal loop interval (seconds)
SIGNAL_LOOP_INTERVAL_SEC = 60

# Retry delays (seconds)
RETRY_DELAY_SHORT_SEC = 1
RETRY_DELAY_MEDIUM_SEC = 5
RETRY_DELAY_LONG_SEC = 30
RETRY_DELAY_CIRCUIT_BREAKER_SEC = 120

# Task cancellation timeout (seconds)
TASK_CANCEL_TIMEOUT_SEC = 5.0

# =============================================================================
# TRADING CONSTANTS
# =============================================================================

# Trading days per year (for annualization calculations)
TRADING_DAYS_PER_YEAR = 252

# Hours per trading day (for forex, 24h)
HOURS_PER_TRADING_DAY = 24

# Standard lot size
STANDARD_LOT = 100000
MINI_LOT = 10000
MICRO_LOT = 1000

# =============================================================================
# PIP MULTIPLIERS
# =============================================================================

# Pip multiplier for JPY pairs (2 decimal places)
PIP_MULTIPLIER_JPY = 100

# Pip multiplier for standard pairs (4 decimal places)
PIP_MULTIPLIER_STANDARD = 10000

# Pip multiplier for indices/metals (varies)
PIP_MULTIPLIER_GOLD = 10
PIP_MULTIPLIER_INDEX = 1

# =============================================================================
# RISK THRESHOLDS
# =============================================================================

# Default risk percentages
DEFAULT_MAX_RISK_PCT = 1.0           # Max risk per trade (1%)
DEFAULT_MAX_TOTAL_RISK_PCT = 5.0     # Max total portfolio risk (5%)
DEFAULT_DD_REDUCE_PCT = 10.0         # Reduce size at 10% drawdown
DEFAULT_DD_HALT_PCT = 20.0           # Halt trading at 20% drawdown

# Broker health scores
BROKER_HEALTH_WARNING = 50.0
BROKER_HEALTH_CRITICAL = 30.0

# Default position limits
DEFAULT_MAX_POSITIONS = 5
DEFAULT_MAX_POSITIONS_PER_PAIR = 2
DEFAULT_MAX_CORRELATED_POSITIONS = 3

# Kelly fraction bounds
KELLY_FRACTION_MIN = 0.05
KELLY_FRACTION_MAX = 0.50

# Z-score thresholds for entry
ZSCORE_MIN_ENTRY = 1.25
ZSCORE_MAX_ENTRY = 4.0

# =============================================================================
# STATISTICAL CONSTANTS
# =============================================================================

# Hurst exponent thresholds
HURST_MEAN_REVERTING_THRESHOLD = 0.45
HURST_TRENDING_THRESHOLD = 0.55
HURST_RANDOM_WALK = 0.5

# VaR/CVaR confidence levels
VAR_CONFIDENCE_95 = 0.95
VAR_CONFIDENCE_99 = 0.99

# Correlation thresholds
CORRELATION_HIGH = 0.7
CORRELATION_MEDIUM = 0.5
CORRELATION_LOW = 0.3

# =============================================================================
# HTTP/NETWORK CONSTANTS
# =============================================================================

# Connection pooling
HTTP_POOL_CONNECTIONS = 5
HTTP_POOL_MAXSIZE = 10
HTTP_MAX_RETRIES = 2

# Timeouts (seconds)
HTTP_CONNECT_TIMEOUT = 2
HTTP_READ_TIMEOUT = 5
HTTP_REQUEST_TIMEOUT_SEC = 10
EXTERNAL_FEED_TIMEOUT = 2

# Feed timeouts
FEED_TIMEOUT_SEC = 5
FEED_STALE_THRESHOLD_SEC = 10

# =============================================================================
# FILE PATHS
# =============================================================================

# Default log file
DEFAULT_LOG_FILE = "archon_ri_v6.log"

# Default database file
DEFAULT_DB_FILE = "archon_trading.db"

# State persistence file
DEFAULT_STATE_FILE = "archon_state.json"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_pip_multiplier(pair: str) -> int:
    """Get pip multiplier for a currency pair."""
    pair_upper = pair.upper()
    if 'JPY' in pair_upper:
        return PIP_MULTIPLIER_JPY
    elif 'XAU' in pair_upper or 'GOLD' in pair_upper:
        return PIP_MULTIPLIER_GOLD
    else:
        return PIP_MULTIPLIER_STANDARD


def is_jpy_pair(pair: str) -> bool:
    """Check if pair involves JPY."""
    return 'JPY' in pair.upper()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # System
    'VERSION',
    'SYSTEM_NAME',
    'SYSTEM_COMMENT_PREFIX',

    # MT5
    'MT5_MAGIC_NUMBER',
    'MT5_COMMENT_OPEN',
    'MT5_COMMENT_CLOSE',
    'MT5_COMMENT_ALO',
    'MT5_DEVIATION_POINTS',

    # Timing
    'MENTAL_STOP_CHECK_INTERVAL_SEC',
    'ORDER_TIMEOUT_MS',
    'HEALTH_CHECK_INTERVAL_SEC',
    'CHECKPOINT_INTERVAL_SEC',
    'CVAR_CHECK_INTERVAL_SEC',
    'SIGNAL_LOOP_INTERVAL_SEC',
    'RETRY_DELAY_SHORT_SEC',
    'RETRY_DELAY_MEDIUM_SEC',
    'RETRY_DELAY_LONG_SEC',
    'RETRY_DELAY_CIRCUIT_BREAKER_SEC',
    'TASK_CANCEL_TIMEOUT_SEC',

    # Trading
    'TRADING_DAYS_PER_YEAR',
    'HOURS_PER_TRADING_DAY',
    'STANDARD_LOT',
    'MINI_LOT',
    'MICRO_LOT',

    # Pip multipliers
    'PIP_MULTIPLIER_JPY',
    'PIP_MULTIPLIER_STANDARD',
    'PIP_MULTIPLIER_GOLD',
    'PIP_MULTIPLIER_INDEX',

    # Risk
    'DEFAULT_MAX_RISK_PCT',
    'DEFAULT_MAX_TOTAL_RISK_PCT',
    'DEFAULT_DD_REDUCE_PCT',
    'DEFAULT_DD_HALT_PCT',
    'BROKER_HEALTH_WARNING',
    'BROKER_HEALTH_CRITICAL',
    'DEFAULT_MAX_POSITIONS',
    'DEFAULT_MAX_POSITIONS_PER_PAIR',
    'DEFAULT_MAX_CORRELATED_POSITIONS',
    'KELLY_FRACTION_MIN',
    'KELLY_FRACTION_MAX',
    'ZSCORE_MIN_ENTRY',
    'ZSCORE_MAX_ENTRY',

    # Statistics
    'HURST_MEAN_REVERTING_THRESHOLD',
    'HURST_TRENDING_THRESHOLD',
    'HURST_RANDOM_WALK',
    'VAR_CONFIDENCE_95',
    'VAR_CONFIDENCE_99',
    'CORRELATION_HIGH',
    'CORRELATION_MEDIUM',
    'CORRELATION_LOW',

    # HTTP
    'HTTP_POOL_CONNECTIONS',
    'HTTP_POOL_MAXSIZE',
    'HTTP_MAX_RETRIES',
    'HTTP_CONNECT_TIMEOUT',
    'HTTP_READ_TIMEOUT',
    'HTTP_REQUEST_TIMEOUT_SEC',
    'EXTERNAL_FEED_TIMEOUT',
    'FEED_TIMEOUT_SEC',
    'FEED_STALE_THRESHOLD_SEC',

    # Files
    'DEFAULT_LOG_FILE',
    'DEFAULT_DB_FILE',
    'DEFAULT_STATE_FILE',

    # Functions
    'get_pip_multiplier',
    'is_jpy_pair',
]
