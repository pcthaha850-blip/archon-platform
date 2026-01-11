# ARCHON PRIME - Access Request Procedures

## Overview

This document defines the procedures for requesting, approving, and revoking access to ARCHON PRIME.

**Principle:** No one should have access they don't need, and all access must be justified, approved, and reviewed.

---

## Access Request Process

### Standard Access Request Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Requester  │───►│  Approver   │───►│   System    │───►│  Requester  │
│  Submits    │    │  Reviews    │    │  Provisions │    │  Notified   │
│  Request    │    │  & Approves │    │  Access     │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
      │                  │                  │                  │
  Form filled       Decision in        Automated          Email sent
  Justification     48 hours           provisioning       Access active
  provided          (24h for urgent)
```

### Request Form Requirements

All access requests must include:

1. **Requester Information**
   - Full name
   - Email address
   - Department/Team
   - Manager name

2. **Access Details**
   - Role requested
   - Specific permissions needed (if subset)
   - Resources to access
   - Duration (permanent or time-limited)

3. **Business Justification**
   - Why access is needed
   - What tasks require this access
   - Alternative options considered

4. **Acknowledgments**
   - Acceptable use policy
   - Security requirements
   - Confidentiality agreement

---

## Role-Specific Procedures

### OBSERVER Access

**Use Case:** External stakeholders, partners, auditors (limited scope)

**Request Process:**
1. Requester submits form to Admin
2. Admin reviews within 24 hours
3. Admin provisions access
4. Maximum duration: 90 days
5. Auto-expires unless renewed

**Approver:** Admin or Owner

**Documentation Required:**
- Business justification
- Sponsor (internal contact)
- Expected end date

---

### OPERATOR Access

**Use Case:** Operations team members, on-call staff

**Request Process:**
1. Requester submits form to Admin
2. Admin verifies team membership
3. Admin reviews within 48 hours
4. System provisions access
5. Review cycle: Monthly

**Approver:** Admin

**Documentation Required:**
- Role in operations team
- Completion of operator training
- Manager approval

**Training Required:**
- [ ] ARCHON PRIME orientation
- [ ] Runbook familiarization
- [ ] Incident response basics

---

### ADMIN Access

**Use Case:** Platform administrators, support team leads

**Request Process:**
1. Requester submits form to Team Lead
2. Team Lead endorses request
3. CTO or Risk Officer reviews
4. System provisions access
5. Review cycle: Quarterly

**Approver:** Team Lead + (CTO or Risk Officer)

**Documentation Required:**
- Role responsibilities
- Previous admin experience
- Manager endorsement
- Background check (if new hire)

**Training Required:**
- [ ] ARCHON PRIME admin training
- [ ] Security awareness
- [ ] Data handling procedures
- [ ] Incident escalation

**Additional Requirements:**
- NDA signed
- Security training completed
- MFA enrolled

---

### AUDITOR Access

**Use Case:** Internal audit, external auditors, compliance reviews

**Request Process:**
1. Audit engagement letter submitted
2. Legal reviews scope
3. CTO approves access scope
4. System provisions read-only access
5. Duration: Per engagement (max 90 days)

**Approver:** CTO + Legal

**Documentation Required:**
- Engagement letter
- Audit scope definition
- Data access requirements
- Confidentiality agreement

**Constraints:**
- Read-only access only
- Export requires separate approval
- No access to credentials or PII
- Session recording may be enabled

---

### RISK_OFFICER Access

**Use Case:** Risk management, capital protection oversight

**Request Process:**
1. HR initiates for role appointment
2. Background check completed
3. CTO reviews and approves
4. System provisions access
5. Review cycle: Annual

**Approver:** CTO (Owner)

**Documentation Required:**
- Role appointment letter
- Background check clearance
- Risk management qualifications
- Previous experience verification

**Training Required:**
- [ ] ARCHON PRIME risk systems
- [ ] Kill switch procedures
- [ ] Emergency response protocols
- [ ] Regulatory requirements

**Additional Requirements:**
- Enhanced background check
- NDA signed
- Emergency contact provided
- MFA with hardware key

---

### OWNER Access

**Use Case:** System owners, C-level executives

**Request Process:**
1. Board resolution or CEO directive
2. Legal review
3. Security team provisions
4. Access audit scheduled

**Approver:** Board / CEO (out of system)

**Documentation Required:**
- Board resolution or equivalent
- Role responsibilities
- Emergency succession plan

**Constraints:**
- Maximum 2-3 Owner accounts
- Quarterly access review
- All actions audited
- Hardware MFA required

---

## Approval Workflows

### Standard Approval (48 hours)

```yaml
Role: OBSERVER, OPERATOR
Process:
  1. Request submitted via form
  2. Auto-routed to approver
  3. Approver has 48 hours to decide
  4. If no response, escalates to backup
  5. Decision logged
  6. Requester notified
