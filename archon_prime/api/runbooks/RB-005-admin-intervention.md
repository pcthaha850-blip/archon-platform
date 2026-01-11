# RB-005: Admin Intervention Protocol

## Overview

| Field | Value |
|-------|-------|
| **Runbook ID** | RB-005 |
| **Title** | Admin Intervention Protocol |
| **Severity** | P2 High |
| **Primary Responder** | Risk Officer |
| **Escalation** | CTO |
| **Last Updated** | January 2026 |

---

## 1. Purpose

This runbook defines when and how administrators should manually intervene in trading operations. Admin intervention is a **last resort** when automated systems cannot handle a situation.

**Intervention Types:**
- Force disconnect a profile
- Manually approve/reject a signal
- Override risk parameters
- Suspend a user's trading
- Broadcast emergency messages

**Golden Rule:** Every intervention must be logged, justified, and reversible.

---

## 2. When to Intervene

### Authorized Intervention Scenarios

| Scenario | Authority Required | Justification |
|----------|-------------------|---------------|
| User requests emergency stop | Operator | User consent |
| Suspicious trading pattern | Risk Officer | Risk mitigation |
| System malfunction affecting user | Operator | Service restoration |
| Regulatory request | CTO | Legal compliance |
| Security incident | Risk Officer | Security response |

### DO NOT Intervene For

- Normal system operation
- User disagreement with signal decisions
- Performance optimization
- "Just checking" or curiosity
- Requests without proper authorization

---

## 3. Intervention Procedures

### 3.1 Force Disconnect Profile

**When:** MT5 connection causing issues, user locked out, emergency stop needed

**Authority:** Operator or Risk Officer

**Procedure:**
```bash
# 1. Document reason
REASON="User requested emergency stop - ticket #12345"

# 2. Execute disconnect
curl -X POST "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/disconnect" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"reason\": \"$REASON\", \"notify_user\": true}"

# 3. Verify disconnection
curl -s "https://api.archon.ai/api/v1/admin/profiles/{profile_id}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.is_connected'

# 4. Log action
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) - DISCONNECT - profile_id={profile_id} - $REASON" >> /var/log/archon/admin_actions.log
```

**Notification:**
- User receives email notification
- WebSocket message sent if connected
- Action logged in admin audit trail

---

### 3.2 Suspend User Trading

**When:** Account compromise suspected, regulatory hold, risk violation

**Authority:** Risk Officer only

**Procedure:**
```bash
# 1. Document reason (REQUIRED)
REASON="Suspected unauthorized access - security incident #789"

# 2. Suspend trading for all user profiles
curl -X POST "https://api.archon.ai/api/v1/admin/users/{user_id}/suspend-trading" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"reason\": \"$REASON\", \"duration_hours\": 24}"

# 3. Notify user
curl -X POST "https://api.archon.ai/api/v1/admin/users/{user_id}/notify" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subject": "Trading Suspended", "message": "Your trading has been temporarily suspended. Please contact support."}'

# 4. Create support ticket automatically
curl -X POST "https://api.archon.ai/api/v1/admin/tickets" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"{user_id}\", \"type\": \"trading_suspension\", \"reason\": \"$REASON\"}"
```

**Reversal:**
```bash
# Restore trading (Risk Officer only)
curl -X POST "https://api.archon.ai/api/v1/admin/users/{user_id}/restore-trading" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Security review completed, no issues found"}'
```

---

### 3.3 Manual Signal Override

**When:** Signal stuck in pending, system unable to evaluate, emergency trade needed

**Authority:** Risk Officer only

**CRITICAL:** Manual signal approval bypasses all Gate checks. Use only when absolutely necessary.

