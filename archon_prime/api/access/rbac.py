"""
ARCHON PRIME - Role-Based Access Control (RBAC)

Defines roles, permissions, and authorization logic.
This is the authoritative source for access control.
"""

from enum import Enum
from typing import Set, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from functools import wraps

from fastapi import HTTPException, status, Depends


# ============================================================
# Permissions
# ============================================================


class Permission(str, Enum):
    """All permissions in the system."""

    # User Management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_READ_ALL = "user:read_all"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_SUSPEND = "user:suspend"
    USER_PASSWORD_RESET = "user:password_reset"

    # Profile Management
    PROFILE_READ = "profile:read"
    PROFILE_READ_ALL = "profile:read_all"
    PROFILE_UPDATE = "profile:update"
    PROFILE_DISCONNECT = "profile:disconnect"
    PROFILE_CONFIG = "profile:config"

    # Trading Operations
    POSITION_READ = "position:read"
    POSITION_READ_ALL = "position:read_all"
    POSITION_CLOSE = "position:close"
    POSITION_HEDGE = "position:hedge"
    TRADE_HISTORY_READ = "trade_history:read"

    # Signal Gate
    SIGNAL_READ = "signal:read"
    SIGNAL_READ_ALL = "signal:read_all"
    SIGNAL_OVERRIDE = "signal:override"
    SIGNAL_CONFIG = "signal:config"

    # Risk Controls
    RISK_KILL_SWITCH = "risk:kill_switch"
    RISK_KILL_SWITCH_LIFT = "risk:kill_switch_lift"
    RISK_PARAMS_UPDATE = "risk:params_update"
    RISK_ALERT_READ = "risk:alert_read"
    RISK_ALERT_ACKNOWLEDGE = "risk:alert_acknowledge"

    # System Operations
    SYSTEM_HEALTH_READ = "system:health_read"
    SYSTEM_METRICS_READ = "system:metrics_read"
    SYSTEM_CONFIG_READ = "system:config_read"
    SYSTEM_CONFIG_UPDATE = "system:config_update"
    SYSTEM_RESTART = "system:restart"
    SYSTEM_MAINTENANCE = "system:maintenance"
    SYSTEM_BROADCAST = "system:broadcast"

    # Audit & Compliance
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    AUDIT_ADMIN_ACTIONS = "audit:admin_actions"
    COMPLIANCE_REPORT = "compliance:report"


# ============================================================
# Roles
# ============================================================


class Role(str, Enum):
    """System roles in hierarchy order."""

    OWNER = "OWNER"
    RISK_OFFICER = "RISK_OFFICER"
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    AUDITOR = "AUDITOR"
    OBSERVER = "OBSERVER"


