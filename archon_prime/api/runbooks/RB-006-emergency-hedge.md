# RB-006: Emergency Hedge Escalation

## Overview

| Field | Value |
|-------|-------|
| **Runbook ID** | RB-006 |
| **Title** | Emergency Hedge Escalation |
| **Severity** | P0 EMERGENCY |
| **Primary Responder** | Risk Officer |
| **Escalation** | CTO → CEO |
| **Last Updated** | January 2026 |

---

## ⚠️ CRITICAL NOTICE

This runbook is invoked when **capital is at immediate risk**.

**Time is critical.** Every minute of delay can result in financial loss.

**Do not hesitate.** If in doubt, execute the kill switch first, investigate later.

---

## 1. Emergency Triggers

### Automatic Triggers (System-Initiated)

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Flash Crash | 2% drop in 60 seconds | Auto-hedge all positions |
| Volatility Spike | 3x ATR | Halt new trades |
| Spread Explosion | 10x normal | Close limit orders |
| Drawdown Breach | 5% single position | Alert Risk Officer |
| Drawdown Critical | 10% portfolio | Auto kill switch |

### Manual Triggers (Human-Initiated)

- Black swan market event
- Broker malfunction
- System compromise suspected
- Regulatory halt
- Liquidity crisis

---

## 2. Response Tiers

### Tier 1: ALERT (5% drawdown)
- Risk Officer notified
- Monitor intensified
- No automatic action

### Tier 2: HEDGE (10% drawdown or flash crash)
- Hedging positions opened automatically
- New trades halted
- Risk Officer must acknowledge

### Tier 3: KILL SWITCH (15% drawdown or system compromise)
- ALL positions closed immediately
- ALL trading halted
- ALL connections severed
- CTO notification required

---

## 3. Emergency Procedures

### 3.1 Kill Switch Activation

**When:** Capital at critical risk, system compromise, or regulatory requirement

**Authority:** Risk Officer (Tier 2-3), Operator (Tier 3 only if Risk Officer unreachable)

**Time to Execute:** < 60 seconds

```bash
# ╔═══════════════════════════════════════════════════════════════╗
# ║  KILL SWITCH - CLOSES ALL POSITIONS AND HALTS ALL TRADING    ║
# ╚═══════════════════════════════════════════════════════════════╝

# 1. ACTIVATE KILL SWITCH (this is irreversible)
curl -X POST "https://api.archon.ai/api/v1/admin/emergency/kill-switch" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "EMERGENCY: [describe situation]",
    "close_all_positions": true,
    "disconnect_all_profiles": true,
    "halt_all_trading": true,
    "confirm": "KILL_SWITCH_CONFIRMED"
  }'

# 2. VERIFY ACTIVATION
curl -s "https://api.archon.ai/api/v1/admin/emergency/status" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Expected output:
# {
#   "kill_switch_active": true,
#   "activated_at": "2024-01-15T10:30:00Z",
#   "activated_by": "risk_officer@archon.ai",
#   "positions_closed": 15,
#   "profiles_disconnected": 8
# }
```

**Immediately After:**
1. Call CTO (do not wait for response)
2. Document timestamp and reason
3. Do NOT attempt to restart trading

---

### 3.2 Manual Position Hedge

**When:** System hedge failed, need manual intervention

**Authority:** Risk Officer only

```bash
# 1. List all open positions
curl -s "https://api.archon.ai/api/v1/admin/positions/open" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.[] | {profile_id, ticket, symbol, volume, profit}'

# 2. For each position, open counter-position (hedge)
# This locks in current P&L
curl -X POST "https://api.archon.ai/api/v1/admin/positions/hedge" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_id": "{profile_id}",
    "ticket": {original_ticket},
    "reason": "Emergency hedge - market volatility"
  }'

# 3. Verify hedge is in place
curl -s "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/positions" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

---

### 3.3 Manual Position Close

**When:** Hedge not possible, must exit positions

**Authority:** Risk Officer only

```bash
# Close specific position
curl -X POST "https://api.archon.ai/api/v1/admin/positions/{ticket}/close" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Emergency close - [reason]",
    "slippage_tolerance": 0.001
  }'

# Close all positions for a profile
curl -X POST "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/close-all" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Emergency close all - [reason]"
  }'
