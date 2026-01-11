# ARCHON PRIME — First Live Deployment Plan

## Overview

This document provides a step-by-step plan to deploy ARCHON PRIME to production for the first time. Follow sequentially. Do not skip steps.

**Estimated Time:** 4-6 hours (excluding paper trading validation)

---

## Pre-Deployment Checklist

Before starting deployment, confirm:

- [ ] All tests passing locally (`pytest archon_prime/api/tests/ -v`)
- [ ] Docker installed and running
- [ ] PostgreSQL server available (or using Docker)
- [ ] MT5 terminal installed and configured
- [ ] MT5 account credentials ready
- [ ] Domain/subdomain ready (or localhost for initial testing)
- [ ] SSL certificate available (for production)

---

## Phase 1: Infrastructure Setup (1-2 hours)

### 1.1 Prepare Server

**Minimum Requirements:**
- 2 CPU cores
- 4GB RAM
- 50GB SSD
- Ubuntu 22.04 LTS (recommended) or Windows Server

**Install Dependencies:**
```bash
# Ubuntu
sudo apt update
sudo apt install -y docker.io docker-compose git

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### 1.2 Clone Repository

```bash
git clone https://github.com/pcthaha850-blip/archon-platform.git
cd archon-platform
```

### 1.3 Configure Environment

```bash
cd archon_prime/api/deploy

# Copy and edit environment file
cp .env.prod.example .env

# Edit with your values
nano .env
```

**Required Environment Variables:**
```env
# Database
DATABASE_URL=postgresql://archon:YOUR_SECURE_PASSWORD@db:5432/archon_prime

# Security (GENERATE NEW VALUES - DO NOT USE DEFAULTS)
JWT_SECRET_KEY=<generate: openssl rand -hex 64>
ENCRYPTION_KEY=<generate: openssl rand -hex 32>

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
ENVIRONMENT=production

# MT5 (will configure per-profile later)
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

**Generate Secrets:**
```bash
# JWT Secret (64 bytes hex)
openssl rand -hex 64

# Encryption Key (32 bytes hex)
openssl rand -hex 32
```

### 1.4 Initialize Database

```bash
# Start only the database
docker-compose -f docker-compose.prod.yml up -d db

# Wait for database to be ready
sleep 10

# Run migrations
docker-compose -f docker-compose.prod.yml run --rm api \
  alembic upgrade head

# Verify
docker-compose -f docker-compose.prod.yml exec db \
  psql -U archon -d archon_prime -c "\dt"
```

---

## Phase 2: Deploy Application (30 minutes)

### 2.1 Start All Services

```bash
# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### 2.2 Verify Health

```bash
# Health check
curl http://localhost:8000/api/health

# Expected response:
# {"status": "healthy", "version": "1.0.0"}
```

### 2.3 Create Admin User

```bash
# Access API container
docker-compose -f docker-compose.prod.yml exec api python

# In Python shell:
>>> from archon_prime.api.auth.service import AuthService
>>> from archon_prime.api.db.session import get_db
>>>
>>> # Create admin user
>>> auth = AuthService(next(get_db()))
>>> user = auth.register(
...     email="admin@yourdomain.com",
...     password="SECURE_PASSWORD_HERE",
...     full_name="Admin User"
... )
>>> print(f"Admin created: {user.id}")
>>> exit()
```

### 2.4 Verify Login

```bash
# Test login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@yourdomain.com", "password": "SECURE_PASSWORD_HERE"}'

# Save the access_token from response
export TOKEN="<access_token_from_response>"

# Test authenticated endpoint
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
```

---

## Phase 3: Connect MT5 (30 minutes)

### 3.1 Prepare MT5 Terminal

On the machine running MT5:

1. **Launch MT5** and log into your trading account
2. **Enable Algo Trading:**
   - Tools → Options → Expert Advisors
   - Check "Allow algorithmic trading"
   - Check "Allow DLL imports"
3. **Note Connection Details:**
   - Server name
   - Account number
   - Account password (trading password, not investor)

### 3.2 Create MT5 Profile

```bash
# Create profile via API
curl -X POST http://localhost:8000/api/v1/profiles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Primary Trading Account",
    "mt5_server": "YourBroker-Server",
    "mt5_login": 12345678,
    "mt5_password": "your_trading_password",
    "is_demo": true
  }'

# Save the profile_id from response
export PROFILE_ID="<profile_id_from_response>"
```

### 3.3 Connect Profile

```bash
# Connect to MT5
curl -X POST http://localhost:8000/api/v1/profiles/$PROFILE_ID/connect \
  -H "Authorization: Bearer $TOKEN"

# Verify connection
curl http://localhost:8000/api/v1/profiles/$PROFILE_ID/account \
  -H "Authorization: Bearer $TOKEN"

# Expected: Account info with balance, equity, etc.
```

---

## Phase 4: Validate System (1-2 hours)

### 4.1 Test Signal Submission

```bash
# Submit a test signal (will be blocked if market closed)
curl -X POST http://localhost:8000/api/v1/signals/$PROFILE_ID/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "signal_id": "test_signal_001",
    "symbol": "EURUSD",
    "direction": "BUY",
    "confidence": 0.85,
    "source": "manual_test",
    "entry_price": 1.0850,
    "stop_loss": 1.0800,
    "take_profit": 1.0950
  }'