```

### Elevated Approval (72 hours)

```yaml
Role: ADMIN, AUDITOR
Process:
  1. Request submitted via form
  2. First approver reviews (Team Lead)
  3. Second approver reviews (CTO/Risk Officer)
  4. Both must approve
  5. System provisions after both approvals
  6. Audit record created
```

### Executive Approval (Manual)

```yaml
Role: RISK_OFFICER, OWNER
Process:
  1. HR/Legal initiates process
  2. Background check (if applicable)
  3. CTO/CEO approval (documented)
  4. Security team provisions
  5. Training completed before activation
  6. Compliance notified
```

---

## Access Modification

### Adding Permissions

If an existing user needs additional permissions:

1. User submits modification request
2. Current role and requested additions documented
3. Approver reviews justification
4. If approved, permissions added
5. Audit log updated

**Note:** Consider if a role upgrade is more appropriate than individual permission additions.

### Removing Permissions

Permissions may be removed:
- At user request
- By manager request
- Following security review
- After role change

### Role Upgrade

When moving to a higher-privilege role:

1. New role request submitted (full process)
2. Previous role permissions retained during transition
3. Training completed for new role
4. Previous role revoked after confirmation
5. Audit trail maintained

### Role Downgrade

When moving to a lower-privilege role:

1. Manager or user initiates request
2. Current high-privilege access revoked immediately
3. New role provisioned
4. Transition period NOT required
5. Audit trail maintained

---

## Access Revocation

### Scheduled Revocation

For time-limited access (Observer, Auditor engagements):

```
T-7 days:  Reminder sent to user and sponsor
T-1 day:   Final warning sent
T-0:       Access automatically revoked
T+1 day:   Confirmation sent
```

### Immediate Revocation Triggers

Access is revoked immediately for:

- Employment termination (same day)
- Security incident involving user
- Policy violation confirmed
- User request
- Manager/Legal/Security request

**Process:**
```bash
# Emergency revocation (any authorized admin)
curl -X POST "https://api.archon.ai/api/v1/admin/users/{user_id}/revoke" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"reason": "Security incident", "immediate": true}'
```

### Revocation Checklist

When revoking access:

- [ ] Active sessions terminated
- [ ] API tokens invalidated
- [ ] MFA devices removed
- [ ] Shared credentials rotated (if applicable)
- [ ] User notified (unless security incident)
- [ ] Manager notified
- [ ] Audit log entry created
- [ ] Access review scheduled (for security incidents)

---

## Access Reviews

### Periodic Review Schedule

| Role | Review Frequency | Reviewer |
|------|-----------------|----------|
| Observer | On expiry | Admin |
| Operator | Monthly | Admin |
| Admin | Quarterly | CTO/Risk Officer |
| Auditor | Per engagement | CTO/Legal |
| Risk Officer | Annually | CTO |
| Owner | Annually | Board/CEO |

### Review Process

1. **Generate Report**
   ```bash
   curl -s "https://api.archon.ai/api/v1/admin/access-review/generate" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"role": "ADMIN", "period_days": 90}'
   ```

2. **Review Each User**
   - Is access still needed?
   - Is role appropriate?
   - Has user been active?
   - Any security concerns?

3. **Take Action**
   - Confirm: Access remains
   - Modify: Adjust permissions
   - Revoke: Remove access

4. **Document**
   - Review decision logged
   - Justification recorded
   - Next review scheduled

### Review Report Template

```markdown
## Access Review Report

