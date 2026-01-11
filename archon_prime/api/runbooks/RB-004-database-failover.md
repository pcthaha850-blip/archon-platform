# RB-004: Database Failover

## Overview

| Field | Value |
|-------|-------|
| **Runbook ID** | RB-004 |
| **Title** | Database Failover |
| **Severity** | P1 Critical |
| **Primary Responder** | Operator + DBA |
| **Escalation** | CTO |
| **Last Updated** | January 2026 |

---

## 1. What Happened

PostgreSQL database is unavailable or degraded:
- Connection failures
- Query timeouts
- Replication lag (if using read replicas)
- Disk space exhaustion
- Primary failure requiring failover

**Impact:**
- All API operations fail
- User authentication fails
- Signal processing halted
- Position data unavailable
- Complete service outage

**CRITICAL:** Database failure is a full platform outage.

---

## 2. How It's Detected

### Alerts
- `archon_db_connection_failed` — Cannot connect to database
- `archon_db_query_timeout` — Queries exceeding timeout
- `archon_db_replication_lag > 30s` — Replica behind
- `archon_db_disk_usage > 85%` — Running out of space
- `archon_api_5xx_rate > 10%` — API errors spiking

### Metrics
```
archon_db_connections_active
archon_db_connections_waiting
archon_db_query_duration_seconds
archon_db_replication_lag_seconds
archon_db_disk_usage_percent
```

### Logs
```json
{
  "level": "CRITICAL",
  "message": "Database connection failed",
  "error": "Connection refused",
  "host": "db.archon.ai",
  "retry_count": 3
}
```

### Manual Check
```bash
# Test database connectivity
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c "SELECT 1"

# Check connection count
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
```

---

## 3. Who Acts

| Time | Actor | Action |
|------|-------|--------|
| Immediate | On-Call Operator | Enable maintenance mode |
| 0-5 min | On-Call Operator | Assess scope, page DBA |
| 5-15 min | DBA | Execute recovery |
| 15+ min | CTO | Business communication |

---

## 4. Recovery Procedure

### Step 0: Enable Maintenance Mode (Immediate)

```bash
# Prevent further damage, inform users
curl -X POST "https://api.archon.ai/api/v1/admin/maintenance/enable" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"message": "Database maintenance in progress"}'
```

### Step 1: Assess the Failure (3 minutes)

```bash
# Check if database host is reachable
ping $DB_HOST
nc -zv $DB_HOST 5432

# Check database process (if self-managed)
ssh db-server "sudo systemctl status postgresql"

# Check managed service status (AWS RDS)
aws rds describe-db-instances --db-instance-identifier archon-prod \
  --query 'DBInstances[0].DBInstanceStatus'
```

**Failure Types:**

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Host unreachable | Network/VM issue | Check infrastructure |
| Connection refused | PostgreSQL down | Restart service |
| Too many connections | Pool exhaustion | Restart API, increase pool |
| Query timeout | Lock contention | Kill blocking queries |
| Disk full | Storage exhausted | Expand storage |

### Step 2: Scenario-Specific Recovery

#### Scenario A: PostgreSQL Service Down

```bash
# Self-managed
ssh db-server "sudo systemctl restart postgresql"
ssh db-server "sudo systemctl status postgresql"

# Verify
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c "SELECT 1"
```

#### Scenario B: Connection Pool Exhausted

```bash
# Check connection count
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state"

# Kill idle connections
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE state = 'idle' AND query_start < now() - interval '10 minutes'"

# Restart API to reset connection pool
docker service update --force archon_api
```

#### Scenario C: Lock Contention / Blocking Queries

```bash
# Find blocking queries
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
AND state != 'idle'
ORDER BY duration DESC;"

# Kill blocking query (with DBA approval)
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c \
  "SELECT pg_terminate_backend(<pid>)"
```

#### Scenario D: Disk Space Exhausted

```bash
# Check disk usage
ssh db-server "df -h /var/lib/postgresql"

# Emergency: Clear old WAL files (DANGEROUS - DBA only)
ssh db-server "sudo -u postgres pg_archivecleanup /var/lib/postgresql/14/main/pg_wal <oldest_needed_wal>"

# Better: Expand storage
# AWS RDS: Modify storage in console
# Self-managed: Expand volume, resize filesystem
```

