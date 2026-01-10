# ARCHON Platform - Claude Control Contract

**Version:** 3.0.0
**Last Updated:** January 2026
**AI Assistant:** Claude (Opus 4.5 / Sonnet 4)

---

# EXECUTION CONTRACT (READ FIRST, OBEY ALWAYS)

Claude, before you do ANY work:

## 1. ORIENTATION (Required at session start)

Summarize:
- **Product line:** ARCHON RI vs ARCHON PRIME
- **Module:** Which module you are working on
- **Status:** Current module status from MODULE REGISTRY
- **Constraints:** Applicable constraints (file size, risk, safety)

## 2. CONFIRMATION (Required before any code)

Ask the user to confirm:
- The task scope in one sentence
- Which repo/module we are touching
- Task type: `bugfix` | `feature` | `refactor` | `docs` | `test`

## 3. HARD STOPS (You MUST refuse)

You **MUST**:
- **REFUSE** to touch modules marked "🔒 LOCKED" unless explicitly told: `"Override LOCK for [module]"`
- **REFUSE** to create new monolith files or `*_v2.py` / `*_complete.py` / `*_unified.py`
- **REFUSE** to proceed if file size > 500 lines until you propose a split plan
- **REFUSE** to write implementation before tests
- **REFUSE** to modify files outside the confirmed scope

---

# NON-NEGOTIABLE RULES

These rules are absolute. No exceptions. No workarounds.

## File Size
- **MAX 500 lines per file.** If > 500, SPLIT FIRST.
- **Target < 300 lines** for new modules.
- Run `/size-check` before any commit.

## Testing
- **ALL new logic must have tests written FIRST.**
- Show tests before implementation. Always.
- Provide exact test commands.

## Safety Systems
- **NEVER skip Signal Gate consensus check** for any path that sends orders.
- **NEVER bypass drawdown halt thresholds** in config.
- **NEVER trade during high-impact news** (30 min buffer).
- **NEVER exceed 2 concurrent live positions** (ARCHON PRIME).

## Code Quality
- **ALL I/O MUST be async/await.**
- **NEVER commit** `.db`, `.log`, `.env`, `__pycache__`, `*.pyc`.
- **NEVER create** `*_v2.py`, `*_v3.py`, `*_complete.py`, `*_unified.py`.

## Change Discipline
- **One focused task per session.**
- **Tag all modifications:** `# ARCHON_[FEAT|FIX|REF]: <short-id>`
- **Atomic commits** with proper type prefixes.

---

# CHANGE CONTRACT: TESTABLE, REVERSIBLE, AUDITABLE

For **EVERY** change you make:

## 1. TESTABLE
- Write tests FIRST
- Show ONLY the tests initially
- Provide exact test command: `pytest tests/unit/test_[module].py -v`
- Only after user confirms, write implementation

## 2. REVERSIBLE
- One focused task per session
- Tag modified code with `# ARCHON_[FEAT|FIX|REF]: <short-id>`
- Assume a single, atomic commit per change
- List all files touched at end of session

## 3. AUDITABLE
- Update MODULE REGISTRY when adding/modifying modules
- Provide behavioral summary: what changed and why
- Explain impact on: Signal Gate, Risk Engine, Ghost Mode, Brokers
- Propose additional tests to increase confidence

---

# SESSION MODES

You operate in **fixed modes**, not free-form conversation.

## MODE: AUDIT & ORIENTATION

```
MODE: AUDIT & ORIENTATION

1. Read CLAUDE.md fully.
2. Read [file or module].
3. Answer ONLY:
   a) What module is this?
   b) How does it fit into ARCHON RI / PRIME architecture?
   c) What are the critical constraints for this module?
   d) Current status in MODULE REGISTRY.
4. DO NOT propose changes yet.
```

Use this before touching any core module.

## MODE: BUGFIX

```
MODE: BUGFIX

Context:
- Module: [path/to/file.py]
- Symptoms: [describe clearly]
- Tests: [existing test files if any]

Steps:
1. Propose a minimal failing test that reproduces the bug.
2. Show ONLY the test code first, no fixes.
3. After user confirms, propose a minimal fix.
4. Tag all changes: "# ARCHON_FIX: [short-id]"
5. Provide pytest command to run.
6. Summarize: files changed, functions touched, tags used.
```

## MODE: NEW FEATURE

```
MODE: NEW FEATURE

Feature: [one sentence]
Repo: [archon_ri | archon_prime | shared]
Impact: [core | risk | execution | ui | ai | data]

Steps:
1. List ONLY:
   - Files to be created
   - Files to be modified
2. For each file:
   - Responsibility (2 sentences max)
   - Estimated lines (must be < 300)
3. Propose tests FIRST:
   - New test files
   - New test cases
4. WAIT for approval before writing any code.

After approval:
- Write ONLY the tests first
- Then write implementation to make tests pass
- Tag all new code: "# ARCHON_FEAT: [short-id]"
```

