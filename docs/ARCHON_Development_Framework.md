# ARCHON Development Framework & AI Integration Guide

**Version:** 2.0 - Fresh Start Protocol
**Date:** January 2026
**Prepared for:** Thahapc

---

## Root Cause Analysis: Why Builds Keep Breaking

### 1. The Monolith Problem
Large files (13,000+ lines) overwhelm AI context windows. Changes cascade unpredictably, bugs become impossible to track.

### 2. Version Chaos
Files like `v6`, `v62`, `v63`, `archon_ri_v63_complete-1.py` indicate copy-paste versioning instead of proper Git branch management.

### 3. State Pollution
Database files (.db), log files, and runtime artifacts mixed with source code cause different behavior on each run.

### 4. Missing Automated Tests
Changes break things silently. You don't know until days later when running the bot.

### 5. AI Context Limitations
When Claude tries to fix a bug in a 13K line file, it can only see portions at a time. Fixes in one area break logic elsewhere.

---

## The Solution: Two-Product Architecture

| Product | Purpose | Tech Stack |
|---------|---------|------------|
| **ARCHON RI** | Research & Intelligence - Backtesting, strategy dev, ML | Python 3.11+ |
| **ARCHON PRIME** | Production Trading - Live execution, risk management | Python + C++ |

### Shared Core Libraries
- **archon-core**: Risk models (CVaR, Kelly), signal validation
- **archon-data**: Market data handlers, persistence layer
- **archon-brokers**: MT5, IB, OANDA adapters
- **archon-ai**: Gemini integration, Guardian & Intelligence agents

---

## AI Tool Selection & Usage Strategy

### Claude Models (Development Phase)

| Model | Use For | When |
|-------|---------|------|
| **Claude Code (Sonnet 4)** | Daily coding, bug fixes, features | 80% of work |
| **Claude Opus 4.5** | Architecture, complex debugging, review | When stuck |
| **Claude Sonnet 4.5** | Extended sessions, agentic coding | Large features |

### Gemini Integration (Runtime Phase)

Use Gemini for:
- Market sentiment analysis during trading
- Real-time trade validation and risk assessment
- Self-learning feedback loops from trade outcomes
- Anomaly detection and health monitoring

**Do NOT use Gemini for:**
- Writing code (Claude is superior)
- Architecture decisions
- Debugging development issues

### The Golden Rule
**One AI, One Context, One Task**

- Use Claude Code for implementation in small, focused sessions
- Each session should focus on ONE module (< 500 lines)
- Update CLAUDE.md with each module's purpose and interfaces
- Commit after each successful change

---

## File Size Rules

| Lines | Status | Action |
|-------|--------|--------|
| < 300 | IDEAL | Perfect for AI assistance |
| 300-500 | ACCEPTABLE | Consider splitting if complex |
| 500-1000 | WARNING | Plan refactoring |
| > 1000 | CRITICAL | Must split immediately |

### Splitting Strategy
When a file exceeds limits, split by responsibility:

```
risk_engine.py (800 lines) → split into:
├── risk_engine/cvar.py      - CVaR calculations
├── risk_engine/kelly.py     - Kelly fraction sizing
├── risk_engine/regime.py    - Regime detection
└── risk_engine/engine.py    - Main orchestration
```

**Never do this:**
- `risk_engine_v2.py`
- `risk_engine_complete.py`
- `risk_engine_final.py`

Use Git branches instead!

---

## CLAUDE.md Best Practices

### What Goes in CLAUDE.md

| Section | Purpose |
|---------|---------|
| Project Context | What the project does, who it's for, key goals |
| Architecture | Module map, dependencies, data flow |
| Critical Rules | Absolute constraints Claude must never violate |
| Conventions | Naming, formatting, patterns |
| Commands | Shortcuts for common tasks |
| Current State | What's working, broken, in progress |

### The Golden Rule
CLAUDE.md should tell Claude everything it needs to work on your project WITHOUT reading any other files first.

---

## Effective Claude Code Sessions

### The One Task Rule

| BAD SESSION | GOOD SESSION |
|-------------|--------------|
| "Fix the risk engine, add logging, update tests, and refactor the broker interface" | "Add CVaR calculation to RiskEngine.evaluate() method" |

### Session Workflow

