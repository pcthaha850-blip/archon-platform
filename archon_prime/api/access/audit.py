"""
ARCHON PRIME - Audit Logging System

Complete audit trail for all administrative and sensitive actions.
Supports compliance requirements (SOC 2, GDPR).
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from uuid import uuid4
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


# ============================================================
# Audit Event Types
# ============================================================


class AuditEventType(str, Enum):
    """Categories of auditable events."""

    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token.refresh"
    AUTH_MFA_SUCCESS = "auth.mfa.success"
    AUTH_MFA_FAILURE = "auth.mfa.failure"
    AUTH_PASSWORD_CHANGE = "auth.password.change"
    AUTH_PASSWORD_RESET = "auth.password.reset"

    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_SUSPENDED = "user.suspended"
    USER_RESTORED = "user.restored"
    USER_ROLE_ASSIGNED = "user.role.assigned"
    USER_ROLE_REVOKED = "user.role.revoked"

    # Profile Management
    PROFILE_CREATED = "profile.created"
    PROFILE_UPDATED = "profile.updated"
    PROFILE_DELETED = "profile.deleted"
    PROFILE_CONNECTED = "profile.connected"
    PROFILE_DISCONNECTED = "profile.disconnected"
    PROFILE_FORCE_DISCONNECTED = "profile.force_disconnected"

    # Trading Operations
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    POSITION_HEDGED = "position.hedged"
    POSITION_MODIFIED = "position.modified"

    # Signal Gate
    SIGNAL_SUBMITTED = "signal.submitted"
    SIGNAL_APPROVED = "signal.approved"
    SIGNAL_REJECTED = "signal.rejected"
    SIGNAL_OVERRIDDEN = "signal.overridden"
    SIGNAL_EXECUTED = "signal.executed"
    SIGNAL_CONFIG_UPDATED = "signal.config.updated"

    # Risk Controls
    RISK_ALERT_CREATED = "risk.alert.created"
    RISK_ALERT_ACKNOWLEDGED = "risk.alert.acknowledged"
    RISK_PARAMS_UPDATED = "risk.params.updated"
    RISK_KILL_SWITCH_ACTIVATED = "risk.kill_switch.activated"
    RISK_KILL_SWITCH_LIFTED = "risk.kill_switch.lifted"

    # System Operations
    SYSTEM_CONFIG_UPDATED = "system.config.updated"
    SYSTEM_MAINTENANCE_ENABLED = "system.maintenance.enabled"
    SYSTEM_MAINTENANCE_DISABLED = "system.maintenance.disabled"
    SYSTEM_SERVICE_RESTARTED = "system.service.restarted"
    SYSTEM_BROADCAST_SENT = "system.broadcast.sent"

    # Data Access
    DATA_EXPORTED = "data.exported"
    DATA_ACCESSED = "data.accessed"
    AUDIT_LOG_ACCESSED = "audit.log.accessed"

    # Emergency
    EMERGENCY_BREAK_GLASS = "emergency.break_glass"
    EMERGENCY_ACTION = "emergency.action"


class AuditResult(str, Enum):
    """Result of an audited action."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


class AuditSeverity(str, Enum):
    """Severity level of audit event."""

    LOW = "low"           # Routine operations
    MEDIUM = "medium"     # Notable actions
    HIGH = "high"         # Sensitive actions
    CRITICAL = "critical" # Emergency/risk events


# ============================================================
# Audit Event Structure
# ============================================================


@dataclass
class AuditActor:
    """Who performed the action."""

    user_id: str
    email: str
    roles: List[str]
    ip_address: str
    user_agent: str
    session_id: Optional[str] = None
    mfa_verified: bool = False


@dataclass
class AuditAction:
    """What action was performed."""

    type: AuditEventType
    resource_type: str
    resource_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    """Complete audit event record."""

    event_id: str
    timestamp: datetime
    actor: AuditActor
    action: AuditAction
    result: AuditResult
    severity: AuditSeverity
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "actor": asdict(self.actor),
            "action": {
                "type": self.action.type.value,
                "resource_type": self.action.resource_type,
                "resource_id": self.action.resource_id,
                "details": self.action.details,
            },
            "result": self.result.value,
            "severity": self.severity.value,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    def compute_hash(self) -> str:
        """Compute SHA256 hash for integrity verification."""
        content = f"{self.event_id}{self.timestamp.isoformat()}{self.actor.user_id}{self.action.type.value}"
        return hashlib.sha256(content.encode()).hexdigest()