## MODE: REFACTOR / SPLIT

```
MODE: REFACTOR / SPLIT

File: [path]
Lines: [N]

Steps:
1. Analyze and propose:
   - New module boundaries
   - New file names
   - Public API per new file
2. Confirm each new file < 300 lines
3. After approval:
   - Show NEW files one by one
   - Show updated imports
4. Provide:
   - /test command
   - /size-check command
5. Update MODULE REGISTRY
```

## MODE: CODE REVIEW

```
MODE: CODE REVIEW

Files to review: [list]

Tasks:
1. Check file sizes (< 500 lines)
2. Verify test coverage exists
3. Check for safety bypasses:
   - Signal Gate skips
   - Drawdown halt bypasses
   - Hardcoded credentials
4. Identify code smells:
   - Monolithic functions (> 50 lines)
   - Missing error handling
   - Sync I/O in async context
5. Propose improvements with priority
```

---

# PROJECT OVERVIEW

ARCHON is an institutional-grade AI trading platform with two product lines:

| Product | Purpose | Tech Stack |
|---------|---------|------------|
| **ARCHON RI** | Research & Intelligence - Backtesting, strategy dev, ML | Python 3.11+ |
| **ARCHON PRIME** | Production Trading - Live execution, risk management | Python + C++ |

**Target Markets:** Forex (XAUUSD, majors) via MT5, expansion to IB and FIX
**Account Focus:** $500-$10,000 retail to institutional
**Performance Targets:** 25-40% annual returns, Sharpe 3.5-5.5, max DD <10%

---

# MODULE REGISTRY

## Core Modules (shared/archon_core/)

| Module | Path | Lines | Status | Lock |
|--------|------|-------|--------|------|
| Constants | constants.py | 281 | ✅ Stable | |
| Exceptions | exceptions.py | 425 | ✅ Stable | |
| Correlation Tracker | correlation_tracker.py | 350 | ✅ Stable | |
| Kelly Criterion | kelly_criterion.py | 264 | ✅ Stable | |
| CVaR Engine | cvar_engine.py | 265 | ✅ Stable | |
| Panic Hedge | panic_hedge.py | 419 | ✅ Stable | 🔒 |
| Signal Gate | signal_gate.py | 397 | ✅ Stable | 🔒 |
| Hurst Regime | hurst_regime.py | ~300 | ✅ Stable | |
| Position Manager | position_manager.py | 420 | ✅ Stable | |

## Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| test_kelly_criterion.py | 17 | ✅ Pass |
| test_cvar_engine.py | 13 | ✅ Pass |
| test_signal_gate.py | 17 | ✅ Pass |
| test_panic_hedge.py | 30 | ✅ Pass |
| test_correlation_tracker.py | 28 | ✅ Pass |
| test_position_manager.py | 27 | ✅ Pass |

**Total: 132 tests passing**

## Modules To Extract

| Module | Source | Target | Priority |
|--------|--------|--------|----------|
| Spread Filter | ARCHON_RI_V10 | shared/archon_core/ | HIGH |
| Circuit Breakers | ARCHON_RI_V10 | shared/archon_core/ | HIGH |
| State Manager | ARCHON_RI_V10 | shared/archon_data/ | MEDIUM |
| Orchestrator | ARCHON_RI_V10 | archon_prime/ | MEDIUM |

## Broker Adapters (NOT YET EXTRACTED)

| Module | Target Path | Lines | Status |
|--------|-------------|-------|--------|
| Base Broker | shared/archon_brokers/base.py | <200 | 🔧 Pending |
| MT5 Adapter | shared/archon_brokers/mt5_adapter.py | <500 | 🔧 Pending |
| OANDA Adapter | shared/archon_brokers/oanda_adapter.py | <400 | 🔧 Pending |
| IB Adapter | shared/archon_brokers/ib_adapter.py | <500 | 🔧 Pending |

---

# PROJECT STRUCTURE

```
archon-platform/
├── CLAUDE.md                    # THIS FILE (READ FIRST)
├── pyproject.toml               # Dependencies & build
│
├── shared/                      # Shared libraries
│   ├── archon_core/            # Core trading logic (EXTRACTED)
│   │   ├── constants.py        # 281 lines ✅
│   │   ├── exceptions.py       # 425 lines ✅
│   │   ├── correlation_tracker.py  # 350 lines ✅
│   │   ├── kelly_criterion.py  # 264 lines ✅
│   │   ├── cvar_engine.py      # 265 lines ✅
│   │   ├── panic_hedge.py      # 419 lines ✅ 🔒
│   │   ├── signal_gate.py      # 397 lines ✅ 🔒
│   │   ├── hurst_regime.py     # ~300 lines ✅
│   │   └── position_manager.py # 420 lines ✅
│   │
│   ├── archon_data/            # Data layer (PENDING)
│   ├── archon_brokers/         # Broker adapters (PENDING)
│   └── archon_ai/              # AI agents (PENDING)
│
├── archon_ri/                   # Research Platform (PENDING)
├── archon_prime/                # Production Platform (PENDING)
│
├── config/
│   ├── paper.yaml
│   └── live.yaml
│
├── tests/
│   ├── conftest.py             # Shared fixtures
│   └── unit/                   # 132 tests ✅
│
└── docs/
    └── ARCHON_Development_Framework.md
```

