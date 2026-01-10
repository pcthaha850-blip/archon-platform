"""
ARCHON RI v6.3 - Centralized Exception Hierarchy
=================================================

Provides structured exception types for proper error handling
and categorization across the trading system.

Exception Categories:
    - BrokerError: Connection and broker communication issues
    - OrderError: Order execution and validation failures
    - RiskError: Risk limit violations and drawdown events
    - DataError: Data validation and feed issues
    - ConfigurationError: Configuration and setup problems
    - SystemError: System-level and infrastructure errors
    - StrategyError: Strategy and signal generation issues
    - ExternalServiceError: Third-party service failures

Author: ARCHON RI Development Team
Version: 6.3.0
"""

from typing import Any, Dict, Optional


class ArchonError(Exception):
    """
    Base exception for all ARCHON system errors.

    Attributes:
        message: Human-readable error description
        code: Optional error code for programmatic handling
        details: Optional dict with additional context
        recoverable: Whether error can potentially be retried
    """

    # Default recoverability - subclasses can override
    recoverable: bool = True

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


# =============================================================================
# BROKER & CONNECTION ERRORS
# =============================================================================


class BrokerError(ArchonError):
    """Base exception for broker-related errors."""

    def __init__(self, message: str, error_code: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.error_code = error_code


class BrokerConnectionError(BrokerError):
    """Failed to connect to broker (MT5)."""

    pass


class BrokerDisconnectedError(BrokerError):
    """Lost connection to broker during operation."""

    pass


class BrokerTimeoutError(BrokerError):
    """Broker operation timed out."""

    pass


# =============================================================================
# ORDER & EXECUTION ERRORS
# =============================================================================


class OrderError(ArchonError):
    """Base exception for order-related errors."""

    pass


class OrderExecutionError(OrderError):
    """Order execution failed."""

    def __init__(
        self,
        message: str,
        ticket: Optional[int] = None,
        retcode: Optional[int] = None,
        order_type: Optional[str] = None,
        pair: Optional[str] = None,
        lots: Optional[float] = None,
        error_code: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.ticket = ticket
        self.retcode = retcode
        self.order_type = order_type
        self.pair = pair
        self.lots = lots
        self.error_code = error_code


class OrderRejectedError(OrderError):
    """Order was rejected by broker."""

    pass


class InsufficientMarginError(OrderError):
    """Insufficient margin for order."""

    pass


class InvalidOrderError(OrderError):
    """Order parameters are invalid."""

    pass


class DuplicateOrderError(OrderError):
    """Duplicate order detected (idempotency violation)."""

    pass


# =============================================================================
# RISK & VALIDATION ERRORS
# =============================================================================


class RiskError(ArchonError):
    """Base exception for risk-related errors."""

    pass


class RiskLimitExceededError(RiskError):
    """Risk limit exceeded - trade blocked."""

    recoverable: bool = False  # Risk limits require intervention

    def __init__(
        self,
        message: str,
        limit_type: str = "unknown",
        current_value: float = 0.0,
        limit_value: float = 0.0,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.limit_type = limit_type
        self.current_value = current_value
        self.limit_value = limit_value


class DrawdownHaltError(RiskError):
    """Trading halted due to drawdown limit."""

    pass


class PositionLimitError(RiskError):
    """Maximum position count reached."""

    pass


# =============================================================================
# DATA & VALIDATION ERRORS
# =============================================================================


class DataError(ArchonError):
    """Base exception for data-related errors."""

    pass


class DataValidationError(DataError):
    """Invalid data received or calculated."""

    pass


class InsufficientDataError(DataError):
    """Not enough data for calculation."""

    def __init__(
        self, message: str, required: int = 0, available: int = 0, **kwargs
    ):
        super().__init__(message, **kwargs)
        self.required = required
        self.available = available


class PriceFeedError(DataError):
    """Error with price feed data."""

    pass


class PriceManipulationError(PriceFeedError):
    """Potential price manipulation detected."""

    pass


# =============================================================================
# CONFIGURATION ERRORS
# =============================================================================


class ConfigurationError(ArchonError):
    """Base exception for configuration errors."""

    pass


class InvalidConfigError(ConfigurationError):
    """Invalid configuration value."""

    pass


class MissingConfigError(ConfigurationError):
    """Required configuration is missing."""

    pass


# =============================================================================
# SYSTEM & INFRASTRUCTURE ERRORS
# =============================================================================


class ArchonSystemError(ArchonError):
    """Base exception for system-level errors."""

    pass


class CircuitBreakerOpenError(ArchonSystemError):
    """Circuit breaker is open - operations blocked."""

    recoverable: bool = False  # Circuit breaker requires waiting

    def __init__(
        self,
        message: str,
        reason: Optional[str] = None,
        resume_time: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.reason = reason
        self.resume_time = resume_time


class StateError(ArchonSystemError):
    """Invalid system state."""

    pass


class ShutdownError(ArchonSystemError):
    """Error during shutdown."""

    pass


# =============================================================================
# STRATEGY ERRORS
# =============================================================================


class StrategyError(ArchonError):
    """Base exception for strategy-related errors."""

    pass


class SignalGenerationError(StrategyError):
    """Failed to generate trading signal."""

    pass


class RegimeDetectionError(StrategyError):
    """Failed to detect market regime."""

    pass


# =============================================================================
# EXTERNAL SERVICE ERRORS
# =============================================================================


class ExternalServiceError(ArchonError):
    """Base exception for external service errors."""

    pass


class TelegramError(ExternalServiceError):
    """Telegram API error."""

    pass


class ExternalFeedError(ExternalServiceError):
    """External price feed error."""

    pass


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def is_recoverable(error: Exception) -> bool:
    """
    Determine if an error is potentially recoverable.

    Recoverable errors can be retried after a delay.
    Non-recoverable errors require intervention.
    """
    # Check if error has recoverable attribute (ArchonError subclasses)
    if hasattr(error, "recoverable"):
        return error.recoverable

    # Standard Python exceptions are generally not recoverable
    return not isinstance(error, (SystemExit, KeyboardInterrupt, MemoryError))


def is_critical(error: Exception) -> bool:
    """
    Determine if an error is critical and requires immediate attention.

    Critical errors are those that:
    - Block trading operations
    - Indicate potential system compromise
    - Require immediate intervention
    """
    critical_types = (
        DrawdownHaltError,
        CircuitBreakerOpenError,
        PriceManipulationError,
        InsufficientMarginError,
        RiskLimitExceededError,
    )
    return isinstance(error, critical_types)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Base
    "ArchonError",
    # Broker
    "BrokerError",
    "BrokerConnectionError",
    "BrokerDisconnectedError",
    "BrokerTimeoutError",
    # Order
    "OrderError",
    "OrderExecutionError",
    "OrderRejectedError",
    "InsufficientMarginError",
    "InvalidOrderError",
    "DuplicateOrderError",
    # Risk
    "RiskError",
    "RiskLimitExceededError",
    "DrawdownHaltError",
    "PositionLimitError",
    # Data
    "DataError",
    "DataValidationError",
    "InsufficientDataError",
    "PriceFeedError",
    "PriceManipulationError",
    # Config
    "ConfigurationError",
    "InvalidConfigError",
    "MissingConfigError",
    # System
    "ArchonSystemError",
    "CircuitBreakerOpenError",
    "StateError",
    "ShutdownError",
    # Strategy
    "StrategyError",
    "SignalGenerationError",
    "RegimeDetectionError",
    # External
    "ExternalServiceError",
    "TelegramError",
    "ExternalFeedError",
    # Helpers
    "is_recoverable",
    "is_critical",
]