# ============================================================
# Severity Mapping
# ============================================================


EVENT_SEVERITY: Dict[AuditEventType, AuditSeverity] = {
    # Low severity - routine operations
    AuditEventType.AUTH_LOGIN_SUCCESS: AuditSeverity.LOW,
    AuditEventType.AUTH_LOGOUT: AuditSeverity.LOW,
    AuditEventType.AUTH_TOKEN_REFRESH: AuditSeverity.LOW,
    AuditEventType.DATA_ACCESSED: AuditSeverity.LOW,

    # Medium severity - notable actions
    AuditEventType.AUTH_LOGIN_FAILURE: AuditSeverity.MEDIUM,
    AuditEventType.AUTH_MFA_FAILURE: AuditSeverity.MEDIUM,
    AuditEventType.USER_CREATED: AuditSeverity.MEDIUM,
    AuditEventType.USER_UPDATED: AuditSeverity.MEDIUM,
    AuditEventType.PROFILE_CREATED: AuditSeverity.MEDIUM,
    AuditEventType.PROFILE_CONNECTED: AuditSeverity.MEDIUM,
    AuditEventType.SIGNAL_SUBMITTED: AuditSeverity.MEDIUM,
    AuditEventType.SIGNAL_APPROVED: AuditSeverity.MEDIUM,
    AuditEventType.SIGNAL_REJECTED: AuditSeverity.MEDIUM,

    # High severity - sensitive actions
    AuditEventType.AUTH_PASSWORD_CHANGE: AuditSeverity.HIGH,
    AuditEventType.AUTH_PASSWORD_RESET: AuditSeverity.HIGH,
    AuditEventType.USER_DELETED: AuditSeverity.HIGH,
    AuditEventType.USER_SUSPENDED: AuditSeverity.HIGH,
    AuditEventType.USER_ROLE_ASSIGNED: AuditSeverity.HIGH,
    AuditEventType.USER_ROLE_REVOKED: AuditSeverity.HIGH,
    AuditEventType.PROFILE_FORCE_DISCONNECTED: AuditSeverity.HIGH,
    AuditEventType.POSITION_CLOSED: AuditSeverity.HIGH,
    AuditEventType.POSITION_HEDGED: AuditSeverity.HIGH,
    AuditEventType.SIGNAL_OVERRIDDEN: AuditSeverity.HIGH,
    AuditEventType.RISK_PARAMS_UPDATED: AuditSeverity.HIGH,
    AuditEventType.SYSTEM_CONFIG_UPDATED: AuditSeverity.HIGH,
    AuditEventType.DATA_EXPORTED: AuditSeverity.HIGH,

    # Critical severity - emergency/risk events
    AuditEventType.RISK_KILL_SWITCH_ACTIVATED: AuditSeverity.CRITICAL,
    AuditEventType.RISK_KILL_SWITCH_LIFTED: AuditSeverity.CRITICAL,
    AuditEventType.EMERGENCY_BREAK_GLASS: AuditSeverity.CRITICAL,
    AuditEventType.EMERGENCY_ACTION: AuditSeverity.CRITICAL,
}


def get_event_severity(event_type: AuditEventType) -> AuditSeverity:
    """Get severity for an event type."""
    return EVENT_SEVERITY.get(event_type, AuditSeverity.MEDIUM)


# ============================================================
# Audit Logger
# ============================================================


