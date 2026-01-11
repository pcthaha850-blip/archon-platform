# ARCHON PRIME - Access & Authority Model

## Overview

This document defines **who can do what** within ARCHON PRIME.

**Principles:**
1. **Least Privilege** — Users get minimum access needed for their role
2. **Separation of Duties** — Critical actions require multiple roles
3. **Time-Bound Access** — Elevated permissions expire automatically
4. **Complete Auditability** — Every action is logged and exportable

---

## Role Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                        ROLE HIERARCHY                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         ┌──────────┐                            │
│                         │   OWNER  │                            │
│                         │  (CTO)   │                            │
│                         └────┬─────┘                            │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              │               │               │                  │
│        ┌─────▼─────┐  ┌──────▼─────┐  ┌─────▼─────┐            │
│        │   RISK    │  │   ADMIN    │  │  AUDITOR  │            │
│        │  OFFICER  │  │            │  │           │            │
│        └─────┬─────┘  └──────┬─────┘  └───────────┘            │
│              │               │                                   │
│              └───────┬───────┘                                  │
│                      │                                           │
│               ┌──────▼──────┐                                   │
│               │  OPERATOR   │                                   │
│               └──────┬──────┘                                   │
│                      │                                           │
│               ┌──────▼──────┐                                   │
│               │  OBSERVER   │                                   │
│               └─────────────┘                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Role Definitions

### 1. OWNER (System Owner / CTO)

**Purpose:** Ultimate authority over the platform

**Capabilities:**
- All permissions of all other roles
- Modify system-wide configuration
- Approve role assignments
- Lift kill switch
- Access all audit logs
- Delete/archive data

**Constraints:**
- Cannot bypass audit logging
- Actions require MFA
- Session timeout: 1 hour

**Assignment:** Manual, requires board approval

---

### 2. RISK_OFFICER

**Purpose:** Capital protection and risk governance

**Capabilities:**
- Activate/deactivate kill switch
- Suspend user trading
- Override signal decisions
- Modify risk parameters
- View all positions across platform
- Acknowledge risk alerts
- Access risk audit logs

**Constraints:**
- Cannot modify user accounts
- Cannot access MT5 credentials
- Cannot delete audit logs
- Overrides require documented reason

**Assignment:** CTO approval, annual review

---

### 3. ADMIN

**Purpose:** Platform administration and user support

**Capabilities:**
- Create/modify/suspend user accounts
- Reset user passwords
- View user profiles (not credentials)
- Force disconnect profiles
- Broadcast system messages
- View operational metrics
- Access support tickets

**Constraints:**
- Cannot activate kill switch
- Cannot override signals
- Cannot modify risk parameters
- Cannot view trading P&L details

**Assignment:** Team Lead approval, quarterly review

---

### 4. OPERATOR

**Purpose:** Day-to-day operational monitoring

**Capabilities:**
- View system health dashboards
- View connection status
- Restart services (with approval)
- Acknowledge operational alerts
- View aggregated metrics
- Execute runbook procedures

**Constraints:**
- Cannot modify user accounts
- Cannot access individual user data
- Cannot execute emergency actions alone
- Limited to operational endpoints

**Assignment:** Admin approval, monthly review

---

### 5. AUDITOR

**Purpose:** Compliance and audit oversight

**Capabilities:**
- Read-only access to all audit logs
- Export audit data
- View compliance reports
- Access decision provenance
- Generate regulatory reports

**Constraints:**
- Cannot modify anything
- Cannot execute any actions
- Read-only across entire platform
- Cannot access raw credentials

**Assignment:** CTO + Legal approval, annual review

---

### 6. OBSERVER

**Purpose:** Read-only monitoring (external stakeholders)

**Capabilities:**
- View public dashboards
- View aggregated statistics
- View system status

**Constraints:**
- No access to individual user data
- No access to trading details
- No access to audit logs
- No action capabilities

