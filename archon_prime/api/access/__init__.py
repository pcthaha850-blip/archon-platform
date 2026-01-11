"""
ARCHON PRIME - Access & Authority Module

Role-based access control, permissions, and audit logging.

Components:
- rbac.py: Role definitions, permissions, authorization decorators
- audit.py: Audit logging, compliance reports
- ACCESS_MODEL.md: Complete access model documentation
- ACCESS_PROCEDURES.md: Access request and revocation procedures

Usage:
    from archon_prime.api.access.rbac import (
        Role,
        Permission,
        require_role,
        require_permission,
        has_permission,
    )

    from archon_prime.api.access.audit import (
        AuditLogger,
        AuditEventType,
        audit_log,
    )
"""

from archon_prime.api.access.rbac import (
    Role,
    Permission,
    AuthContext,
    SessionConfig,
    ROLE_PERMISSIONS,
    ROLE_SESSION_CONFIG,
    get_effective_permissions,
    has_permission,
    has_role,
    require_permission,
    require_role,
    require_roles,
    require_mfa,
    is_sensitive_action,
    can_assign_role,
    get_role_expiry,
)

from archon_prime.api.access.audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditResult,
    AuditSeverity,
    AuditActor,
    AuditAction,
    audit_log,
    generate_access_report,
    generate_admin_actions_report,
)

__all__ = [
    # Roles and Permissions
    "Role",
    "Permission",
    "AuthContext",
    "SessionConfig",
    "ROLE_PERMISSIONS",
    "ROLE_SESSION_CONFIG",
    "get_effective_permissions",
    "has_permission",
    "has_role",
    "require_permission",
    "require_role",
    "require_roles",
    "require_mfa",
    "is_sensitive_action",
    "can_assign_role",
    "get_role_expiry",

    # Audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditResult",
    "AuditSeverity",
    "AuditActor",
    "AuditAction",
    "audit_log",
    "generate_access_report",
    "generate_admin_actions_report",
]