class AuditLogger:
    """
    Central audit logging service.

    All audit events flow through this class.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db_session = db_session
        self._buffer: List[AuditEvent] = []
        self._buffer_size = 100

    async def log(
        self,
        event_type: AuditEventType,
        actor: AuditActor,
        resource_type: str,
        resource_id: Optional[str] = None,
        result: AuditResult = AuditResult.SUCCESS,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log an audit event."""
        event = AuditEvent(
            event_id=f"evt_{uuid4().hex[:16]}",
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            action=AuditAction(
                type=event_type,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
            ),
            result=result,
            severity=get_event_severity(event_type),
            request_id=request_id,
            correlation_id=correlation_id,
            duration_ms=duration_ms,
            error_message=error_message,
            metadata=metadata or {},
        )

        # Log to structured logger
        logger.info(
            "AUDIT",
            extra={
                "audit_event": event.to_dict(),
                "event_hash": event.compute_hash(),
            },
        )

        # Store in database (if session available)
        if self.db_session:
            await self._persist_event(event)

        # Buffer for batch processing
        self._buffer.append(event)
        if len(self._buffer) >= self._buffer_size:
            await self._flush_buffer()

        return event

    async def _persist_event(self, event: AuditEvent) -> None:
        """Persist event to database."""
        # Implementation would insert into audit_logs table
        pass

    async def _flush_buffer(self) -> None:
        """Flush buffered events."""
        if not self._buffer:
            return

        # Batch insert to database
        # Send to external logging service (Datadog, Splunk, etc.)
        self._buffer.clear()

    async def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        result: Optional[AuditResult] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        # Implementation would query audit_logs table
        pass

    async def export(
        self,
        start_time: datetime,
        end_time: datetime,
        format: str = "json",
        include_hash: bool = True,
    ) -> str:
        """Export audit events for compliance."""
        events = await self.query(
            start_time=start_time,
            end_time=end_time,
            limit=10000,
        )

        if format == "json":
            export_data = {
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "period_start": start_time.isoformat(),
                "period_end": end_time.isoformat(),
                "event_count": len(events),
                "events": [e.to_dict() for e in events],
            }
            if include_hash:
                content = json.dumps(export_data, sort_keys=True, default=str)
                export_data["integrity_hash"] = hashlib.sha256(content.encode()).hexdigest()

            return json.dumps(export_data, indent=2, default=str)

        raise ValueError(f"Unsupported format: {format}")


# ============================================================
# Audit Decorator
# ============================================================


