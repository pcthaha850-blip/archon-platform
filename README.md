# ARCHON PRIME

**Institutional-grade signal execution platform for retail and semi-institutional traders.**

> *"Institutional risk controls. Retail accessibility. Your edge, protected."*

---

## What is ARCHON PRIME?

ARCHON PRIME is a commercial multi-tenant SaaS platform that provides:

- **Signal Gate** — Every signal passes through a 5-check consensus gate before execution
- **Position Sizing** — Kelly Criterion with CVaR-adjusted sizing protects capital
- **Panic Hedge** — Automatic hedging during flash crashes and volatility spikes
- **Kill Switch** — Emergency stop with sub-second activation
- **Full Provenance** — Every trade has a complete decision chain with SHA256 verification

## Architecture

```
+------------------------------------------------------------------+
|                    React Frontend                                 |
+-----------------------------+------------------------------------+
                              | HTTPS + WebSocket
                              v
+------------------------------------------------------------------+
|                     FastAPI Backend                               |
|  +----------+ +----------+ +----------+ +------------------+     |
|  | Auth API | | User API | |Trade API | | Admin API        |     |
|  +----------+ +----------+ +----------+ +------------------+     |
|                                                                   |
|  +--------------------------------------------------------------+|
|  |              MT5 Connection Pool                              ||
|  +--------------------------------------------------------------+|
+-----------------------------+------------------+-----------------+
                              |                  |
            +-----------------+------+    +------+---------+
            |    PostgreSQL         |    |  MT5 Terminals |
            +-----------------------+    +----------------+
```

## Deployment

### Quick Start (Development)

```bash
cd archon_prime/api/deploy
cp .env.example .env
docker-compose -f docker-compose.dev.yml up -d
```

### Production

```bash
cd archon_prime/api/deploy
cp .env.prod.example .env
docker stack deploy -c docker-compose.prod.yml archon
```

See [DEPLOYMENT.md](archon_prime/api/deploy/DEPLOYMENT.md) for complete deployment guide.

## Governance

### Roles

| Role | Purpose |
|------|---------|
| Owner | Ultimate authority, kill switch lift |
| Risk Officer | Capital protection, panic hedge |
| Admin | User management, system operations |
| Operator | Day-to-day monitoring |
| Auditor | Compliance oversight (read-only) |
| Observer | External stakeholders (read-only) |

See [ACCESS_MODEL.md](archon_prime/api/access/ACCESS_MODEL.md) for complete access model.

### Change Governance

Core modules are **frozen**. Changes require:

1. RFC submission
2. Review period (3-7 days)
3. CTO/Risk Officer approval
4. Extended testing
5. Staged rollout

See [CORE_FREEZE.md](archon_prime/docs/CORE_FREEZE.md) for change governance.

## Documentation

| Document | Purpose |
|----------|---------|
| [DEPLOYMENT.md](archon_prime/api/deploy/DEPLOYMENT.md) | Deployment guide |
| [ACCESS_MODEL.md](archon_prime/api/access/ACCESS_MODEL.md) | Access & authority |
| [COMPLIANCE_GUIDE.md](archon_prime/api/compliance/COMPLIANCE_GUIDE.md) | Audit & compliance |
| [COMMERCIAL_POSITIONING.md](archon_prime/docs/COMMERCIAL_POSITIONING.md) | Commercial framing |
| [CORE_FREEZE.md](archon_prime/docs/CORE_FREEZE.md) | Version governance |

### Runbooks

| Runbook | Scenario |
|---------|----------|
| [RB-001](archon_prime/api/runbooks/RB-001-mt5-outage.md) | MT5 Outage |
| [RB-002](archon_prime/api/runbooks/RB-002-signal-gate-overload.md) | Signal Gate Overload |
| [RB-003](archon_prime/api/runbooks/RB-003-websocket-degradation.md) | WebSocket Degradation |
| [RB-004](archon_prime/api/runbooks/RB-004-database-failover.md) | Database Failover |
| [RB-005](archon_prime/api/runbooks/RB-005-admin-intervention.md) | Admin Intervention |
| [RB-006](archon_prime/api/runbooks/RB-006-emergency-hedge.md) | Emergency Hedge |

## Testing

```bash
# Run all tests
pytest archon_prime/api/tests/ -v

# Run specific test suites
pytest archon_prime/api/tests/test_e2e_signal_flow.py -v
pytest archon_prime/api/tests/test_failure_modes.py -v
```

## Version

**ARCHON PRIME v1.0.0** — Production Ready

---

## License

Proprietary. All rights reserved.

## Disclaimer

Trading in financial instruments involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. ARCHON PRIME provides execution and risk management tools but does not provide investment advice.
