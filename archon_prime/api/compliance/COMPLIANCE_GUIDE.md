# ARCHON PRIME - Compliance & Audit Guide

## Overview

This guide defines how ARCHON PRIME satisfies compliance requirements through evidence collection, provenance tracking, and audit trail maintenance.

**Core Question:** *"Show me why this trade happened."*

This guide ensures you can answer that question—without hesitation—for any trade, any time, years later.

---

## Compliance Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     COMPLIANCE LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Provenance  │    │   Evidence   │    │   Reports    │          │
│  │   Tracker    │    │   Packager   │    │  Generator   │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                    │                   │                   │
│         ▼                    ▼                   ▼                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      AUDIT DATABASE                           │  │
│  │  • Decision Chains    • Evidence Packages    • Reports        │  │
│  │  • Integrity Hashes   • Access Logs          • Change Logs    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │    REGULATORY EXPORTS     │
                    │  • SOC 2 Evidence         │
                    │  • GDPR Data Access       │
                    │  • Audit Packages         │
                    └───────────────────────────┘
```

---

## Decision Provenance

### What is Provenance?

Provenance tracks the **complete chain of decisions** from signal generation to trade execution. Every step is:
- Timestamped
- Attributed to a source
- Hash-verified for integrity
- Linked to parent decisions

### Decision Chain Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DECISION CHAIN EXAMPLE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Signal Generated                                                    │
│  └── Source: ai_agent                                               │
│      └── Signal Validated                                            │
│          └── Source: signal_gate                                    │
│              └── Risk Approved                                       │
│                  └── Source: risk_engine                            │
│                      └── Position Opened                             │
│                          └── Source: position_manager               │
│                                                                      │
│  Chain ID: chain_a1b2c3d4e5f6                                       │
│  Outcome: executed                                                   │
│  Duration: 127ms                                                     │
│  Nodes: 4                                                            │
│  Chain Hash: 9f86d081884c7d659a2...                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Decision Types

| Type | Description | Recorded Data |
|------|-------------|---------------|
| `signal.generated` | New signal created | Signal parameters, source, confidence |
| `signal.validated` | Signal passed validation | Validation checks, scores |
| `signal.rejected` | Signal failed validation | Rejection reason, failed checks |
| `gate.passed` | Signal passed all gates | Gate results, thresholds |
| `gate.blocked` | Signal blocked by gate | Blocking gate, reason |
| `gate.override` | Gate decision overridden | Override reason, authorizer |
| `risk.approved` | Risk evaluation passed | Risk metrics, limits |
| `risk.reduced` | Position size reduced | Original vs. adjusted size |
| `risk.rejected` | Position rejected by risk | Risk threshold exceeded |
| `position.opened` | Position created | Entry details, broker confirmation |
| `position.modified` | Position changed | Modification details |
| `position.closed` | Position closed | Exit details, P&L |
| `emergency.kill_switch` | Kill switch activated | Reason, authorizer |
| `emergency.panic_hedge` | Panic hedge triggered | Market conditions, hedges placed |
| `emergency.manual` | Manual intervention | Operator action, justification |

### Querying Provenance

```python
from archon_prime.api.compliance import (
    ProvenanceTracker,
    ProvenanceQuery,
    DecisionType,
    get_trade_provenance,
    verify_decision_integrity,
)

# Initialize tracker
tracker = ProvenanceTracker(storage_backend=db)

# Query: "Why did trade XYZ happen?"
chain = get_trade_provenance("trade_xyz123", tracker)
if chain:
    # View timeline
    timeline = chain.get_timeline()
    for step in timeline:
        print(f"{step['timestamp']}: {step['decision']} - {step['rationale']}")

    # Verify integrity
    verification = verify_decision_integrity(chain)
    print(f"Integrity verified: {verification['verified']}")

# Query: All blocked signals last 24 hours
query = ProvenanceQuery(
    start_time=datetime.now() - timedelta(days=1),
    decision_types={DecisionType.GATE_BLOCKED, DecisionType.RISK_REJECTED},
    outcome="rejected",
)
blocked_chains = tracker.query(query)
```

---

## Evidence Management

### Evidence Types

| Type | Description | Retention |
|------|-------------|-----------|
| Decision Chains | Complete provenance trails | 7 years |
| Signal History | All signals processed | 7 years |
| Trade History | All executed trades | 7 years |
| Risk Alerts | All risk events | 7 years |
| Admin Actions | All administrative actions | 7 years |
| Test Results | Automated test evidence | 3 years |
| System Health | Performance metrics | 2 years |

### Creating Evidence Packages

```python
from archon_prime.api.compliance import (
    EvidencePackager,
    EvidenceType,
    EvidenceFormat,
    export_evidence_package,
    create_audit_bundle,
)