def audit_log(
    event_type: AuditEventType,
    resource_type: str,
    resource_id_param: Optional[str] = None,
    include_request: bool = False,
    include_response: bool = False,
):
    """
    Decorator to automatically audit function calls.

    Usage:
        @audit_log(AuditEventType.USER_CREATED, "user")
        async def create_user(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            start_time = time.monotonic()

            # Extract auth context
            auth_context = kwargs.get("auth_context")
            if not auth_context:
                # No audit if no auth context
                return await func(*args, **kwargs)

            # Build actor
            actor = AuditActor(
                user_id=auth_context.user_id,
                email=auth_context.email,
                roles=[r.value for r in auth_context.roles],
                ip_address=auth_context.ip_address,
                user_agent=auth_context.user_agent,
                session_id=auth_context.session_id,
                mfa_verified=auth_context.mfa_verified,
            )

            # Get resource ID
            resource_id = None
            if resource_id_param:
                resource_id = kwargs.get(resource_id_param) or \
                             (args[0] if args else None)

            # Build details
            details = {}
            if include_request:
                # Sanitize request data (remove sensitive fields)
                request_data = kwargs.get("request") or kwargs.get("data")
                if request_data:
                    details["request"] = _sanitize_for_audit(request_data)

            # Get audit logger
            audit_logger = kwargs.get("audit_logger") or AuditLogger()

            try:
                result = await func(*args, **kwargs)

                duration_ms = int((time.monotonic() - start_time) * 1000)

                if include_response and result:
                    details["response"] = _sanitize_for_audit(result)

                await audit_logger.log(
                    event_type=event_type,
                    actor=actor,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    result=AuditResult.SUCCESS,
                    details=details,
                    duration_ms=duration_ms,
                )

                return result

            except Exception as e:
                duration_ms = int((time.monotonic() - start_time) * 1000)

                await audit_logger.log(
                    event_type=event_type,
                    actor=actor,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    result=AuditResult.ERROR,
                    details=details,
                    error_message=str(e),
                    duration_ms=duration_ms,
                )

                raise

        return wrapper
    return decorator


def _sanitize_for_audit(data: Any) -> Any:
    """Remove sensitive fields from data before logging."""
    sensitive_fields = {
        "password", "password_hash", "secret", "token", "api_key",
        "mt5_password", "mt5_password_encrypted", "encryption_key",
        "credit_card", "ssn", "private_key",
    }

    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k.lower() in sensitive_fields else _sanitize_for_audit(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_sanitize_for_audit(item) for item in data]
    elif hasattr(data, "__dict__"):
        return _sanitize_for_audit(data.__dict__)
    else:
        return data


# ============================================================
# Compliance Reports
# ============================================================


@dataclass
class ComplianceReport:
    """Structured compliance report."""

    report_id: str
    report_type: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    summary: Dict[str, Any]
    details: List[Dict[str, Any]]
    integrity_hash: str


async def generate_access_report(
    audit_logger: AuditLogger,
    start_time: datetime,
    end_time: datetime,
) -> ComplianceReport:
    """Generate access control compliance report."""
    events = await audit_logger.query(
        start_time=start_time,
        end_time=end_time,
        event_types=[
            AuditEventType.AUTH_LOGIN_SUCCESS,
            AuditEventType.AUTH_LOGIN_FAILURE,
            AuditEventType.USER_ROLE_ASSIGNED,
            AuditEventType.USER_ROLE_REVOKED,
        ],
    )

    # Aggregate statistics
    login_success = len([e for e in events if e.action.type == AuditEventType.AUTH_LOGIN_SUCCESS])
    login_failure = len([e for e in events if e.action.type == AuditEventType.AUTH_LOGIN_FAILURE])
    role_changes = len([e for e in events if "role" in e.action.type.value])

    summary = {
        "total_login_attempts": login_success + login_failure,
        "successful_logins": login_success,
        "failed_logins": login_failure,
        "role_changes": role_changes,
        "unique_users": len(set(e.actor.user_id for e in events)),
    }

    report_data = {
        "summary": summary,
        "events": [e.to_dict() for e in events],
    }
    integrity_hash = hashlib.sha256(
        json.dumps(report_data, sort_keys=True, default=str).encode()
    ).hexdigest()

    return ComplianceReport(
        report_id=f"rpt_{uuid4().hex[:16]}",
        report_type="access_control",
        generated_at=datetime.now(timezone.utc),
        period_start=start_time,
        period_end=end_time,
        summary=summary,
        details=[e.to_dict() for e in events],
        integrity_hash=integrity_hash,
    )


async def generate_admin_actions_report(
    audit_logger: AuditLogger,
    start_time: datetime,
    end_time: datetime,
) -> ComplianceReport:
    """Generate administrative actions compliance report."""
    # Query high and critical severity events
    events = await audit_logger.query(
        start_time=start_time,
        end_time=end_time,
        severity=AuditSeverity.HIGH,
    )

    critical_events = await audit_logger.query(
        start_time=start_time,
        end_time=end_time,
        severity=AuditSeverity.CRITICAL,
    )

    all_events = events + critical_events

    summary = {
        "total_admin_actions": len(all_events),
        "high_severity": len(events),
        "critical_severity": len(critical_events),
        "by_type": {},
        "by_actor": {},
    }

    # Aggregate by type
    for event in all_events:
        event_type = event.action.type.value
        summary["by_type"][event_type] = summary["by_type"].get(event_type, 0) + 1

        actor_email = event.actor.email
        summary["by_actor"][actor_email] = summary["by_actor"].get(actor_email, 0) + 1

    report_data = {
        "summary": summary,
        "events": [e.to_dict() for e in all_events],
    }
    integrity_hash = hashlib.sha256(
        json.dumps(report_data, sort_keys=True, default=str).encode()
    ).hexdigest()

    return ComplianceReport(
        report_id=f"rpt_{uuid4().hex[:16]}",
        report_type="admin_actions",
        generated_at=datetime.now(timezone.utc),
        period_start=start_time,
        period_end=end_time,
        summary=summary,
        details=[e.to_dict() for e in all_events],
        integrity_hash=integrity_hash,
    )
