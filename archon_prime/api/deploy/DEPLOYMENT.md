# ARCHON PRIME - Deployment Guide

## Overview

This guide covers deployment of ARCHON PRIME API across three environments:

| Environment | Purpose | Infrastructure |
|-------------|---------|----------------|
| **Development** | Local development with hot reload | Docker Compose, local volumes |
| **Staging** | Pre-production validation | Docker Compose, managed DB/Redis |
| **Production** | Live institutional trading | Docker Swarm/K8s, managed services |

---

## Architecture

```
                                    ┌─────────────────┐
                                    │   Load Balancer │
                                    │   (SSL/TLS)     │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
              ┌─────▼─────┐           ┌──────▼─────┐           ┌──────▼─────┐
              │  API #1   │           │   API #2   │           │   API #3   │
              │  (8000)   │           │   (8000)   │           │   (8000)   │
              └─────┬─────┘           └──────┬─────┘           └──────┬─────┘
                    │                        │                        │
                    └────────────────────────┼────────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
              ┌─────▼─────┐           ┌──────▼─────┐           ┌──────▼─────┐
              │ PostgreSQL│           │   Redis    │           │  Workers   │
              │  (5432)   │           │   (6379)   │           │ (Background│
              └───────────┘           └────────────┘           └────────────┘
```

---

## Quick Start

### Development

```bash
# 1. Navigate to deploy directory
cd archon_prime/api/deploy

# 2. Start all services
docker-compose -f docker-compose.dev.yml up -d

# 3. Check status
docker-compose -f docker-compose.dev.yml ps

# 4. View logs
docker-compose -f docker-compose.dev.yml logs -f api

# 5. Run migrations
docker-compose -f docker-compose.dev.yml exec api alembic upgrade head

# 6. Access services
# API:     http://localhost:8000
# Docs:    http://localhost:8000/api/docs
# Adminer: http://localhost:8080
```

### Staging

```bash
# 1. Create environment file
cp .env.staging.example .env.staging
# Edit .env.staging with real credentials

# 2. Deploy
docker-compose -f docker-compose.staging.yml --env-file .env.staging up -d

# 3. Run migrations (one-time)
docker-compose -f docker-compose.staging.yml --env-file .env.staging run --rm migrations
```

### Production

```bash
# 1. Build and push image
docker build -t archon/archon-prime-api:1.0.0 ..
docker push your-registry/archon-prime-api:1.0.0

# 2. Create secrets (Docker Swarm)
echo "your-jwt-secret" | docker secret create jwt_secret -
echo "your-encryption-key" | docker secret create encryption_key -

# 3. Deploy stack
docker stack deploy -c docker-compose.prod.yml archon

# 4. Check status
docker service ls
docker service logs archon_api
```

---

## Environment Configuration

### Required Secrets

| Secret | Description | Generation |
|--------|-------------|------------|
| `JWT_SECRET_KEY` | JWT signing key | `openssl rand -hex 32` |
| `JWT_REFRESH_SECRET_KEY` | Refresh token key | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | AES-256 key for MT5 credentials | `python -c "import secrets; print(secrets.token_hex(16))"` |
| `POSTGRES_PASSWORD` | Database password | Strong random password |
| `REDIS_PASSWORD` | Redis password | Strong random password |

### Secret Management

**Development:** Store in `.env.dev` (gitignored)

**Staging:** Store in `.env.staging` or secrets manager

**Production:** Use external secrets manager:
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- GCP Secret Manager

---

## Database Management

### Migrations

```bash
# Generate new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback one step
docker-compose exec api alembic downgrade -1

# View current version
docker-compose exec api alembic current
```

### Backups

**Staging/Production:**
```bash
# Backup
pg_dump -h $DB_HOST -U $DB_USER -d archon_prime > backup_$(date +%Y%m%d).sql

# Restore
psql -h $DB_HOST -U $DB_USER -d archon_prime < backup_20240115.sql
```

---

## Health Checks

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Basic health check |
| `GET /api/health/ready` | Readiness (DB, Redis connected) |
| `GET /api/health/live` | Liveness (process running) |

### Docker Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## Scaling

### Horizontal Scaling

```bash
# Docker Compose
docker-compose up -d --scale api=3

# Docker Swarm
docker service scale archon_api=5

# Kubernetes
kubectl scale deployment archon-api --replicas=5
```

