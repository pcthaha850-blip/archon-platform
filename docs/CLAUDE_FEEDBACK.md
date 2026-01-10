# Claude Feedback Log

Track AI wins and mistakes to improve future sessions.
**Before important sessions, paste relevant "Mistakes" as context.**

---

## Wins

| Date | Description |
|------|-------------|
| 2026-01-10 | Excellent module extraction from monolithic v63 file into 9 clean modules |
| 2026-01-10 | Created 132 comprehensive unit tests, all passing |
| 2026-01-10 | Followed TDD approach for position_manager.py |
| 2026-01-10 | Kept all modules under 500 lines (target met) |

---

## Mistakes

| Date | Mistake | Fix Applied |
|------|---------|-------------|
| - | - | - |

*No mistakes logged yet. Update this when Claude violates the contract.*

---

## How to Use This File

### Before a Critical Session

Paste this context to Claude:

```
Claude, review docs/CLAUDE_FEEDBACK.md.

Previously you made these mistakes:
[paste relevant mistakes]

You MUST avoid these mistakes now.
Re-read CLAUDE.md and summarize the rules that prevent these mistakes.
```

### After a Session

Update this file with:
- **Wins:** Good behaviors to reinforce
- **Mistakes:** Violations to prevent next time

---

## Common Mistake Patterns to Watch

- [ ] Tried to modify 🔒 LOCKED module without override
- [ ] Wrote implementation before tests
- [ ] Created file > 500 lines
- [ ] Skipped Session Orientation
- [ ] Modified files outside confirmed scope
- [ ] Forgot to tag changes with `# ARCHON_[type]: [id]`
- [ ] Didn't update MODULE REGISTRY after adding module
- [ ] Created `*_v2.py` or `*_complete.py` file

---

## Session History

| Date | Mode | Task | Outcome |
|------|------|------|---------|
| 2026-01-10 | REFACTOR | Extract modules from v63 monolith | ✅ 9 modules extracted |
| 2026-01-10 | TEST | Create unit tests for extracted modules | ✅ 132 tests passing |
| 2026-01-10 | DOCS | Update CLAUDE.md to v3.0 contract | ✅ Contract enforced |

---

**Remember:** This file trains Claude through explicit reminders, not model fine-tuning.