1. **Start with context:** "Read CLAUDE.md and core/risk_engine.py"
2. **State your goal:** "I need to add Kelly fraction bounds checking"
3. **Ask for a plan:** "What's your approach before writing code?"
4. **Review the plan** before Claude executes
5. **Test immediately:** "Run pytest tests/test_risk_engine.py"
6. **Update CLAUDE.md** if you changed module status

### Pro Tip
Start every session with:
> "Read CLAUDE.md first, then tell me what you understand about [specific module]."

---

## Starting a New Feature

| Step | What to Say to Claude |
|------|----------------------|
| 1 | "Read CLAUDE.md and explain the current state of the risk engine" |
| 2 | "I want to add Hurst exponent regime detection. What files need changes?" |
| 3 | "Write the test cases first before implementing" |
| 4 | "Now implement the feature to pass those tests" |
| 5 | "/test-risk" (verify tests pass) |
| 6 | "Update CLAUDE.md module registry with the new file" |

## Fixing a Bug

| Step | What to Say to Claude |
|------|----------------------|
| 1 | "Read CLAUDE.md. The Signal Gate is rejecting valid signals." |
| 2 | "Read core/signal_gate.py and explain the consensus logic" |
| 3 | "Write a failing test that reproduces this bug" |
| 4 | "Fix the bug and verify the test passes" |
| 5 | "/test" (verify no regressions) |

**Bug Fix Rule:** Always write a failing test that reproduces the bug BEFORE fixing it.

---

## Common Mistakes to Avoid

### Mistake #1: Vague Instructions

| DON'T SAY | DO SAY |
|-----------|--------|
| "Fix the trading system" | "Fix the position sizing bug in core/risk_engine.py line 145" |
| "Make it faster" | "Optimize the CVaR loop in risk_engine.py to use vectorized numpy" |
| "Add error handling" | "Add try/except around MT5 API calls in brokers/mt5.py" |

### Mistake #2: Context Overload
- Don't paste entire files into chat - use "Read file.py"
- Don't ask Claude to work on 5 files at once
- Don't combine unrelated changes in one session

### Mistake #3: Skipping Tests
- Never say "just implement it, we'll test later"
- Tests catch bugs before they cascade
- Tests let Claude verify its own work

### Mistake #4: Not Updating CLAUDE.md
If you add a new file and don't update the module registry, Claude won't know it exists in the next session.

---

## Quick Reference Card

| Situation | What to Tell Claude |
|-----------|---------------------|
| Start of session | "Read CLAUDE.md first" |
| Before coding | "What's your plan before we start?" |
| New feature | "Write the tests first" |
| Bug fix | "Write a failing test that reproduces it" |
| After changes | "/test" |
| File getting long | "This file is over 500 lines. Split it." |
| End of session | "Update CLAUDE.md with what changed" |
| Confused behavior | "Stop. Re-read CLAUDE.md and explain what you understand." |

---

## Git Workflow

```
[main] ◄────────────────────────────────────────────────
   │                                                   │
   │    [develop] ◄─────────────────────────────────   │
   │        │                                      │   │
   │        │    [feature/add-vwap] ◄──────────   │   │
   │        │         │                        │   │   │
   │        │         │  1. Create branch      │   │   │
   │        │         │  2. Write tests first  │   │   │
   │        │         │  3. Implement feature  │   │   │
   │        │         │  4. All tests pass     │   │   │
   │        │         │  5. PR to develop      │   │   │
   │        │         └────────────────────────┘   │   │
   │        └──────────────────────────────────────┘   │
   └───────────────────────────────────────────────────┘
```

### Branch Naming
```
feature/add-vwap-execution
fix/kelly-calculation-error
hotfix/mt5-reconnection
refactor/split-risk-engine
```

### Commit Messages
```
feat: Add VWAP execution algorithm
fix: Correct Kelly criterion for negative z-scores
refactor: Split signal_gate into modular components
test: Add integration tests for risk engine
docs: Update CLAUDE.md with new modules
```

---

## Checklist Before Live Trading

- [ ] Paper trading for 30+ days
- [ ] Shadow mode validation passed
- [ ] All unit tests passing (80%+ coverage)
- [ ] Integration tests passing
- [ ] Drawdown protection verified
- [ ] Kill switch tested
- [ ] Panic hedge thresholds calibrated
- [ ] Gemini API rate limits understood
- [ ] Backup strategy documented
- [ ] Emergency contact list ready

---

**Remember:** Your architecture is solid. The bugs aren't in the design—they're in the process. Fix the process, and the system will stabilize.
