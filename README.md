<p align="center">
  <img src="assets/logos/archon_prime_logo_1.png" alt="ARCHON PRIME" width="400">
</p>

<h1 align="center">ARCHON PRIME</h1>

<p align="center">
  <strong>Plugin-based Real-time Intelligence for Market Execution</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#documentation">Documentation</a>
</p>

---

## Overview

ARCHON PRIME is an institutional-grade, plugin-based trading platform designed for automated forex trading. Built from the ground up with modularity, safety, and performance in mind.

| Metric | Target |
|--------|--------|
| Annual Returns | 25-40% |
| Sharpe Ratio | 3.5-5.5 |
| Maximum Drawdown | <10% |
| Win Rate | 75-82% |

## Features

- **Plugin Architecture** - Hot-swappable strategies, risk managers, and execution engines
- **Event-Driven Core** - Async pub/sub communication between all components
- **Multi-Layer Risk** - Kelly sizing, CVaR, drawdown protection, correlation limits
- **Stealth Execution** - Anti-detection with jitter, order splitting, pattern disguise
- **Multi-Broker Support** - MT5, OANDA, Interactive Brokers adapters
- **Shadow Mode** - Test new logic safely without affecting live trades

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EVENT BUS                                │
│    TICK → SIGNAL → RISK → STEALTH → EXECUTE → RESULT            │
└─────────────────────────────────────────────────────────────────┘
         │           │          │           │
    ┌────┴────┐ ┌────┴────┐ ┌───┴───┐ ┌────┴────┐
    │STRATEGY │ │  RISK   │ │STEALTH│ │EXECUTION│
    │ PLUGINS │ │ PLUGINS │ │PLUGINS│ │ PLUGINS │
    └─────────┘ └─────────┘ └───────┘ └─────────┘
```

### Plugin Categories

| Category | Plugins | Purpose |
|----------|---------|---------|
| **Core** | 6 | Event bus, plugin loader, config, orchestrator |
| **Strategies** | 2+ | TSM, VMR, and custom strategies |
| **Risk** | 3+ | Kelly sizer, CVaR, drawdown controller |
| **Execution** | 2+ | Ghost executor, TWAP |
| **Brokers** | 2+ | MT5 adapter, paper broker |
| **Monitoring** | 2+ | Metrics collector, alert manager |

## Installation

```bash
# Clone the repository
git clone https://github.com/pcthaha850-blip/archon-platform.git
cd archon-platform

# Install dependencies
pip install -e .

# Run tests
pytest tests/ -v
```

## Usage

### Paper Trading

```bash
python -m archon_prime.main --config config/paper.yaml
```

### Live Trading

```bash
python -m archon_prime.main --config config/live.yaml --mode live
```

### Dry Run (Validate Config)

```bash
python -m archon_prime.main --config config/paper.yaml --dry-run
```

## Configuration

Configuration is managed via YAML files with environment variable support:

```yaml
mode: paper
broker:
  type: mt5
  server: ${MT5_SERVER}
  login: ${MT5_LOGIN}
  password: ${MT5_PASSWORD}

trading:
  symbols: ["EURUSD", "GBPUSD", "XAUUSD"]
  max_positions: 2

risk:
  max_risk_per_trade_pct: 0.5
  max_drawdown_pct: 10.0
```

## Documentation

- [Architecture Plan](docs/ARCHON_PRIME_ARCHITECTURE_PLAN.md) - Comprehensive system design
- [Development Framework](docs/ARCHON_Development_Framework.md) - Development guidelines
- [CLAUDE.md](CLAUDE.md) - AI assistant control contract

## Project Structure

```
archon-platform/
├── archon_prime/           # Production trading platform
│   ├── core/               # Core infrastructure
│   │   ├── event_bus.py    # Async pub/sub
│   │   ├── plugin_base.py  # Plugin base classes
│   │   ├── plugin_loader.py# Dynamic loading
│   │   ├── config_manager.py
│   │   └── orchestrator.py
│   └── plugins/            # All plugins
│       ├── strategies/     # Trading strategies
│       ├── risk/           # Risk management
│       ├── execution/      # Order execution
│       ├── brokers/        # Broker adapters
│       └── monitoring/     # System monitoring
├── shared/                 # Shared libraries
│   └── archon_core/        # Core modules (132 tests)
├── tests/                  # Test suites
├── config/                 # Configuration files
├── assets/                 # Brand assets
└── docs/                   # Documentation
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific module tests
pytest tests/unit/test_event_bus.py -v

# Run with coverage
pytest tests/ --cov=archon_prime --cov-report=html
```

## License

Proprietary - ARCHON RI Research Institute / DB Investing

---

<p align="center">
  <strong>ARCHON PRIME</strong> - Simple core, powerful plugins, total control.
</p>
