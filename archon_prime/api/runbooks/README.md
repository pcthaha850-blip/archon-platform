# ARCHON PRIME - Operator Runbooks

## Purpose

These runbooks define **how humans respond** when the system needs intervention.

Every runbook answers five questions:
1. **What happened?** — Symptom description
2. **How is it detected?** — Alerts, metrics, logs
3. **Who acts?** — Role and escalation path
4. **What actions are allowed?** — Step-by-step procedures
5. **How is recovery verified?** — Success criteria

---

## Runbook Index

| ID | Runbook | Severity | Primary Responder |
|----|---------|----------|-------------------|
| RB-001 | [MT5 Connection Outage](./RB-001-mt5-outage.md) | P1 Critical | Operator |
| RB-002 | [Signal Gate Overload](./RB-002-signal-gate-overload.md) | P1 Critical | Operator |
| RB-003 | [WebSocket Degradation](./RB-003-websocket-degradation.md) | P2 High | Operator |
| RB-004 | [Database Failover](./RB-004-database-failover.md) | P1 Critical | Operator + DBA |
| RB-005 | [Admin Intervention Protocol](./RB-005-admin-intervention.md) | P2 High | Risk Officer |
| RB-006 | [Emergency Hedge Escalation](./RB-006-emergency-hedge.md) | P0 Emergency | Risk Officer |

---

## Severity Levels

| Level | Response Time | Escalation | Description |
|-------|---------------|------------|-------------|
| **P0 Emergency** | Immediate | CEO/CTO | Capital at risk, system-wide failure |
| **P1 Critical** | < 15 min | On-call Lead | Service down, trading impacted |
| **P2 High** | < 1 hour | Team Lead | Degraded performance, partial outage |
| **P3 Medium** | < 4 hours | Team | Non-critical issue, workaround exists |
| **P4 Low** | Next business day | Team | Minor issue, no impact |

---

## Escalation Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                     ESCALATION PATH                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   P4/P3 ──► Operator ──► Team Lead                              │
│                                                                  │
│   P2 ────► Operator ──► Team Lead ──► Risk Officer              │
│                                                                  │
│   P1 ────► On-Call ──► Risk Officer ──► CTO                     │
│                                                                  │
│   P0 ────► On-Call ──► Risk Officer ──► CTO ──► CEO             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Contact Directory

| Role | Primary | Backup | Contact Method |
|------|---------|--------|----------------|
| Operator (On-Call) | [TBD] | [TBD] | PagerDuty / Phone |
| Team Lead | [TBD] | [TBD] | Slack / Phone |
| Risk Officer | [TBD] | [TBD] | Phone (always) |
| DBA | [TBD] | [TBD] | Slack / Phone |
| CTO | [TBD] | [TBD] | Phone |

---

## Common Commands

### Health Checks
```bash
# API health
curl -s https://api.archon.ai/api/health | jq

# Database connectivity
docker exec archon_api python -c "from archon_prime.api.db.session import engine; print('DB OK')"

# Redis connectivity
docker exec archon_redis redis-cli ping
```

### Service Status
```bash
# Docker Compose
docker-compose -f deploy/docker-compose.prod.yml ps

# Docker Swarm
docker service ls
docker service ps archon_api

# Logs (last 100 lines)
docker service logs --tail 100 archon_api
```

### Emergency Actions
```bash
# Enable maintenance mode
curl -X POST https://api.archon.ai/api/v1/admin/maintenance -H "Authorization: Bearer $ADMIN_TOKEN"

# Kill switch (halt all trading)
curl -X POST https://api.archon.ai/api/v1/admin/kill-switch -H "Authorization: Bearer $ADMIN_TOKEN"

# Force disconnect all MT5
curl -X POST https://api.archon.ai/api/v1/admin/disconnect-all -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Incident Response Template

When responding to an incident, document:

```markdown
## Incident: [Title]

**Severity:** P[0-4]
**Detected:** [timestamp]
**Resolved:** [timestamp]
**Duration:** [minutes]

### Timeline
- [HH:MM] Alert received
- [HH:MM] Investigation started
- [HH:MM] Root cause identified
- [HH:MM] Remediation applied
- [HH:MM] Recovery verified

### Root Cause
[Description]

### Impact
- Users affected: [count]
- Trades impacted: [count]
- Financial impact: [amount]

### Resolution
[What was done]

### Follow-up Actions
- [ ] Action item 1
- [ ] Action item 2
```

---

## Runbook Maintenance

- **Review Frequency:** Monthly
- **Owner:** Operations Team
- **Last Updated:** [Date]
- **Version:** 1.0.0

After each incident:
1. Review relevant runbook
2. Update if procedures changed
3. Add lessons learned
4. Test updated procedures

---

**Remember:** These runbooks exist so that when something breaks at 3 AM, you don't have to think — you follow the procedure.