#### Scenario E: Primary Failure (Failover Required)

**AWS RDS Multi-AZ:**
```bash
# Failover happens automatically
# Monitor status
aws rds describe-db-instances --db-instance-identifier archon-prod \
  --query 'DBInstances[0].{Status:DBInstanceStatus,AZ:AvailabilityZone}'

# If stuck, force failover
aws rds reboot-db-instance --db-instance-identifier archon-prod --force-failover
```

**Self-Managed with Patroni/Stolon:**
```bash
# Check cluster status
patronictl -c /etc/patroni.yml list

# Manual failover if needed
patronictl -c /etc/patroni.yml failover --master <old-master> --candidate <new-master>
```

### Step 3: Verify Database Recovery

```bash
# Test connectivity
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c "SELECT 1"

# Check table accessibility
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c \
  "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM mt5_profiles; SELECT COUNT(*) FROM signals;"

# Check for corruption (if crash occurred)
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d archon_prime -c \
  "SELECT schemaname, tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
```

### Step 4: Restore API Service

```bash
# Restart API to reconnect
docker service update --force archon_api

# Disable maintenance mode
curl -X POST "https://api.archon.ai/api/v1/admin/maintenance/disable" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Verify API health
curl -s https://api.archon.ai/api/health | jq
```

---

## 5. Recovery Verification

### Immediate Checks

```bash
# 1. API responding
curl -s https://api.archon.ai/api/health | jq

# 2. Database queries working
curl -s https://api.archon.ai/api/v1/users/me \
  -H "Authorization: Bearer $USER_TOKEN" | jq

# 3. No error logs
docker service logs --tail 50 archon_api 2>&1 | grep -i error

# 4. Connection pool healthy
curl -s https://api.archon.ai/api/v1/admin/health/detailed \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.database'
```

### Success Criteria

- [ ] API health endpoint returns 200
- [ ] User authentication working
- [ ] Signal submission working
- [ ] Position queries returning data
- [ ] No database errors in logs
- [ ] Connection pool not exhausted

### Post-Recovery

1. Monitor for 1 hour for stability
2. Check for data integrity issues
3. Review what caused the failure
4. Update backups if needed
5. Document incident

---

## 6. Data Recovery (If Needed)

### Point-in-Time Recovery

```bash
# AWS RDS
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier archon-prod \
  --target-db-instance-identifier archon-prod-recovered \
  --restore-time 2024-01-15T10:00:00Z

# Self-managed (requires WAL archiving)
pg_basebackup + pg_restore with recovery_target_time
```

### Backup Restoration

```bash
# List available backups
aws rds describe-db-snapshots --db-instance-identifier archon-prod

# Restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier archon-prod-restored \
  --db-snapshot-identifier archon-prod-snapshot-20240115
```

---

## 7. Prevention

### High Availability Setup
```yaml
# Recommended production setup
- AWS RDS Multi-AZ (automatic failover)
- Or PostgreSQL with Patroni/Stolon
- Read replicas for query offloading
- Connection pooling (PgBouncer)
```

### Monitoring
```yaml
alerts:
  - name: DBConnectionsFailing
    condition: archon_db_errors > 0
    severity: critical

  - name: DBDiskHigh
    condition: archon_db_disk_usage > 80%
    severity: warning

  - name: DBDiskCritical
    condition: archon_db_disk_usage > 90%
    severity: critical

  - name: DBReplicationLag
    condition: archon_db_replication_lag > 30s
    severity: warning
```

### Backups
- Automated daily snapshots (7 day retention minimum)
- Point-in-time recovery enabled
- Weekly backup restoration tests
- Offsite backup copies

---

## 8. Related Runbooks

- [RB-001: MT5 Outage](./RB-001-mt5-outage.md) — May occur alongside DB issues
- [RB-006: Emergency Hedge](./RB-006-emergency-hedge.md) — If positions at risk during outage

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