# Initialize packager
packager = EvidencePackager(db_session=db)

# Create package for audit
package = packager.create_package(
    title="Q4 2025 Trading Audit",
    purpose="quarterly_audit",
    requested_by="auditor@example.com",
    period_start=datetime(2025, 10, 1),
    period_end=datetime(2025, 12, 31),
    classification="CONFIDENTIAL",
)

# Collect evidence
packager.collect_decision_chains(package, decision_chains)
packager.collect_signal_history(package, signals)
packager.collect_trade_history(package, trades)
packager.collect_risk_alerts(package, alerts)
packager.collect_admin_actions(package, admin_actions)

# Verify integrity
verification = package.verify_integrity()
print(f"Package verified: {verification['verified']}")

# Export as ZIP bundle
data = export_evidence_package(package, EvidenceFormat.ZIP)
Path("audit_package.zip").write_bytes(data)
```

### Evidence Package Contents

When exported as ZIP, a package contains:

```
audit_package.zip
├── MANIFEST.json           # Package metadata
├── README.md               # Human-readable summary
├── INTEGRITY.json          # Integrity verification results
└── evidence/
    ├── decision_chain/
    │   └── evi_abc123.json
    ├── signal_history/
    │   └── evi_def456.json
    ├── trade_history/
    │   └── evi_ghi789.json
    ├── risk_alerts/
    │   └── evi_jkl012.json
    └── admin_actions/
        └── evi_mno345.json
```

---

## Compliance Reports

### Report Types

| Report | Purpose | Audience |
|--------|---------|----------|
| SOC 2 Evidence | Control implementation proof | Auditors |
| GDPR Data Access | Data subject access requests | Legal, Data Subjects |
| Trading Activity | Trade execution summary | Operations, Compliance |
| Risk Assessment | Risk event analysis | Risk Officer, CTO |
| Access Review | User access audit | Security, HR |
| Executive Summary | High-level overview | Leadership |

### Generating Reports

```python
from archon_prime.api.compliance import (
    ComplianceReporter,
    ReportType,
    generate_compliance_report,
    generate_regulatory_summary,
)

# Initialize reporter
reporter = ComplianceReporter(db_session=db)

# Generate SOC 2 evidence report
soc2_report = generate_compliance_report(
    reporter=reporter,
    report_type=ReportType.SOC2_EVIDENCE,
    period_start=datetime(2025, 1, 1),
    period_end=datetime(2025, 12, 31),
    generated_by="compliance@company.com",
    data={
        "access_logs": access_logs,
        "change_logs": change_logs,
        "incident_logs": incident_logs,
    },
)

# Export as Markdown
markdown = soc2_report.to_markdown()
Path("soc2_report.md").write_text(markdown)

# Export as JSON
json_data = soc2_report.to_dict()
```

### SOC 2 Control Mapping

| Control | Implementation | Evidence |
|---------|----------------|----------|
| CC6.1 - Logical Access | RBAC with 6-tier roles | Access logs, role assignments |
| CC6.2 - Access Provisioning | Approval workflows | Request/approval records |
| CC6.3 - Access Removal | Immediate revocation | Revocation logs |
| CC6.6 - Access Review | Quarterly reviews | Review reports |
| CC7.2 - System Operations | Incident response | Incident logs, runbooks |
| CC7.3 - Change Management | Audit logging | Change logs |

### GDPR Compliance

| Requirement | Implementation |
|-------------|----------------|
| Right to Access | Data export via Evidence Packager |
| Right to Erasure | Data deletion with audit trail |
| Purpose Limitation | Role-based access controls |
| Data Minimization | Retention policies |
| Audit Trail | Complete provenance tracking |

---

## Answering "Why Did This Trade Happen?"

### Step-by-Step Query Process

1. **Identify the Trade**
   ```python
   trade_id = "pos_abc123"
   ```

2. **Get Complete Provenance**
   ```python
   chain = get_trade_provenance(trade_id, tracker)
   ```

3. **View Decision Timeline**
   ```python
   timeline = chain.get_timeline()
   # [
   #   {"timestamp": "2025-01-11T10:30:00Z", "decision": "signal.generated", ...},
   #   {"timestamp": "2025-01-11T10:30:01Z", "decision": "gate.passed", ...},
   #   {"timestamp": "2025-01-11T10:30:02Z", "decision": "risk.approved", ...},
   #   {"timestamp": "2025-01-11T10:30:03Z", "decision": "position.opened", ...},
   # ]
   ```

4. **Verify Integrity**
   ```python
   verification = verify_decision_integrity(chain)
   assert verification["verified"], "Integrity check failed!"
   ```

5. **Extract Key Details**
   ```python
   for node in chain.nodes:
       print(f"""
       Step: {node.decision_type.value}
       Source: {node.source.value}
       Time: {node.timestamp}
       Rationale: {node.rationale}
       Confidence: {node.confidence}
       Input: {node.input_data}
       Output: {node.output_data}
       """)
   ```

### Example Output

```
Trade Provenance: pos_abc123
Chain ID: chain_xyz789
Outcome: executed
Duration: 127ms

