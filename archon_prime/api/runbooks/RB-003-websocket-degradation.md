# RB-003: WebSocket Degradation

## Overview

| Field | Value |
|-------|-------|
| **Runbook ID** | RB-003 |
| **Title** | WebSocket Degradation |
| **Severity** | P2 High |
| **Primary Responder** | Operator |
| **Escalation** | Team Lead → CTO |
| **Last Updated** | January 2026 |

---

## 1. What Happened

WebSocket connections are experiencing issues:
- Clients unable to connect
- Existing connections dropping
- Messages not being delivered
- High latency in real-time updates

**Impact:**
- Users not seeing live position updates
- Signal notifications delayed or missing
- Risk alerts not reaching clients
- Dashboard appears "frozen"

**Note:** WebSocket issues do NOT affect trading execution. Signals still process, positions still sync — clients just don't see updates in real-time.

---

## 2. How It's Detected

### Alerts
- `archon_websocket_connections < expected` — Fewer connections than normal
- `archon_websocket_errors_rate > 10/min` — Connection errors spiking
- `archon_websocket_broadcast_latency > 1s` — Slow message delivery
- `archon_websocket_queue_depth > 1000` — Message backlog

### Metrics
```
archon_websocket_connections_active
archon_websocket_connections_total
archon_websocket_messages_sent_total
archon_websocket_errors_total
archon_websocket_broadcast_duration_seconds
```

### Logs
```json
{
  "level": "ERROR",
  "message": "WebSocket send failed",
  "client_id": "xxx",
  "error": "Connection closed",
  "queue_depth": 150
}
```

### Manual Check
```bash
# Check WebSocket manager status
curl -s https://api.archon.ai/api/v1/admin/websocket/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Test WebSocket connectivity
wscat -c wss://api.archon.ai/api/v1/ws/test
```

---

## 3. Who Acts

| Time | Actor | Action |
|------|-------|--------|
| 0-10 min | On-Call Operator | Diagnose and mitigate |
| 10-30 min | On-Call Operator | Implement fix |
| 30+ min | Team Lead | Escalate if unresolved |

---

## 4. Recovery Procedure

### Step 1: Assess Scope (3 minutes)

```bash
# Current connection count vs expected
curl -s https://api.archon.ai/api/v1/admin/websocket/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '{
    active: .active_connections,
    peak_today: .peak_connections,
    errors_last_hour: .errors_last_hour
  }'

# Check connection distribution
curl -s https://api.archon.ai/api/v1/admin/websocket/connections \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq 'group_by(.server) | map({server: .[0].server, count: length})'
```

**Determine:**
- Is it all clients or specific subset?
- Is it one API instance or all?
- Did it start suddenly or gradually?

### Step 2: Check Infrastructure

**Load Balancer:**
```bash
# Check if LB is upgrading WebSocket connections
# AWS ALB: Check target group health
# Nginx: Check upgrade headers
curl -I https://api.archon.ai/api/v1/ws/health

# Should see:
# Connection: Upgrade
# Upgrade: websocket
```

**API Instances:**
```bash
# Check each instance's WS capacity
for i in 1 2 3; do
  echo "Instance $i:"
  curl -s "http://api-$i:8000/api/v1/admin/websocket/status" | jq '.active_connections'
done
```

**Memory Pressure:**
```bash
# High memory can cause WS issues
docker stats --no-stream archon_api
```

### Step 3: Common Fixes

**Fix A: Restart Stale Connections**
```bash
# Force cleanup of dead connections
curl -X POST "https://api.archon.ai/api/v1/admin/websocket/cleanup" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Fix B: Clear Message Queue**
```bash
# If message queue is backed up
curl -X POST "https://api.archon.ai/api/v1/admin/websocket/queue/flush" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Fix C: Restart WebSocket Manager**
```bash
# Rolling restart of API instances
docker service update --force archon_api

# Or specific instance
docker restart archon_api_1
```

**Fix D: Scale Up (if capacity issue)**
```bash
# Add more API instances
docker service scale archon_api=5
```

### Step 4: Load Balancer Fixes

**Nginx WebSocket Config:**
```nginx
# Ensure these settings in nginx.conf
location /api/v1/ws {
    proxy_pass http://api_backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;  # 24 hours
    proxy_send_timeout 86400;
}
```

**AWS ALB:**
- Verify target group protocol is HTTP (not HTTPS)
- Check idle timeout (increase to 4000 seconds)
- Verify sticky sessions enabled for WebSocket

### Step 5: Client-Side Mitigation

If server-side fixes taking time, notify clients:

```bash
# Broadcast reconnect instruction
curl -X POST "https://api.archon.ai/api/v1/admin/broadcast" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type": "system", "message": "Please refresh your dashboard"}'
```

---

## 5. Recovery Verification

### Immediate Checks

```bash
# 1. Connection count recovering
watch -n 10 'curl -s https://api.archon.ai/api/v1/admin/websocket/status \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq ".active_connections"'

# 2. Error rate dropping
curl -s https://api.archon.ai/api/v1/admin/websocket/stats?minutes=5 \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.errors_per_minute'

# 3. Messages being delivered
curl -s https://api.archon.ai/api/v1/admin/websocket/stats?minutes=5 \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.messages_per_minute'
```

### Success Criteria

- [ ] Active connections returning to baseline
- [ ] Error rate < 1/minute
- [ ] Message queue depth < 100
- [ ] Broadcast latency < 500ms
- [ ] No client complaints about frozen dashboard

### Post-Recovery

1. Review connection logs for patterns
2. Check if specific client versions affected
3. Update WebSocket timeout settings if needed
4. Document incident

---

## 6. Prevention

### WebSocket Configuration
```yaml
# Recommended settings
WEBSOCKET_PING_INTERVAL: 30  # seconds
WEBSOCKET_PING_TIMEOUT: 10   # seconds
WEBSOCKET_MAX_CONNECTIONS: 10000
WEBSOCKET_MESSAGE_QUEUE_SIZE: 1000
WEBSOCKET_BROADCAST_TIMEOUT: 5  # seconds
```

### Load Balancer Settings
```yaml
# ALB/Nginx recommendations
idle_timeout: 3600  # 1 hour minimum
sticky_sessions: true
health_check_path: /api/health
```

### Monitoring
- Alert on connection count drop > 20%
- Alert on error rate > 10/min
- Alert on message queue > 500

---

## 7. Client Recovery

If clients need to manually recover:

1. **Refresh browser** — Simplest fix
2. **Clear browser cache** — If stale JS
3. **Check network** — Corporate firewalls may block WS
4. **Try different browser** — Rule out client issues

---

## 8. Related Runbooks

- [RB-004: Database Failover](./RB-004-database-failover.md) — If WS issues caused by DB
- [RB-001: MT5 Outage](./RB-001-mt5-outage.md) — If no data to broadcast

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