# ============================================================
# Role Permission Mappings
# ============================================================


ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.OWNER: {
        # All permissions
        *Permission,
    },

    Role.RISK_OFFICER: {
        # User (limited)
        Permission.USER_READ,
        Permission.USER_READ_ALL,
        Permission.USER_SUSPEND,

        # Profile
        Permission.PROFILE_READ,
        Permission.PROFILE_READ_ALL,
        Permission.PROFILE_DISCONNECT,
        Permission.PROFILE_CONFIG,

        # Trading
        Permission.POSITION_READ,
        Permission.POSITION_READ_ALL,
        Permission.POSITION_CLOSE,
        Permission.POSITION_HEDGE,
        Permission.TRADE_HISTORY_READ,

        # Signal Gate
        Permission.SIGNAL_READ,
        Permission.SIGNAL_READ_ALL,
        Permission.SIGNAL_OVERRIDE,
        Permission.SIGNAL_CONFIG,

        # Risk Controls (full)
        Permission.RISK_KILL_SWITCH,
        Permission.RISK_PARAMS_UPDATE,
        Permission.RISK_ALERT_READ,
        Permission.RISK_ALERT_ACKNOWLEDGE,

        # System (limited)
        Permission.SYSTEM_HEALTH_READ,
        Permission.SYSTEM_METRICS_READ,
        Permission.SYSTEM_MAINTENANCE,
        Permission.SYSTEM_BROADCAST,

        # Audit (read only)
        Permission.AUDIT_READ,
        Permission.AUDIT_ADMIN_ACTIONS,
        Permission.COMPLIANCE_REPORT,
    },

    Role.ADMIN: {
        # User (full except delete)
        Permission.USER_CREATE,
        Permission.USER_READ,
        Permission.USER_READ_ALL,
        Permission.USER_UPDATE,
        Permission.USER_SUSPEND,
        Permission.USER_PASSWORD_RESET,

        # Profile (limited)
        Permission.PROFILE_READ,
        Permission.PROFILE_READ_ALL,
        Permission.PROFILE_DISCONNECT,

        # Risk (alerts only)
        Permission.RISK_ALERT_READ,

        # System
        Permission.SYSTEM_HEALTH_READ,
        Permission.SYSTEM_METRICS_READ,
        Permission.SYSTEM_RESTART,
        Permission.SYSTEM_MAINTENANCE,
        Permission.SYSTEM_BROADCAST,
    },

    Role.OPERATOR: {
        # Profile (view only)
        Permission.PROFILE_READ_ALL,

        # Risk (view only)
        Permission.RISK_ALERT_READ,

        # System (operational)
        Permission.SYSTEM_HEALTH_READ,
        Permission.SYSTEM_METRICS_READ,
        Permission.SYSTEM_RESTART,  # With documented reason
    },

    Role.AUDITOR: {
        # User (read only)
        Permission.USER_READ,
        Permission.USER_READ_ALL,

        # Profile (read only)
        Permission.PROFILE_READ,
        Permission.PROFILE_READ_ALL,

        # Trading (read only)
        Permission.POSITION_READ_ALL,
        Permission.TRADE_HISTORY_READ,

        # Signal (read only)
        Permission.SIGNAL_READ,
        Permission.SIGNAL_READ_ALL,

        # Risk (read only)
        Permission.RISK_ALERT_READ,

        # System (read only)
        Permission.SYSTEM_HEALTH_READ,
        Permission.SYSTEM_METRICS_READ,

        # Audit (full read + export)
        Permission.AUDIT_READ,
        Permission.AUDIT_EXPORT,
        Permission.AUDIT_ADMIN_ACTIONS,
        Permission.COMPLIANCE_REPORT,
    },

    Role.OBSERVER: {
        # Minimal read-only
        Permission.SYSTEM_HEALTH_READ,
        Permission.SYSTEM_METRICS_READ,
    },
}


# ============================================================
# Session Configuration
# ============================================================


@dataclass
class SessionConfig:
    """Session configuration per role."""

    session_duration_hours: int
    idle_timeout_minutes: int
    max_concurrent_sessions: int
    mfa_required: bool
    mfa_on_sensitive: bool = False
    geo_restricted: bool = False


ROLE_SESSION_CONFIG: dict[Role, SessionConfig] = {
    Role.OWNER: SessionConfig(
        session_duration_hours=1,
        idle_timeout_minutes=15,
        max_concurrent_sessions=1,
        mfa_required=True,
        geo_restricted=True,
    ),
    Role.RISK_OFFICER: SessionConfig(
        session_duration_hours=4,
        idle_timeout_minutes=30,
        max_concurrent_sessions=2,
        mfa_required=True,
        geo_restricted=True,
    ),
    Role.ADMIN: SessionConfig(
        session_duration_hours=8,
        idle_timeout_minutes=60,
        max_concurrent_sessions=2,
        mfa_required=False,
        mfa_on_sensitive=True,
    ),
    Role.OPERATOR: SessionConfig(
        session_duration_hours=8,
        idle_timeout_minutes=60,
        max_concurrent_sessions=3,
        mfa_required=True,
    ),
    Role.AUDITOR: SessionConfig(
        session_duration_hours=4,
        idle_timeout_minutes=30,
        max_concurrent_sessions=1,
        mfa_required=True,
    ),
    Role.OBSERVER: SessionConfig(
        session_duration_hours=4,
        idle_timeout_minutes=30,
        max_concurrent_sessions=1,
        mfa_required=True,
    ),
}


# ============================================================
# Authorization Context
# ============================================================


@dataclass
class AuthContext:
    """Authorization context for a request."""

    user_id: str
    email: str
    roles: Set[Role]
    permissions: Set[Permission]
    session_id: str
    mfa_verified: bool
    ip_address: str
    user_agent: str
    session_start: datetime
    last_activity: datetime


def get_effective_permissions(roles: Set[Role]) -> Set[Permission]:
    """Get all permissions for a set of roles."""
    permissions = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, set()))
    return permissions


def has_permission(context: AuthContext, permission: Permission) -> bool:
    """Check if context has a specific permission."""
    return permission in context.permissions