Decision Timeline:
─────────────────────────────────────────────────────────────────────
[2025-01-11T10:30:00.123Z] SIGNAL GENERATED
  Source: AI Agent (Intelligence)
  Rationale: Bullish XAUUSD setup detected - RSI divergence + support bounce
  Confidence: 0.87
  Input: {"symbol": "XAUUSD", "direction": "BUY", "entry": 2035.50}

[2025-01-11T10:30:01.234Z] GATE PASSED
  Source: Signal Gate
  Rationale: All gates passed (5/5)
  Confidence: 1.0
  Checks: confidence ✓, position_limit ✓, drawdown ✓, daily_limit ✓, time ✓

[2025-01-11T10:30:02.345Z] RISK APPROVED
  Source: Risk Engine
  Rationale: Position size within limits, drawdown < 5%
  Confidence: 1.0
  Risk Metrics: {"position_size": 0.1, "risk_pct": 0.5, "drawdown": 3.2}

[2025-01-11T10:30:03.456Z] POSITION OPENED
  Source: Position Manager
  Rationale: Order executed successfully
  Confidence: 1.0
  Execution: {"ticket": 12345678, "entry": 2035.48, "sl": 2030.00, "tp": 2050.00}
─────────────────────────────────────────────────────────────────────

Chain Integrity: VERIFIED ✓
Chain Hash: 9f86d081884c7d659a2feaa0c55ad015...
```

---

## Audit Procedures

### Regular Audits

| Audit Type | Frequency | Scope |
|------------|-----------|-------|
| Access Review | Quarterly | All user access |
| Trading Activity | Monthly | All trades |
| Risk Assessment | Monthly | Risk events |
| System Health | Weekly | Performance metrics |
| Full Compliance | Annually | All areas |

### Audit Checklist

**Pre-Audit:**
- [ ] Generate evidence package for audit period
- [ ] Verify all evidence integrity
- [ ] Prepare decision provenance exports
- [ ] Generate compliance reports
- [ ] Review access logs for anomalies

**During Audit:**
- [ ] Provide evidence package to auditor
- [ ] Answer provenance queries in real-time
- [ ] Demonstrate RBAC controls
- [ ] Show audit trail completeness
- [ ] Explain risk controls

**Post-Audit:**
- [ ] Document findings
- [ ] Create remediation plan (if needed)
- [ ] Update procedures
- [ ] Archive audit evidence

### Emergency Audit Response

If an auditor or regulator requests immediate evidence:

```bash
# 1. Generate emergency evidence package
curl -X POST "https://api.archon.ai/api/v1/compliance/evidence/package" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "purpose": "regulatory_inquiry",
    "period_start": "2025-01-01T00:00:00Z",
    "period_end": "2025-01-11T23:59:59Z",
    "evidence_types": ["decision_chain", "trade_history", "admin_actions"],
    "classification": "CONFIDENTIAL"
  }'

# 2. Export package
curl -X GET "https://api.archon.ai/api/v1/compliance/evidence/package/{package_id}/export" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -o evidence_package.zip
```

---

## Data Retention

### Retention Schedule

| Data Type | Retention Period | Storage Tier |
|-----------|------------------|--------------|
| Decision Chains | 7 years | Hot (1 year) → Cold |
| Trade History | 7 years | Hot (1 year) → Cold |
| Audit Logs | 7 years | Hot (1 year) → Cold |
| Admin Actions | 7 years | Hot (1 year) → Cold |
| Risk Alerts | 7 years | Hot (1 year) → Cold |
| System Metrics | 2 years | Hot (90 days) → Cold |
| Test Evidence | 3 years | Cold |
| Emergency Events | Permanent | Hot + Archive |

### Storage Tiers

- **Hot Storage:** PostgreSQL with full indexing, instant query
- **Cold Storage:** Object storage (S3/GCS), batch access
- **Archive:** Immutable storage, legal hold capable

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
