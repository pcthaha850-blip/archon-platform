# RB-001: MT5 Connection Outage

## Overview

| Field | Value |
|-------|-------|
| **Runbook ID** | RB-001 |
| **Title** | MT5 Connection Outage |
| **Severity** | P1 Critical |
| **Primary Responder** | Operator |
| **Escalation** | Risk Officer → CTO |
| **Last Updated** | January 2026 |

---

## 1. What Happened

MT5 connection pool has lost connectivity to one or more broker terminals. This means:
- Position data is stale
- New orders cannot be placed
- Account balances are not updating
- Signal execution is blocked

**Impact:** Trading operations halted for affected profiles.

---

## 2. How It's Detected

### Alerts
- `archon_mt5_connection_failed` — Connection pool reports disconnection
- `archon_mt5_reconnect_failed` — Auto-reconnection exhausted retries
- `archon_position_sync_stale` — Position data older than 60 seconds

### Metrics
```
archon_mt5_connections_active < expected_count
archon_mt5_reconnect_attempts > 3
archon_position_last_sync_seconds > 60
```

### Logs
```json
{
  "level": "ERROR",
  "message": "MT5 connection lost",
  "profile_id": "xxx",
  "error": "Connection refused",
  "retry_count": 5
}
```

### Manual Check
```bash
# Check connection pool status
curl -s https://api.archon.ai/api/v1/admin/mt5/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Expected: all profiles show is_connected: true
```

---

## 3. Who Acts

| Time | Actor | Action |
|------|-------|--------|
| 0-5 min | On-Call Operator | Initial assessment |
| 5-15 min | On-Call Operator | Execute recovery steps |
| 15+ min | Risk Officer | Escalation decision |
| If positions open | Risk Officer | Emergency hedge decision |

---

## 4. Recovery Procedure

### Step 1: Assess Scope (2 minutes)

```bash
# Check which profiles are affected
curl -s https://api.archon.ai/api/v1/admin/profiles?connected=false \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.[] | {id, name, is_connected}'
```

**Determine:**
- How many profiles affected?
- Any profiles have open positions?
- Is this one broker or multiple?

### Step 2: Check MT5 Terminal Status (3 minutes)

**If self-hosted MT5:**
```bash
# SSH to MT5 server
ssh mt5-server

# Check MT5 process
ps aux | grep terminal64

# Check network connectivity to broker
ping broker-server.com
telnet broker-server.com 443
```

**If broker-side issue:**
- Check broker status page
- Contact broker support
- Document broker incident ticket number

### Step 3: Attempt Manual Reconnection (5 minutes)

```bash
# Force reconnection for specific profile
curl -X POST "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/reconnect" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Force reconnection for all disconnected profiles
curl -X POST "https://api.archon.ai/api/v1/admin/mt5/reconnect-all" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Step 4: If Reconnection Fails

**Option A: Restart MT5 Terminal**
```bash
# On MT5 server
sudo systemctl restart mt5-terminal

# Wait 30 seconds, then verify
curl -s https://api.archon.ai/api/v1/admin/mt5/status \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Option B: Restart Connection Pool**
```bash
# Restart API service (will reinitialize pool)
docker service update --force archon_api
```

### Step 5: If Positions Are Open

**CRITICAL:** Open positions cannot be managed without MT5 connection.

1. **Notify Risk Officer immediately**
2. **Document all open positions:**
   ```bash
   # Get last known positions
   curl -s "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/positions/cached" \
     -H "Authorization: Bearer $ADMIN_TOKEN" | jq
   ```
3. **Consider manual intervention via MT5 desktop client**
4. **If broker accessible via web terminal, use that as backup**

### Step 6: Escalate if Unresolved (15 minutes)

If connection not restored within 15 minutes:

1. Page Risk Officer
2. Prepare incident summary:
   - Profiles affected
   - Open positions at risk
   - Reconnection attempts made
   - Suspected root cause

---

## 5. Recovery Verification

### Immediate Checks

```bash
# 1. Connection status
curl -s https://api.archon.ai/api/v1/admin/mt5/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.connections[] | select(.connected == true)'

# 2. Position sync working
curl -s "https://api.archon.ai/api/v1/profiles/{profile_id}/positions" \
  -H "Authorization: Bearer $USER_TOKEN" | jq

# 3. Account data fresh
curl -s "https://api.archon.ai/api/v1/profiles/{profile_id}/account" \
  -H "Authorization: Bearer $USER_TOKEN" | jq '.last_updated'
```

### Success Criteria

- [ ] All previously connected profiles show `is_connected: true`
- [ ] Position data is less than 10 seconds old
- [ ] Account balance/equity updating
- [ ] No ERROR logs in last 5 minutes
- [ ] WebSocket broadcasting position updates

### Post-Recovery

1. Monitor for 30 minutes for stability
2. Review logs for root cause
3. Document incident
4. Update runbook if needed

---

## 6. Prevention

### Monitoring
- Alert on single disconnection (warning)
- Alert on multiple disconnections (critical)
- Alert on reconnection loop (critical)

### Configuration
```yaml
# Recommended MT5 pool settings
MT5_POOL_RECONNECT_ATTEMPTS: 5
MT5_POOL_RECONNECT_DELAY: 10  # seconds
MT5_POOL_HEALTH_CHECK_INTERVAL: 15  # seconds
MT5_POOL_CONNECTION_TIMEOUT: 30  # seconds
```

### Regular Maintenance
- Weekly: Verify MT5 terminal auto-start on reboot
- Monthly: Test failover procedure
- Quarterly: Review broker SLA and uptime

---

## 7. Related Runbooks

- [RB-006: Emergency Hedge Escalation](./RB-006-emergency-hedge.md) — If positions at risk
- [RB-005: Admin Intervention Protocol](./RB-005-admin-intervention.md) — For manual position management

---

## 8. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