**Assignment:** Admin approval, time-limited (max 90 days)

---

## Permission Matrix

### User Management

| Permission | Owner | Risk Officer | Admin | Operator | Auditor | Observer |
|------------|-------|--------------|-------|----------|---------|----------|
| Create user | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| View user list | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| View user details | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Modify user | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Suspend user | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Delete user | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Reset password | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |

### Profile Management

| Permission | Owner | Risk Officer | Admin | Operator | Auditor | Observer |
|------------|-------|--------------|-------|----------|---------|----------|
| View all profiles | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| View profile details | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Force disconnect | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Modify profile config | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Access MT5 credentials | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Trading Operations

| Permission | Owner | Risk Officer | Admin | Operator | Auditor | Observer |
|------------|-------|--------------|-------|----------|---------|----------|
| View positions | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Close positions | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Hedge positions | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| View P&L | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |

### Signal Gate

| Permission | Owner | Risk Officer | Admin | Operator | Auditor | Observer |
|------------|-------|--------------|-------|----------|---------|----------|
| View signals | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Override signal | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Modify gate config | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| View decision provenance | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |

### Risk Controls

| Permission | Owner | Risk Officer | Admin | Operator | Auditor | Observer |
|------------|-------|--------------|-------|----------|---------|----------|
| Activate kill switch | ✅ | ✅ | ❌ | ❌* | ❌ | ❌ |
| Lift kill switch | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Modify risk params | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| View risk alerts | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Acknowledge alerts | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

*Operator can activate kill switch ONLY if Risk Officer unreachable (documented)

### System Operations

| Permission | Owner | Risk Officer | Admin | Operator | Auditor | Observer |
|------------|-------|--------------|-------|----------|---------|----------|
| View health | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View metrics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Restart services | ✅ | ❌ | ✅ | ✅** | ❌ | ❌ |
| Modify config | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Enable maintenance | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Broadcast messages | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |

**Operator restart requires documented reason

### Audit & Compliance

| Permission | Owner | Risk Officer | Admin | Operator | Auditor | Observer |
|------------|-------|--------------|-------|----------|---------|----------|
| View audit logs | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Export audit logs | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| View admin actions | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Generate reports | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Delete logs | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## Access Lifecycle

### Granting Access

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Request   │───►│   Approve   │───►│  Provision  │───►│   Active    │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     │                   │                  │                   │
     │                   │                  │                   │
   Requester         Approver           System             User notified
   submits           reviews &          creates            access
   request           approves           account            confirmed
```

### Access Request Requirements

| Role | Approver | Documentation | Review Cycle |
|------|----------|---------------|--------------|
| Owner | Board | Background check, NDA | Annual |
| Risk Officer | CTO | Background check, NDA | Annual |
| Admin | Team Lead + CTO | NDA | Quarterly |
| Operator | Admin | Onboarding complete | Monthly |
| Auditor | CTO + Legal | Engagement letter | Per-engagement |
| Observer | Admin | Business justification | Per-request (max 90 days) |

### Revoking Access

**Immediate Revocation Triggers:**
- Employment termination
- Role change
- Security incident
- Policy violation
- Request by user

**Process:**
```bash
# Revoke all access
curl -X POST "https://api.archon.ai/api/v1/admin/users/{user_id}/revoke-access" \
  -H "Authorization: Bearer $OWNER_TOKEN" \
  -d '{"reason": "Employment terminated", "effective": "immediate"}'