---

# PROTECTION SYSTEM

## Panic Hedge Thresholds (🔒 LOCKED - Do not modify without override)

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Flash Crash | 2% drop in 60s | Hedge all positions |
| Volatility Spike | 3x ATR | Halt new trades |
| Spread Explosion | 10x normal | Close limit orders |
| Drawdown Breach | 5% | Kill switch |

## Risk Parameters

```yaml
risk:
  max_risk_per_trade_pct: 0.5    # Max 0.5% per trade
  max_total_risk_pct: 2.0        # Max 2% total exposure
  max_concurrent_positions: 2    # Never exceed 2
  dd_reduce_threshold_pct: 10.0  # Reduce risk at 10% DD
  dd_halt_threshold_pct: 15.0    # Stop trading at 15% DD
  kelly_min_z: 1.25              # Minimum z-score for Kelly
  kelly_scale: 0.15              # Kelly scaling factor
```

---

# COMMANDS

## Development
```bash
# Run all tests
pytest tests/ -v --tb=short

# Run specific module tests
pytest tests/unit/test_kelly_criterion.py -v

# Check code quality
ruff check . && black --check .

# CRITICAL: Check file sizes
find . -name '*.py' -exec wc -l {} + | sort -n | tail -20

# Coverage report
pytest tests/ --cov=shared --cov-report=html
```

## Verification
```bash
# Full verification before commit
pytest tests/ -v && ruff check . && find . -name '*.py' -exec wc -l {} + | sort -n | tail -10
```

---

# GIT WORKFLOW

## Branch Naming
```
feature/add-vwap-execution
fix/kelly-calculation-error
hotfix/mt5-reconnection
refactor/split-risk-engine
```

## Commit Messages
```
feat: Add VWAP execution algorithm
fix: Correct Kelly criterion for negative z-scores
refactor: Split signal_gate into modular components
test: Add integration tests for risk engine
docs: Update CLAUDE.md with new modules
```

## Commit Checklist
- [ ] All tests pass
- [ ] No file > 500 lines
- [ ] MODULE REGISTRY updated
- [ ] Appropriate tags in code

---

# TESTING REQUIREMENTS

## Before Any Commit
- [ ] All unit tests pass
- [ ] No linting errors
- [ ] Coverage > 80% for modified files
- [ ] File size < 500 lines
- [ ] Code tagged with `# ARCHON_[type]: [id]`

## Before Merge to Develop
- [ ] All integration tests pass
- [ ] MODULE REGISTRY updated
- [ ] CLAUDE.md updated if structure changed

## Before Merge to Main
- [ ] 30+ day paper trading record
- [ ] Security audit passed
- [ ] All locked modules untouched (or override documented)

---

# AI TOOL SELECTION

## Development Phase (Claude)

| Model | Use For | When |
|-------|---------|------|
| **Claude Code (Sonnet 4)** | Daily coding, bug fixes, features | 80% of work |
| **Claude Opus 4.5** | Architecture, complex debugging, review | When stuck |

## Runtime Phase (Gemini)

| Agent | Purpose |
|-------|---------|
| **Intelligence** | Market sentiment, trade validation |
| **Guardian** | Security monitoring, anomaly detection |

**WARNING:** Do NOT use Gemini for code, debugging, or architecture.

---

# QUICK REFERENCE

| Task | Command |
|------|---------|
| Run tests | `pytest tests/ -v` |
| Size check | `find . -name '*.py' -exec wc -l {} + \| sort -n` |
| Lint | `ruff check .` |
| Format | `black .` |

---

# SESSION START TEMPLATE

When starting a session, Claude should respond with:

```
## Session Orientation

**Product:** [ARCHON RI / ARCHON PRIME / Shared]
**Module:** [module name and path]
**Status:** [from MODULE REGISTRY]
**Lock Status:** [🔒 LOCKED / Unlocked]

**Applicable Constraints:**
- File size limit: 500 lines (target < 300)
- Tests required: Yes
- Safety systems affected: [list if any]

**Please confirm:**
1. Task scope: [your understanding]
2. Task type: [bugfix | feature | refactor | docs | test]
3. Files in scope: [list]

Awaiting confirmation before proceeding.
```

---

**Contract Version:** 3.0.0
**Last Updated:** January 2026

**Remember:** This is a CONTRACT, not documentation. Every rule is binding. Every mode is mandatory. Every check is required.
