# Claude Code Cheat Sheet - ARCHON Platform

**Quick Reference for AI-Assisted Development**

---

## Session Startup

```
1. "Read CLAUDE.md first"
2. "Explain what you understand about [module]"
3. State ONE specific goal
```

---

## File Size Rules

| Lines | Status | Action |
|:-----:|:------:|:-------|
| <300 | IDEAL | Perfect for AI |
| 300-500 | OK | Plan split |
| 500-1000 | WARN | Split soon |
| >1000 | STOP | Split NOW |

---

## Development Commands

| Command | Action |
|---------|--------|
| `/test` | `pytest tests/ -v --tb=short` |
| `/test-risk` | `pytest tests/test_risk_engine.py -v` |
| `/lint` | `ruff check . && black --check .` |
| `/size-check` | `find . -name '*.py' -exec wc -l {} + \| sort -n \| tail -20` |
| `/coverage` | `pytest tests/ --cov=shared --cov-report=html` |

---

## Trading Commands

| Command | Action |
|---------|--------|
| `/paper` | `python -m archon_prime.main --mode paper --capital 500` |
| `/simulation` | `python -m archon_prime.main --mode simulation` |
| `/dashboard` | `python -m archon_prime.ui.dashboard --port 8080` |
| `/backtest` | `python -m archon_ri.backend.engine.backtest` |

---

## Workflow: New Feature

```
1. "What files need to change for [feature]?"
2. "Write the tests first"
3. "Implement to pass tests"
4. "/test"
5. "Update CLAUDE.md"
```

---

## Workflow: Bug Fix

```
1. "Write a failing test that reproduces it"
2. "Fix the bug"
3. "/test"
4. "Update CLAUDE.md"
```

---

## Workflow: Refactor

```
1. "/size-check"
2. If >500 lines: "Split [file] into <300 line modules"
3. "/test"
4. "Update CLAUDE.md registry"
```

---

## Claude Modes

| Mode | Trigger | Focus |
|------|---------|-------|
| **Strategy** | "Enter Strategy Mode" | Architecture, design |
| **Refactor** | "Enter Refactor Mode" | Split files, organize |
| **Test** | "Enter Test Mode" | TDD, coverage |
| **Audit** | "Enter Audit Mode" | Compliance, docs |

---

## AI Selection

### Development (Claude)
| Model | Use For |
|-------|---------|
| Sonnet 4 | Daily coding (80%) |
| Opus 4.5 | Architecture, stuck |
| Sonnet 4.5 | Large features |

### Runtime (Gemini)
| Agent | Purpose |
|-------|---------|
| Intelligence | Market analysis |
| Guardian | Risk validation |

---

## Critical Rules

### DO
- [x] Max 500 lines per file
- [x] Tests before code
- [x] pytest before commit
- [x] Git branches (feature/, fix/)
- [x] Update CLAUDE.md
- [x] async/await for I/O

### DON'T
- [ ] Monolithic files (v63_complete)
- [ ] Commit .db, .log, __pycache__
- [ ] Skip Signal Gate
- [ ] >2 concurrent positions
- [ ] Bypass 15% drawdown halt

---

## Risk Thresholds

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Flash Crash | 2% / 60s | Hedge all |
| Vol Spike | 3x ATR | Halt trades |
| Spread | 10x normal | Close limits |
| Drawdown | 5% | Kill switch |

---

## Quick Prompts

| Situation | Say This |
|-----------|----------|
| Start | "Read CLAUDE.md first" |
| Plan | "What's your approach?" |
| Feature | "Write tests first" |
| Bug | "Write failing test first" |
| Done | "/test" |
| Long file | "Split this file" |
| End | "Update CLAUDE.md" |
| Confused | "Stop. Re-read CLAUDE.md" |

---

## Git Branches

```
feature/add-vwap-execution
fix/kelly-calculation-error
hotfix/mt5-reconnection
refactor/split-risk-engine
```

## Commit Format

```
feat: Add VWAP execution
fix: Correct Kelly calc
refactor: Split signal_gate
test: Add risk tests
docs: Update CLAUDE.md
```

---

## Module Status Icons

| Icon | Meaning |
|:----:|---------|
| STABLE | Production ready |
| TESTING | Under test |
| WIP | Work in progress |
| NOT EXTRACTED | Needs extraction |

---

**One AI. One Context. One Task.**
