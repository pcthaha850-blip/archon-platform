# RB-002: Signal Gate Overload

## Overview

| Field | Value |
|-------|-------|
| **Runbook ID** | RB-002 |
| **Title** | Signal Gate Overload |
| **Severity** | P1 Critical |
| **Primary Responder** | Operator |
| **Escalation** | Risk Officer → CTO |
| **Last Updated** | January 2026 |

---

## 1. What Happened

The Signal Gate is receiving more signals than it can process, causing:
- Signal processing delays (queue backlog)
- Rate limit exhaustion across multiple profiles
- Increased rejection rate
- Potential missed trading opportunities

**Root Causes:**
- Strategy generating abnormal signal volume
- External integration flooding signals
- DDoS or abuse attempt
- Market volatility triggering multiple strategies

**Impact:** Legitimate signals may be delayed or rejected.

---

## 2. How It's Detected

### Alerts
- `archon_signal_queue_depth > 100` — Backlog building
- `archon_signal_processing_latency_p95 > 500ms` — Slow processing
- `archon_signal_rate_limit_hits > 50/min` — Mass rate limiting
- `archon_signal_rejection_rate > 30%` — High rejection rate

### Metrics
```
archon_signals_queued > 100
archon_signal_latency_seconds{quantile="0.95"} > 0.5
archon_signals_rejected_total rate > 10/min
archon_api_requests_total{endpoint="/signals/submit"} rate > 100/min
```

### Logs
```json
{
  "level": "WARNING",
  "message": "Signal rate limit exceeded",
  "profile_id": "xxx",
  "requests_in_window": 15,
  "limit": 10
}
```

### Manual Check
```bash
# Check signal stats
curl -s https://api.archon.ai/api/v1/admin/signals/stats \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Check rate limit status across profiles
curl -s https://api.archon.ai/api/v1/admin/signals/rate-limits \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

---

## 3. Who Acts

| Time | Actor | Action |
|------|-------|--------|
| 0-5 min | On-Call Operator | Identify source |
| 5-10 min | On-Call Operator | Apply throttling |
| 10+ min | Risk Officer | Evaluate impact on trading |
| If abuse | Risk Officer | Block source |

---

## 4. Recovery Procedure

### Step 1: Identify the Source (3 minutes)

```bash
# Top signal submitters in last hour
curl -s "https://api.archon.ai/api/v1/admin/signals/stats?hours=1&group_by=profile" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq 'sort_by(.count) | reverse | .[0:10]'

# Check for unusual patterns
curl -s "https://api.archon.ai/api/v1/admin/signals/stats?hours=1&group_by=source" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

**Determine:**
- Is it one profile or many?
- Is it one strategy or multiple?
- Is it legitimate volume or abuse?

### Step 2: Assess Legitimacy

**Legitimate Overload (market volatility):**
- Multiple strategies firing on news event
- High-volatility market conditions
- Expected behavior during market opens

**Suspicious Activity:**
- Single profile generating 10x normal volume
- Unknown source identifier
- Requests from unusual IP ranges
- Malformed or duplicate idempotency keys

### Step 3: Apply Immediate Throttling

**Option A: Increase Rate Limits (if legitimate)**
```bash
# Temporarily increase global rate limit
curl -X PATCH "https://api.archon.ai/api/v1/admin/config" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"signal_rate_limit_per_minute": 20}'
```

**Option B: Throttle Specific Profile (if abuse)**
```bash
# Reduce rate limit for specific profile
curl -X PATCH "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/config" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"signal_rate_limit_per_minute": 2}'
```

**Option C: Block Profile (if malicious)**
```bash
# Disable signal submission for profile
curl -X POST "https://api.archon.ai/api/v1/admin/profiles/{profile_id}/block-signals" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Step 4: Clear Backlog (if needed)

```bash
# Check queue depth
curl -s https://api.archon.ai/api/v1/admin/signals/queue \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.depth'

# If queue is stale, clear old entries (older than 5 minutes)
curl -X POST "https://api.archon.ai/api/v1/admin/signals/queue/prune?max_age_seconds=300" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Step 5: Scale If Needed

If legitimate volume exceeds capacity:

```bash
# Scale API replicas
docker service scale archon_api=5

# Or update deployment
kubectl scale deployment archon-api --replicas=5
```

### Step 6: Monitor Recovery

```bash
# Watch signal processing in real-time
watch -n 5 'curl -s https://api.archon.ai/api/v1/admin/signals/stats?minutes=5 \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq'
```

---

## 5. Recovery Verification

### Immediate Checks

```bash
# 1. Queue depth back to normal
curl -s https://api.archon.ai/api/v1/admin/signals/queue \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.depth'
# Expected: < 10

# 2. Processing latency normal
curl -s https://api.archon.ai/api/v1/admin/signals/stats?minutes=5 \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.avg_processing_ms'
# Expected: < 100ms

# 3. Rejection rate normal
curl -s https://api.archon.ai/api/v1/admin/signals/stats?minutes=5 \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.rejection_rate'
# Expected: < 10%
```

### Success Criteria

- [ ] Signal queue depth < 10
- [ ] P95 latency < 200ms
- [ ] Rejection rate < 10%
- [ ] No rate limit alerts firing
- [ ] CRITICAL signals still processing immediately

### Post-Recovery

1. If blocked a profile, investigate and communicate with user
2. If scaled up, determine if permanent increase needed
3. Review signal patterns for anomaly detection tuning
4. Document incident

---

## 6. Prevention

### Rate Limiting Configuration
```yaml
# Per-profile limits
SIGNAL_RATE_LIMIT_NORMAL: 10/min
SIGNAL_RATE_LIMIT_HIGH: 20/min
SIGNAL_RATE_LIMIT_CRITICAL: unlimited

# Global limits
SIGNAL_GLOBAL_RATE_LIMIT: 1000/min
SIGNAL_QUEUE_MAX_DEPTH: 500
```

### Monitoring Thresholds
```yaml
alerts:
  - name: SignalQueueHigh
    condition: archon_signals_queued > 50
    severity: warning

  - name: SignalQueueCritical
    condition: archon_signals_queued > 200
    severity: critical

  - name: SignalLatencyHigh
    condition: archon_signal_latency_p95 > 500ms
    severity: critical
```

### Capacity Planning
- Review signal volume trends weekly
- Scale proactively before known high-volume events
- Maintain 2x headroom for burst capacity

---

## 7. Related Runbooks

- [RB-001: MT5 Outage](./RB-001-mt5-outage.md) — If signals approved but can't execute
- [RB-005: Admin Intervention](./RB-005-admin-intervention.md) — For manual signal approval

---

## 8. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
