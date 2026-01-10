# ARCHON_FEAT: config-manager-001
"""
ARCHON PRIME - Configuration Manager
====================================

Centralized configuration management for ARCHON PRIME.

Features:
- YAML/JSON configuration loading
- Environment variable overrides
- Configuration validation
- Hot reload support

Author: ARCHON Development Team
Version: 1.0.0
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
import json

logger = logging.getLogger("ARCHON_ConfigManager")


@dataclass
class TradingConfig:
    """Trading configuration."""

    symbols: List[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD", "XAUUSD"])
    timeframes: List[str] = field(default_factory=lambda: ["M1", "M5", "H1"])
    max_positions: int = 2
    max_risk_per_trade_pct: float = 0.5
    max_total_risk_pct: float = 2.0


@dataclass
class RiskConfig:
    """Risk management configuration."""

    max_drawdown_pct: float = 10.0
    dd_reduce_threshold_pct: float = 5.0
    dd_halt_threshold_pct: float = 15.0
    kelly_min_z: float = 1.25
    kelly_scale: float = 0.15
    cvar_confidence: float = 0.95
    correlation_threshold: float = 0.7
    panic_hedge_trigger_pct: float = 2.0


@dataclass
class ExecutionConfig:
    """Execution configuration."""

    slippage_tolerance_pips: float = 2.0
    max_spread_pips: float = 3.0
    order_timeout_sec: int = 30
    retry_attempts: int = 3
    ghost_mode_enabled: bool = True
    iceberg_enabled: bool = True
    twap_enabled: bool = True


@dataclass
class BrokerConfig:
    """Broker configuration."""

    name: str = "mt5"
    server: str = ""
    login: int = 0
    password: str = ""
    path: str = ""
    timeout: int = 60000


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""

    log_level: str = "INFO"
    metrics_interval_sec: int = 60
    health_check_interval_sec: int = 30
    alert_email: str = ""
    alert_webhook: str = ""


@dataclass
class PluginConfig:
    """Plugin system configuration."""

    enabled_strategies: List[str] = field(default_factory=list)
    enabled_risk: List[str] = field(default_factory=list)
    enabled_execution: List[str] = field(default_factory=list)
    enabled_brokers: List[str] = field(default_factory=list)
    enabled_data: List[str] = field(default_factory=list)
    enabled_monitoring: List[str] = field(default_factory=list)
    enabled_ml: List[str] = field(default_factory=list)
    enabled_stealth: List[str] = field(default_factory=list)


@dataclass
class SystemConfig:
    """Complete system configuration."""

    mode: str = "paper"  # paper, live
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)


class ConfigManager:
    """
    Configuration manager for ARCHON PRIME.

    Handles loading, validation, and access to system configuration.

    Example:
        config_manager = ConfigManager()
        config_manager.load("config/live.yaml")

        max_dd = config_manager.get("risk.max_drawdown_pct")
        symbols = config_manager.get("trading.symbols")
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path
        self._config: SystemConfig = SystemConfig()
        self._raw_config: Dict[str, Any] = {}
        self._loaded_at: Optional[datetime] = None
        self._env_prefix = "ARCHON_"

        if config_path:
            self.load(config_path)

        logger.info("ConfigManager initialized")

    def load(self, path: Union[str, Path]) -> bool:
        """
        Load configuration from file.

        Args:
            path: Path to config file (YAML or JSON)

        Returns:
            True if loaded successfully
        """
        path = Path(path)

        if not path.exists():
            logger.warning(f"Config file not found: {path}")
            return False

        try:
            with open(path, "r") as f:
                if path.suffix in [".yaml", ".yml"]:
                    self._raw_config = yaml.safe_load(f) or {}
                elif path.suffix == ".json":
                    self._raw_config = json.load(f)
                else:
                    logger.error(f"Unsupported config format: {path.suffix}")
                    return False

            # Apply environment overrides
            self._apply_env_overrides()

            # Parse into structured config
            self._parse_config()

            self._config_path = path
            self._loaded_at = datetime.now(timezone.utc)
            logger.info(f"Configuration loaded from: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        for key, value in os.environ.items():
            if key.startswith(self._env_prefix):
                config_key = key[len(self._env_prefix):].lower().replace("__", ".")
                self._set_nested(config_key, self._parse_value(value))

    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type."""
        # Try boolean
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # Try integer
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string
        return value

    def _set_nested(self, key: str, value: Any) -> None:
        """Set a nested config value using dot notation."""
        parts = key.split(".")
        current = self._raw_config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def _parse_config(self) -> None:
        """Parse raw config into structured config."""
        raw = self._raw_config

        # Mode
        self._config.mode = raw.get("mode", "paper")

        # Trading config
        if "trading" in raw:
            t = raw["trading"]
            self._config.trading = TradingConfig(
                symbols=t.get("symbols", ["EURUSD", "GBPUSD", "XAUUSD"]),
                timeframes=t.get("timeframes", ["M1", "M5", "H1"]),
                max_positions=t.get("max_positions", 2),
                max_risk_per_trade_pct=t.get("max_risk_per_trade_pct", 0.5),
                max_total_risk_pct=t.get("max_total_risk_pct", 2.0),
            )

        # Risk config
        if "risk" in raw:
            r = raw["risk"]
            self._config.risk = RiskConfig(
                max_drawdown_pct=r.get("max_drawdown_pct", 10.0),
                dd_reduce_threshold_pct=r.get("dd_reduce_threshold_pct", 5.0),
                dd_halt_threshold_pct=r.get("dd_halt_threshold_pct", 15.0),
                kelly_min_z=r.get("kelly_min_z", 1.25),
                kelly_scale=r.get("kelly_scale", 0.15),
                cvar_confidence=r.get("cvar_confidence", 0.95),
                correlation_threshold=r.get("correlation_threshold", 0.7),
                panic_hedge_trigger_pct=r.get("panic_hedge_trigger_pct", 2.0),
            )

        # Execution config
        if "execution" in raw:
            e = raw["execution"]
            self._config.execution = ExecutionConfig(
                slippage_tolerance_pips=e.get("slippage_tolerance_pips", 2.0),
                max_spread_pips=e.get("max_spread_pips", 3.0),
                order_timeout_sec=e.get("order_timeout_sec", 30),
                retry_attempts=e.get("retry_attempts", 3),
                ghost_mode_enabled=e.get("ghost_mode_enabled", True),
                iceberg_enabled=e.get("iceberg_enabled", True),
                twap_enabled=e.get("twap_enabled", True),
            )

        # Broker config
        if "broker" in raw:
            b = raw["broker"]
            self._config.broker = BrokerConfig(
                name=b.get("name", "mt5"),
                server=b.get("server", ""),
                login=b.get("login", 0),
                password=b.get("password", ""),
                path=b.get("path", ""),
                timeout=b.get("timeout", 60000),
            )

        # Monitoring config
        if "monitoring" in raw:
            m = raw["monitoring"]
            self._config.monitoring = MonitoringConfig(
                log_level=m.get("log_level", "INFO"),
                metrics_interval_sec=m.get("metrics_interval_sec", 60),
                health_check_interval_sec=m.get("health_check_interval_sec", 30),
                alert_email=m.get("alert_email", ""),
                alert_webhook=m.get("alert_webhook", ""),
            )

        # Plugins config
        if "plugins" in raw:
            p = raw["plugins"]
            self._config.plugins = PluginConfig(
                enabled_strategies=p.get("strategies", []),
                enabled_risk=p.get("risk", []),
                enabled_execution=p.get("execution", []),
                enabled_brokers=p.get("brokers", []),
                enabled_data=p.get("data", []),
                enabled_monitoring=p.get("monitoring", []),
                enabled_ml=p.get("ml", []),
                enabled_stealth=p.get("stealth", []),
            )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Dot-notation key (e.g., "risk.max_drawdown_pct")
            default: Default value if not found

        Returns:
            Configuration value
        """
        parts = key.split(".")
        current = self._raw_config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value (runtime only)."""
        self._set_nested(key, value)
        self._parse_config()

    @property
    def config(self) -> SystemConfig:
        """Get the structured configuration."""
        return self._config

    @property
    def trading(self) -> TradingConfig:
        """Get trading configuration."""
        return self._config.trading

    @property
    def risk(self) -> RiskConfig:
        """Get risk configuration."""
        return self._config.risk

    @property
    def execution(self) -> ExecutionConfig:
        """Get execution configuration."""
        return self._config.execution

    @property
    def broker(self) -> BrokerConfig:
        """Get broker configuration."""
        return self._config.broker

    @property
    def monitoring(self) -> MonitoringConfig:
        """Get monitoring configuration."""
        return self._config.monitoring

    @property
    def plugins(self) -> PluginConfig:
        """Get plugin configuration."""
        return self._config.plugins

    @property
    def is_live(self) -> bool:
        """Check if running in live mode."""
        return self._config.mode == "live"

    @property
    def is_paper(self) -> bool:
        """Check if running in paper mode."""
        return self._config.mode == "paper"

    def reload(self) -> bool:
        """Reload configuration from file."""
        if self._config_path:
            return self.load(self._config_path)
        return False

    def save(self, path: Optional[Path] = None) -> bool:
        """
        Save configuration to file.

        Args:
            path: Optional path (uses loaded path if not specified)

        Returns:
            True if saved successfully
        """
        path = path or self._config_path

        if not path:
            logger.error("No config path specified")
            return False

        try:
            with open(path, "w") as f:
                if path.suffix in [".yaml", ".yml"]:
                    yaml.safe_dump(self._raw_config, f, default_flow_style=False)
                else:
                    json.dump(self._raw_config, f, indent=2)

            logger.info(f"Configuration saved to: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate trading config
        if self._config.trading.max_positions < 1:
            errors.append("trading.max_positions must be >= 1")

        if self._config.trading.max_risk_per_trade_pct <= 0:
            errors.append("trading.max_risk_per_trade_pct must be > 0")

        if self._config.trading.max_risk_per_trade_pct > 5:
            errors.append("trading.max_risk_per_trade_pct should be <= 5%")

        # Validate risk config
        if self._config.risk.max_drawdown_pct <= 0:
            errors.append("risk.max_drawdown_pct must be > 0")

        if self._config.risk.dd_halt_threshold_pct < self._config.risk.dd_reduce_threshold_pct:
            errors.append("risk.dd_halt_threshold_pct must be >= dd_reduce_threshold_pct")

        # Validate mode
        if self._config.mode not in ["paper", "live"]:
            errors.append("mode must be 'paper' or 'live'")

        return errors

    def get_info(self) -> Dict[str, Any]:
        """Get configuration info."""
        return {
            "path": str(self._config_path) if self._config_path else None,
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
            "mode": self._config.mode,
            "symbols": self._config.trading.symbols,
            "max_positions": self._config.trading.max_positions,
            "validation_errors": self.validate(),
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "TradingConfig",
    "RiskConfig",
    "ExecutionConfig",
    "BrokerConfig",
    "MonitoringConfig",
    "PluginConfig",
    "SystemConfig",
    "ConfigManager",
]