**Procedure:**
```bash
# 1. Get signal details first
curl -s "https://api.archon.ai/api/v1/admin/signals/{signal_id}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# 2. Document justification (MANDATORY)
JUSTIFICATION="System unable to evaluate due to DB outage. Manual review confirms: confidence 0.85, within risk limits, user has equity."

# 3. Manual approval
curl -X POST "https://api.archon.ai/api/v1/admin/signals/{signal_id}/override" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"decision\": \"approved\",
    \"override_reason\": \"$JUSTIFICATION\",
    \"risk_acknowledged\": true
  }"

# 4. Verify
curl -s "https://api.archon.ai/api/v1/admin/signals/{signal_id}" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '{decision, override_by, override_reason}'
```

**Audit Trail:**
- All manual overrides logged with admin ID
- Requires explicit risk acknowledgment
- Cannot be undone (only new signal can reverse)

---

### 3.4 Override Risk Parameters

**When:** Temporary adjustment needed for specific profile

**Authority:** Risk Officer only, CTO for global changes

**Procedure:**
```bash
# 1. Get current parameters
curl -s "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/risk-config" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# 2. Apply override (temporary)
curl -X PATCH "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/risk-config" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "max_positions": 10,
    "max_drawdown_percent": 20,
    "override_expiry_hours": 24,
    "override_reason": "Institutional client with higher risk tolerance - approved by CTO"
  }'

# 3. Verify
curl -s "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/risk-config" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

**Constraints:**
- Overrides automatically expire
- Cannot exceed system-wide maximums
- Logged and auditable

---

### 3.5 Emergency Broadcast

**When:** System-wide notification needed

**Authority:** Operator (informational), Risk Officer (action required)

**Procedure:**
```bash
# Informational broadcast
curl -X POST "https://api.archon.ai/api/v1/admin/broadcast" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "info",
    "title": "Scheduled Maintenance",
    "message": "System maintenance scheduled for 2024-01-20 02:00 UTC",
    "expires_at": "2024-01-20T02:00:00Z"
  }'

# Urgent broadcast (requires Risk Officer)
curl -X POST "https://api.archon.ai/api/v1/admin/broadcast" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "urgent",
    "title": "Trading Suspended",
    "message": "All trading suspended due to market conditions. Positions are safe.",
    "require_acknowledgment": true
  }'
```

---

## 4. Audit Requirements

### Every Intervention Must Include

1. **Timestamp** — When action was taken
2. **Admin ID** — Who performed the action
3. **Action Type** — What was done
4. **Target** — User/profile/signal affected
5. **Reason** — Why intervention was necessary
6. **Authorization** — Who approved (if escalated)

### Audit Log Access

```bash
# View recent admin actions
curl -s "https://api.archon.ai/api/v1/admin/audit-log?hours=24" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Export for compliance
curl -s "https://api.archon.ai/api/v1/admin/audit-log/export?start=2024-01-01&end=2024-01-31" \
  -H "Authorization: Bearer $ADMIN_TOKEN" > audit_jan_2024.json
```

---

## 5. Post-Intervention

### Immediate

1. Verify action took effect
2. Confirm user notified (if applicable)
3. Document in incident ticket

### Within 24 Hours

1. Review if intervention was appropriate
2. Identify if system improvement needed
3. Update runbooks if procedure changed

### Weekly Review

1. All interventions reviewed by Risk Officer
2. Patterns identified
3. Automation opportunities flagged

---

## 6. Escalation

| Situation | Escalate To | Method |
|-----------|-------------|--------|
| Unsure if intervention appropriate | Risk Officer | Slack/Phone |
| User disputing intervention | Team Lead | Ticket |
| Regulatory implications | CTO + Legal | Phone |
| Financial loss occurred | CTO | Phone immediately |

---

## 7. Prohibited Actions

Administrators MUST NOT:

- Override signals without documented reason
- Suspend users without Risk Officer approval
- Access user MT5 credentials
- Execute trades on behalf of users
- Modify historical records
- Share user data externally

Violations result in immediate access revocation and review.

---

## 8. Related Runbooks

- [RB-001: MT5 Outage](./RB-001-mt5-outage.md) — May require force disconnect
- [RB-006: Emergency Hedge](./RB-006-emergency-hedge.md) — Escalation path from intervention

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