**Review Date:** [Date]
**Reviewer:** [Name]
**Role Reviewed:** [Role]
**Period:** [Start] to [End]

### Users Reviewed

| User | Status | Decision | Notes |
|------|--------|----------|-------|
| user@example.com | Active | Retain | Regular usage |
| user2@example.com | Inactive | Revoke | No login 60 days |

### Summary
- Total users: X
- Retained: Y
- Revoked: Z
- Modified: W

### Findings
[Any security concerns or patterns noted]

### Next Review
[Scheduled date]
```

---

## Emergency Access

### Break-Glass Procedure

When normal access channels are unavailable:

1. **Document Emergency**
   - What is the emergency?
   - Why is immediate access needed?
   - What access is required?

2. **Obtain Verbal Approval**
   - Contact two of: CTO, Risk Officer, Legal
   - Record approval (timestamp, approver names)

3. **Access Emergency Credentials**
   - Retrieve from secure storage (HSM/Vault)
   - Two-person authorization required

4. **Execute with Full Logging**
   - All actions recorded
   - Session may be recorded
   - Time-limited (4 hours max)

5. **Post-Emergency Review**
   - Within 24 hours
   - Full incident report
   - Access review
   - Process improvement

### Emergency Contact Chain

```
Primary:   Risk Officer → [Phone]
Secondary: CTO → [Phone]
Tertiary:  CEO → [Phone]
Legal:     General Counsel → [Phone]
```

---

## Compliance Requirements

### Documentation Retention

| Document | Retention |
|----------|-----------|
| Access requests | 7 years |
| Approval records | 7 years |
| Revocation records | 7 years |
| Review reports | 7 years |
| Training records | Employment + 3 years |

### Audit Trail Requirements

All access changes must log:
- Who requested
- Who approved
- When provisioned
- What access granted
- Justification

### Regulatory Considerations

**SOC 2:**
- Access provisioning documented
- Reviews conducted regularly
- Revocation timely

**GDPR:**
- Access limited to necessary
- Data access logged
- Right to access supported

---

## Forms and Templates

### Access Request Form

```
ARCHON PRIME ACCESS REQUEST

Requester Information:
- Name: _______________
- Email: _______________
- Department: _______________
- Manager: _______________

Access Requested:
- Role: [ ] Observer [ ] Operator [ ] Admin [ ] Auditor [ ] Risk Officer
- Duration: [ ] Permanent [ ] Time-limited: ___ days
- Start Date: _______________

Business Justification:
_________________________________________________
_________________________________________________

Acknowledgments:
[ ] I have read the Acceptable Use Policy
[ ] I understand my security responsibilities
[ ] I agree to complete required training

Requester Signature: _______________ Date: _______________
Manager Approval: _______________ Date: _______________
```

### Access Revocation Form

```
ARCHON PRIME ACCESS REVOCATION

User Information:
- Name: _______________
- Email: _______________
- Current Role: _______________

Revocation Details:
- Reason: [ ] Termination [ ] Role Change [ ] Security [ ] Request [ ] Other
- Effective: [ ] Immediate [ ] Date: _______________
- Explanation: _______________

Actions Required:
[ ] Terminate sessions
[ ] Revoke tokens
[ ] Remove MFA devices
[ ] Notify user
[ ] Notify manager

Authorized By: _______________ Date: _______________
Executed By: _______________ Date: _______________
```

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | Jan 2026 | Operations | Initial version |