def has_any_permission(context: AuthContext, permissions: Set[Permission]) -> bool:
    """Check if context has any of the specified permissions."""
    return bool(context.permissions & permissions)


def has_all_permissions(context: AuthContext, permissions: Set[Permission]) -> bool:
    """Check if context has all of the specified permissions."""
    return permissions.issubset(context.permissions)


def has_role(context: AuthContext, role: Role) -> bool:
    """Check if context has a specific role."""
    return role in context.roles


def has_any_role(context: AuthContext, roles: Set[Role]) -> bool:
    """Check if context has any of the specified roles."""
    return bool(context.roles & roles)


# ============================================================
# Authorization Decorators
# ============================================================


def require_permission(permission: Permission):
    """Decorator to require a specific permission."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get auth context from request (injected by dependency)
            auth_context: AuthContext = kwargs.get("auth_context")
            if not auth_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not has_permission(auth_context, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permissions(permissions: Set[Permission], require_all: bool = True):
    """Decorator to require multiple permissions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            auth_context: AuthContext = kwargs.get("auth_context")
            if not auth_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if require_all:
                if not has_all_permissions(auth_context, permissions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions",
                    )
            else:
                if not has_any_permission(auth_context, permissions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions",
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: Role):
    """Decorator to require a specific role."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            auth_context: AuthContext = kwargs.get("auth_context")
            if not auth_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not has_role(auth_context, role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {role.value}",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_roles(roles: Set[Role], require_all: bool = False):
    """Decorator to require one or all of specified roles."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            auth_context: AuthContext = kwargs.get("auth_context")
            if not auth_context:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if require_all:
                if not roles.issubset(auth_context.roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient roles",
                    )
            else:
                if not has_any_role(auth_context, roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient roles",
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_mfa(func):
    """Decorator to require MFA verification."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        auth_context: AuthContext = kwargs.get("auth_context")
        if not auth_context:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        if not auth_context.mfa_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA verification required",
            )

        return await func(*args, **kwargs)
    return wrapper


# ============================================================
# Sensitive Actions Registry
# ============================================================


SENSITIVE_ACTIONS: Set[Permission] = {
    Permission.USER_DELETE,
    Permission.USER_SUSPEND,
    Permission.RISK_KILL_SWITCH,
    Permission.RISK_KILL_SWITCH_LIFT,
    Permission.RISK_PARAMS_UPDATE,
    Permission.SIGNAL_OVERRIDE,
    Permission.SYSTEM_CONFIG_UPDATE,
    Permission.POSITION_CLOSE,
    Permission.POSITION_HEDGE,
}


def is_sensitive_action(permission: Permission) -> bool:
    """Check if an action is considered sensitive."""
    return permission in SENSITIVE_ACTIONS


# ============================================================
# Role Assignment Validation
# ============================================================


ROLE_ASSIGNMENT_APPROVERS: dict[Role, Set[Role]] = {
    Role.OWNER: set(),  # Board approval (out of system)
    Role.RISK_OFFICER: {Role.OWNER},
    Role.ADMIN: {Role.OWNER, Role.RISK_OFFICER},
    Role.OPERATOR: {Role.OWNER, Role.ADMIN},
    Role.AUDITOR: {Role.OWNER},
    Role.OBSERVER: {Role.OWNER, Role.ADMIN},
}


def can_assign_role(assigner_roles: Set[Role], target_role: Role) -> bool:
    """Check if assigner can assign target role."""
    required_approvers = ROLE_ASSIGNMENT_APPROVERS.get(target_role, set())
    if not required_approvers:
        return False  # Cannot assign via system
    return bool(assigner_roles & required_approvers)


# ============================================================
# Access Expiry
# ============================================================


ROLE_MAX_DURATION: dict[Role, Optional[timedelta]] = {
    Role.OWNER: None,  # No expiry
    Role.RISK_OFFICER: timedelta(days=365),
    Role.ADMIN: timedelta(days=90),
    Role.OPERATOR: timedelta(days=30),
    Role.AUDITOR: timedelta(days=90),  # Per engagement
    Role.OBSERVER: timedelta(days=90),
}


def get_role_expiry(role: Role, granted_at: datetime) -> Optional[datetime]:
    """Get expiry datetime for a role."""
    duration = ROLE_MAX_DURATION.get(role)
    if duration is None:
        return None
    return granted_at + duration