```

---

## Session Management

### Session Timeouts

| Role | Session Duration | Idle Timeout | MFA Required |
|------|------------------|--------------|--------------|
| Owner | 1 hour | 15 min | Always |
| Risk Officer | 4 hours | 30 min | Always |
| Admin | 8 hours | 1 hour | On sensitive actions |
| Operator | 8 hours | 1 hour | On login |
| Auditor | 4 hours | 30 min | Always |
| Observer | 4 hours | 30 min | On login |

### Concurrent Sessions

| Role | Max Sessions | Geographic Restriction |
|------|--------------|----------------------|
| Owner | 1 | Approved locations only |
| Risk Officer | 2 | Approved locations only |
| Admin | 2 | None |
| Operator | 3 | None |
| Auditor | 1 | None |
| Observer | 1 | None |

---

## Emergency Access

### Break-Glass Procedure

When normal access is unavailable and emergency action required:

1. **Document the emergency** — What, why, when
2. **Contact two approvers** — Any two of: CTO, Risk Officer, Legal
3. **Verbal approval** — Recorded and timestamped
4. **Execute with logging** — Every action logged
5. **Post-incident review** — Within 24 hours

### Emergency Access Credentials

- Stored in hardware security module (HSM)
- Requires two-person authorization
- Automatically expires after 4 hours
- Full audit trail generated

---

## API Endpoint Authorization

### Authentication Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────►│   Auth   │────►│   RBAC   │────►│ Endpoint │
│          │     │  (JWT)   │     │  Check   │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                │
                      ▼                ▼
               Verify token      Check role has
               Extract claims    required permission
```

### JWT Claims

```json
{
  "sub": "user_id",
  "email": "user@archon.ai",
  "roles": ["ADMIN", "OPERATOR"],
  "permissions": ["user:read", "user:write", "profile:read"],
  "iat": 1705312800,
  "exp": 1705316400,
  "mfa_verified": true
}
```

### Endpoint Protection

```python
# Example: Endpoint requiring RISK_OFFICER role
@router.post("/emergency/kill-switch")
@require_roles(["OWNER", "RISK_OFFICER"])
@require_mfa
@audit_log(action="KILL_SWITCH_ACTIVATED")
async def activate_kill_switch(
    request: KillSwitchRequest,
    current_user: User = Depends(get_current_user),
):
    ...
```

---

## Audit Requirements

### What Gets Logged

**Always Logged:**
- Authentication attempts (success/failure)
- Role changes
- Permission changes
- Sensitive data access
- Configuration changes
- Emergency actions

**Logged with Details:**
- Admin actions (full request/response)
- Risk actions (full context)
- Signal overrides (decision chain)
- Kill switch events (complete timeline)

### Audit Log Format

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "event_id": "evt_abc123",
  "actor": {
    "user_id": "usr_xyz",
    "email": "admin@archon.ai",
    "roles": ["ADMIN"],
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  },
  "action": {
    "type": "USER_SUSPENDED",
    "resource": "user",
    "resource_id": "usr_target",
    "details": {
      "reason": "Security review",
      "duration_hours": 24
    }
  },
  "result": "SUCCESS",
  "metadata": {
    "request_id": "req_123",
    "session_id": "sess_456"
  }
}
```

### Retention

| Log Type | Retention | Storage |
|----------|-----------|---------|
| Authentication | 2 years | Hot (90 days) + Cold |
| Admin Actions | 7 years | Hot (1 year) + Cold |
| Trading Decisions | 7 years | Hot (1 year) + Cold |
| Emergency Events | Permanent | Hot + Cold + Archive |

---

## Compliance Mapping

### SOC 2 Controls

| Control | Implementation |
|---------|---------------|
| CC6.1 - Logical Access | Role-based access control |
| CC6.2 - Access Provisioning | Approval workflow |
| CC6.3 - Access Removal | Automated on termination |
| CC6.6 - Access Review | Quarterly access reviews |

### GDPR Considerations

- Data access logged
- Purpose limitation enforced
- Right to access supported via Auditor exports
- Data minimization in role permissions

---

## Review Schedule

| Review Type | Frequency | Participants |
|-------------|-----------|--------------|
| Access Review | Quarterly | Team Lead + Admin |
| Permission Audit | Monthly | Security Team |
| Role Appropriateness | Annually | CTO + HR |
| Emergency Access Review | After each use | CTO + Legal |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
