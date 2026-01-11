# ARCHON PRIME — Operator & Owner Guide

## 1. What ARCHON PRIME *Is* (Plain Language)

ARCHON PRIME is an **institution-grade AI trading execution platform**.

It is **not**:
- A retail trading bot
- A plug-and-play EA
- A black-box signal seller

It **is**:
- A governed execution engine
- A signal-to-execution control system
- A risk-aware, auditable trading platform
- A system designed to be *operated*, not "run once"

Think of it as a **trading control room**, not a robot.

---

## 2. What's Inside ARCHON PRIME (System Map)

### Core Components
- **Auth Layer** – Users, JWT, sessions
- **Profiles** – MT5 account isolation
- **Trading Engine** – Positions, history, stats
- **Signal Gate** – *Single authoritative ingress*
- **WebSocket Layer** – Real-time state visibility
- **Admin Layer** – Governance & intervention
- **Background Workers** – State reconciliation
- **Test Suite** – Proof of behavior

Nothing executes trades unless it passes through **Signal Gate**.

---

## 3. How You *Use* ARCHON PRIME (Daily Operation)

### Normal Daily Flow
1. **Signals are submitted** via `/api/v1/signals/{profile_id}/submit`
2. Signal Gate validates:
   - Idempotency
   - Rate limits
   - Provenance
   - Risk state
3. Approved signals execute on MT5
4. State updates broadcast via WebSocket
5. Admin dashboard reflects everything in real time

You **observe**, not babysit.

---

### Admin Usage
Admins can:
- Monitor system health
- View live positions & equity
- Acknowledge alerts
- Force disconnect profiles
- Trigger emergency hedges
- Broadcast system messages

Admins **do not trade** — they govern.

---

## 4. How to Start Using It (Step-by-Step)

### Initial Setup
1. Deploy API + workers
2. Configure environment variables
3. Connect MT5 profiles
4. Verify WebSocket feed
5. Submit test signals
6. Confirm admin visibility

Once verified, the system runs continuously.

---

## 5. How to Maintain ARCHON PRIME

### Daily
- Check dashboard
- Review alerts
- Confirm workers are alive
- Watch WebSocket health

### Weekly
- Review signal stats
- Export audit logs
- Check MT5 connectivity stability

### Monthly
- Rotate secrets
- Review access permissions
- Archive logs
- Review performance metrics

### What You *Do Not* Do
- No refactoring
- No feature additions
- No "quick fixes" in production

The core is frozen.

---

## 6. How to Handle Problems (Mental Model)

ARCHON PRIME is designed so:
- **Failures are visible**
- **Failures are isolated**
- **Failures are recoverable**

If something breaks:
1. Alert triggers
2. Admin sees it
3. Runbook tells you what to do
4. System recovers
5. Audit trail remains intact

You never guess.

---

## 7. How to Upgrade or Change Things (Safely)

### Allowed
- New signal strategies (outside core)
- New dashboards
- New analytics
- New deployment environments

### Not Allowed
- Changing Signal Gate logic
- Bypassing admin authority
- Modifying execution paths
- Altering audit semantics

If it touches **execution or governance**, it requires a new version.

---

## 8. How to Think About It (Most Important)

ARCHON PRIME is:
- A **system**, not a script
- A **platform**, not a product
- A **trust machine**, not a profit hack

Your job is not to "run trades".
Your job is to **operate stability**.

---

## 9. When to Touch It Again

Only when:
- You're deploying to production
- You're onboarding institutions
- You're preparing compliance evidence
- You're launching commercially

Otherwise — **leave it alone**.

---

## 10. Maintenance Checklists

### Daily Checklist
- [ ] Dashboard accessible
- [ ] All workers running (green status)
- [ ] WebSocket connections stable
- [ ] No unacknowledged P0/P1 alerts
- [ ] MT5 profiles connected

### Weekly Checklist
- [ ] Review signal pass/block ratio
- [ ] Export audit logs
- [ ] Check position reconciliation drift
- [ ] Review error logs
- [ ] Verify backup completion

### Monthly Checklist
- [ ] Rotate JWT secrets
- [ ] Rotate encryption keys
- [ ] Review user access (who has what)
- [ ] Archive old logs (>30 days)
- [ ] Review performance metrics
- [ ] Update runbooks if needed

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial operator guide |