```

### 4.2 Test WebSocket Connection

```python
# test_websocket.py
import asyncio
import websockets
import json

async def test_ws():
    uri = f"ws://localhost:8000/api/v1/ws/{PROFILE_ID}?token={TOKEN}"
    async with websockets.connect(uri) as ws:
        print("Connected to WebSocket")
        async for message in ws:
            data = json.loads(message)
            print(f"Received: {data['type']}")

asyncio.run(test_ws())
```

### 4.3 Test Admin Dashboard

```bash
# Get dashboard stats
curl http://localhost:8000/api/v1/admin/dashboard \
  -H "Authorization: Bearer $TOKEN"

# List all profiles
curl http://localhost:8000/api/v1/admin/profiles \
  -H "Authorization: Bearer $TOKEN"

# List alerts
curl http://localhost:8000/api/v1/admin/alerts \
  -H "Authorization: Bearer $TOKEN"
```

### 4.4 Test Kill Switch

```bash
# Activate kill switch (TEST ONLY - will close all positions!)
curl -X POST http://localhost:8000/api/v1/admin/emergency/kill-switch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "confirm": "KILL_SWITCH_CONFIRMED",
    "reason": "Deployment validation test"
  }'
```

---

## Phase 5: Paper Trading Validation (7-30 days)

### 5.1 Paper Trading Requirements

Before going live, complete:

| Requirement | Minimum | Target |
|-------------|---------|--------|
| Days running | 7 | 30 |
| Signals processed | 50 | 200 |
| Successful executions | 90% | 95% |
| System uptime | 99% | 99.9% |
| Zero unhandled errors | Required | Required |

### 5.2 Monitoring During Paper Trading

**Daily:**
- Check dashboard for errors
- Review signal pass/block ratio
- Confirm positions reconcile correctly
- Verify WebSocket stability

**Weekly:**
- Export audit logs
- Review trade provenance
- Check system resource usage
- Validate backup integrity

### 5.3 Graduation Criteria

Before live trading:

- [ ] 7+ days continuous operation
- [ ] 50+ signals processed successfully
- [ ] Zero critical errors
- [ ] All runbooks tested
- [ ] Kill switch verified working
- [ ] Backup/restore tested
- [ ] SSL/TLS configured
- [ ] Rate limiting verified
- [ ] Access controls verified

---

## Phase 6: Go Live (When Ready)

### 6.1 Pre-Live Checklist

- [ ] Paper trading validation complete
- [ ] Production MT5 account ready
- [ ] SSL certificate installed
- [ ] Firewall configured
- [ ] Monitoring alerts configured
- [ ] On-call schedule established
- [ ] Emergency contacts documented
- [ ] Rollback plan ready

### 6.2 Switch to Live Account

```bash
# Create live profile
curl -X POST http://localhost:8000/api/v1/profiles \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Live Trading Account",
    "mt5_server": "YourBroker-Live",
    "mt5_login": 87654321,
    "mt5_password": "live_password",
    "is_demo": false
  }'
```

### 6.3 Gradual Ramp-Up

**Week 1:** 10% of normal position size
**Week 2:** 25% of normal position size
**Week 3:** 50% of normal position size
**Week 4+:** Full position size (if no issues)

### 6.4 First Live Trade Verification

After first live signal:

1. Verify trade in MT5 terminal
2. Check position in dashboard
3. Verify WebSocket update received
4. Check audit log entry
5. Confirm risk metrics updated

---

## Rollback Procedure

If critical issues occur:

```bash
# 1. Activate kill switch
curl -X POST http://localhost:8000/api/v1/admin/emergency/kill-switch \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"confirm": "KILL_SWITCH_CONFIRMED", "reason": "Critical issue"}'

# 2. Stop API (prevents new signals)
docker-compose -f docker-compose.prod.yml stop api

# 3. Disconnect all profiles manually in MT5

# 4. Investigate logs
docker-compose -f docker-compose.prod.yml logs api > incident.log

# 5. When ready to resume:
docker-compose -f docker-compose.prod.yml start api
```

---

## Post-Deployment Operations

### Daily Routine

```
08:00 - Check dashboard, review overnight alerts
08:15 - Verify all workers running
08:30 - Review pending signals (if any)
17:00 - End of day review
17:15 - Export daily audit log
```

### Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| Operator | [Your contact] | First response |
| Risk Officer | [Contact] | P0/P1 incidents |
| CTO | [Contact] | Critical decisions |

---

## Troubleshooting

### API Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Common issues:
# - Database not ready: Wait and retry
# - Port in use: Change API_PORT
# - Missing env vars: Check .env file
```

### MT5 Connection Failed

```bash
# Verify MT5 is running and logged in
# Check server name matches exactly
# Verify credentials are trading (not investor) password
# Ensure Algo Trading is enabled in MT5
```

### WebSocket Disconnects

```bash
# Check nginx/proxy timeout settings
# Verify firewall allows WebSocket upgrades
# Check API logs for connection errors
```

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial deployment guide |