### Resource Limits

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| API | 2 cores | 4 GB | Per instance |
| Worker | 1 core | 2 GB | Per instance |
| PostgreSQL | 2 cores | 4 GB | Managed service recommended |
| Redis | 0.5 cores | 1 GB | Managed service recommended |

---

## Monitoring

### Logging

All services output JSON logs in production:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Signal approved",
  "signal_id": "abc123",
  "profile_id": "def456",
  "decision": "approved"
}
```

### Metrics

Prometheus metrics available at `/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `archon_requests_total` | Counter | Total HTTP requests |
| `archon_request_duration_seconds` | Histogram | Request latency |
| `archon_signals_processed_total` | Counter | Signals processed |
| `archon_active_connections` | Gauge | Active WebSocket connections |

### Alerts

Recommended alerting thresholds:

| Condition | Severity | Action |
|-----------|----------|--------|
| API 5xx rate > 1% | Warning | Investigate logs |
| API 5xx rate > 5% | Critical | Page on-call |
| Response time P95 > 500ms | Warning | Check database |
| Response time P95 > 2s | Critical | Scale or investigate |
| Database connections > 80% | Warning | Increase pool size |
| Memory usage > 90% | Critical | Scale or restart |

---

## Security

### Network Security

- **Development:** All ports exposed to localhost only
- **Staging:** API on port 8000, DB/Redis internal only
- **Production:**
  - API behind load balancer (443 only)
  - DB/Redis in private subnet
  - VPC/network isolation

### SSL/TLS

**Load Balancer Options:**
- AWS ALB with ACM certificates
- Traefik with Let's Encrypt
- Nginx with certbot

**Database/Redis:**
- Enable `ssl=require` in connection strings
- Use `rediss://` protocol for Redis TLS

### Secrets Rotation

1. Generate new secret
2. Update in secrets manager
3. Deploy new version
4. Verify functionality
5. Revoke old secret

---

## Troubleshooting

### Common Issues

**API won't start:**
```bash
# Check logs
docker-compose logs api

# Common causes:
# - Database not ready (check depends_on)
# - Missing environment variables
# - Port already in use
```

**Database connection failed:**
```bash
# Test connection
docker-compose exec api python -c "from archon_prime.api.db.session import engine; print('OK')"

# Check:
# - DATABASE_URL format
# - Network connectivity
# - Credentials
```

**Migrations failed:**
```bash
# Check current state
docker-compose exec api alembic current

# If stuck, stamp current
docker-compose exec api alembic stamp head

# Recreate from scratch (DEV ONLY)
docker-compose exec api alembic downgrade base
docker-compose exec api alembic upgrade head
```

**WebSocket not connecting:**
```bash
# Check:
# - CORS_ORIGINS includes WebSocket origin
# - Load balancer supports WebSocket upgrade
# - Nginx: proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade;
```

---

## Maintenance

### Planned Maintenance

1. Enable maintenance mode: `MAINTENANCE_MODE=true`
2. Wait for active requests to complete
3. Perform maintenance
4. Verify health checks pass
5. Disable maintenance mode

### Zero-Downtime Deployment

Docker Swarm/K8s handle this automatically with:

```yaml
update_config:
  parallelism: 1
  delay: 30s
  failure_action: rollback
  order: start-first
```

### Rollback

```bash
# Docker Swarm
docker service rollback archon_api

# Kubernetes
kubectl rollout undo deployment/archon-api

# Manual
docker-compose up -d --force-recreate --no-deps api
```

---

## Checklist

### Pre-Deployment

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Secrets in secrets manager
- [ ] Database migrations ready
- [ ] Health checks verified
- [ ] Monitoring configured
- [ ] Backup strategy in place

### Post-Deployment

- [ ] Health endpoint responding
- [ ] Logs flowing correctly
- [ ] Metrics being collected
- [ ] Sample API request succeeds
- [ ] WebSocket connection works
- [ ] Admin dashboard accessible

---

## Support

For operational issues:
1. Check this documentation
2. Review application logs
3. Check monitoring dashboards
4. Consult runbooks (when available)

---

**Version:** 1.0.0
**Last Updated:** January 2026
