# ARCHON Core - Trading Logic
"""
Core trading logic and risk management for ARCHON platform.

Modules:
    constants: System-wide constants and configuration values
    exceptions: Centralized exception hierarchy
    correlation_tracker: Pair correlation tracking and cluster detection
    kelly_criterion: Dynamic Kelly position sizing
    cvar_engine: Conditional Value at Risk calculations
    panic_hedge: Emergency protection and kill switch
    signal_gate: Consensus engine for trade validation
"""

from .constants import (
    VERSION,
    SYSTEM_NAME,
    MT5_MAGIC_NUMBER,
    TRADING_DAYS_PER_YEAR,
    get_pip_multiplier,
    is_jpy_pair,
)

from .exceptions import (
    ArchonError,
    BrokerError,
    BrokerConnectionError,
    OrderError,
    OrderExecutionError,
    RiskError,
    RiskLimitExceededError,
    DrawdownHaltError,
    DataError,
    is_recoverable,
    is_critical,
)

from .correlation_tracker import (
    CorrelationCluster,
    CorrelationConfig,
    CorrelationTracker,
)

from .kelly_criterion import (
    KellyConfig,
    KellyCriterion,
)

from .cvar_engine import (
    CVaRConfig,
    CVaRResult,
    CVaREngine,
)

from .panic_hedge import (
    PanicTrigger,
    PanicAction,
    PanicConfig,
    PanicState,
    PanicHedge,
)

from .signal_gate import (
    GateResult,
    GateType,
    GateDecision,
    SignalGateConfig,
    Signal,
    ConsensusResult,
    SignalGate,
)

from .position_manager import (
    PositionSide,
    PositionStatus,
    PositionState,
    Position,
    PositionManagerConfig,
    PositionManager,
)

__version__ = "6.3.0"

__all__ = [
    # Version
    "__version__",

    # Constants
    "VERSION",
    "SYSTEM_NAME",
    "MT5_MAGIC_NUMBER",
    "TRADING_DAYS_PER_YEAR",
    "get_pip_multiplier",
    "is_jpy_pair",

    # Exceptions
    "ArchonError",
    "BrokerError",
    "BrokerConnectionError",
    "OrderError",
    "OrderExecutionError",
    "RiskError",
    "RiskLimitExceededError",
    "DrawdownHaltError",
    "DataError",
    "is_recoverable",
    "is_critical",

    # Correlation Tracker
    "CorrelationCluster",
    "CorrelationConfig",
    "CorrelationTracker",

    # Kelly Criterion
    "KellyConfig",
    "KellyCriterion",

    # CVaR Engine
    "CVaRConfig",
    "CVaRResult",
    "CVaREngine",

    # Panic Hedge
    "PanicTrigger",
    "PanicAction",
    "PanicConfig",
    "PanicState",
    "PanicHedge",

    # Signal Gate
    "GateResult",
    "GateType",
    "GateDecision",
    "SignalGateConfig",
    "Signal",
    "ConsensusResult",
    "SignalGate",

    # Position Manager
    "PositionSide",
    "PositionStatus",
    "PositionState",
    "Position",
    "PositionManagerConfig",
    "PositionManager",
]