```

---

### 3.4 MT5 Desktop Fallback

**When:** API-based closing fails, must use MT5 directly

**Authority:** Risk Officer only

1. **Access MT5 Terminal** (credentials in secure vault)
2. **Navigate to Trade tab**
3. **Right-click position → Close**
4. **Document each manual close**

**WARNING:** This bypasses all logging. Document everything manually.

---

## 4. Communication Protocol

### During Emergency

| Time | Action | Responsible |
|------|--------|-------------|
| T+0 | Execute emergency action | Risk Officer |
| T+1 min | Call CTO | Risk Officer |
| T+5 min | Email summary to leadership | Risk Officer |
| T+15 min | Client notification (if applicable) | CTO |
| T+1 hour | Detailed incident report | Risk Officer |

### Communication Templates

**CTO Call Script:**
> "This is [name], Risk Officer. I have activated [KILL SWITCH / HEDGE] at [time] due to [reason]. [X] positions affected, [Y] estimated impact. I need your acknowledgment and guidance on client communication."

**Email Template:**
```
Subject: URGENT: Trading Emergency - [Date Time]

Kill Switch Activated: [Yes/No]
Positions Closed: [count]
Estimated P&L Impact: [$amount]
Reason: [brief description]
Current Status: [Stable/Monitoring/Ongoing]

Next update in: [X] minutes

Risk Officer: [name]
Contact: [phone]
```

---

## 5. Recovery Procedure

### After Emergency Stabilized

```bash
# 1. Verify all positions closed (if kill switch)
curl -s "https://api.archon.ai/api/v1/admin/positions/open" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq 'length'
# Expected: 0

# 2. Review what happened
curl -s "https://api.archon.ai/api/v1/admin/emergency/history?hours=1" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# 3. Generate incident report
curl -X POST "https://api.archon.ai/api/v1/admin/emergency/report" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "incident_time": "2024-01-15T10:30:00Z",
    "trigger": "flash_crash",
    "actions_taken": ["kill_switch", "all_positions_closed"],
    "impact_summary": "15 positions closed, total realized loss $X"
  }'
```

### Restarting Trading

**Authority:** CTO only (after Risk Officer recommendation)

```bash
# 1. Verify system stability
curl -s "https://api.archon.ai/api/v1/admin/health/full" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# 2. Lift kill switch (CTO authorization code required)
curl -X POST "https://api.archon.ai/api/v1/admin/emergency/restore" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "authorization_code": "[CTO provided code]",
    "restore_trading": true,
    "restore_connections": false,
    "reason": "Market stabilized, risk review complete"
  }'

# 3. Gradually reconnect profiles
# Do NOT reconnect all at once
curl -X POST "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/connect" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 6. Post-Incident Requirements

### Within 24 Hours

- [ ] Complete incident report
- [ ] Root cause analysis
- [ ] Client impact assessment
- [ ] Regulatory notification (if required)

### Within 1 Week

- [ ] Lessons learned document
- [ ] Runbook updates
- [ ] System improvements identified
- [ ] Team debrief conducted

### Incident Report Contents

1. Timeline of events
2. Trigger identification
3. Actions taken (with timestamps)
4. Financial impact
5. Client impact
6. What worked well
7. What needs improvement
8. Action items

---

## 7. Contact Directory

| Role | Name | Phone | Backup |
|------|------|-------|--------|
| Risk Officer (Primary) | [TBD] | [TBD] | [TBD] |
| Risk Officer (Backup) | [TBD] | [TBD] | [TBD] |
| CTO | [TBD] | [TBD] | [TBD] |
| CEO | [TBD] | [TBD] | [TBD] |
| Legal Counsel | [TBD] | [TBD] | [TBD] |

**Escalation Order:** Risk Officer → CTO → CEO

**If Risk Officer Unreachable:** Operator may activate Tier 3 kill switch with documented justification.

---

## 8. Testing

### Monthly Drill
- Simulate emergency (paper trading only)
- Time response
- Verify communication chain
- Update runbook based on findings

### Quarterly Review
- Review all emergency events
- Assess trigger thresholds
- Update contact directory
- Test backup procedures

---

## 9. Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════════╗
║                    EMERGENCY QUICK REFERENCE                       ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                     ║
║  KILL SWITCH URL:                                                   ║
║  POST /api/v1/admin/emergency/kill-switch                          ║
║                                                                     ║
║  REQUIRED HEADER:                                                   ║
║  Authorization: Bearer $ADMIN_TOKEN                                 ║
║                                                                     ║
║  REQUIRED BODY:                                                     ║
║  {"confirm": "KILL_SWITCH_CONFIRMED", "reason": "..."}             ║
║                                                                     ║
║  RISK OFFICER PHONE: [TBD]                                         ║
║  CTO PHONE: [TBD]                                                  ║
║                                                                     ║
║  REMEMBER: Act first, investigate later. Capital > curiosity.      ║
║                                                                     ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
