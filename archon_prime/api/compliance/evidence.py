"""
ARCHON PRIME - Evidence Packaging & Export

Provides evidence collection, packaging, and export for
audits, regulatory inquiries, and internal reviews.
"""

import hashlib
import json
import zipfile
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Dict, Optional, Any, BinaryIO
from uuid import uuid4
from pathlib import Path


class EvidenceType(str, Enum):
    """Types of evidence that can be packaged."""

    # Decision Evidence
    DECISION_CHAIN = "decision_chain"
    SIGNAL_HISTORY = "signal_history"
    GATE_DECISIONS = "gate_decisions"

    # Trading Evidence
    TRADE_HISTORY = "trade_history"
    POSITION_LOG = "position_log"
    ORDER_AUDIT = "order_audit"

    # Risk Evidence
    RISK_ALERTS = "risk_alerts"
    KILL_SWITCH_LOG = "kill_switch_log"
    PANIC_HEDGE_LOG = "panic_hedge_log"

    # Admin Evidence
    ADMIN_ACTIONS = "admin_actions"
    ACCESS_LOG = "access_log"
    CONFIG_CHANGES = "config_changes"

    # System Evidence
    SYSTEM_HEALTH = "system_health"
    ERROR_LOG = "error_log"
    PERFORMANCE_METRICS = "performance_metrics"

    # Test Evidence
    TEST_RESULTS = "test_results"
    COVERAGE_REPORT = "coverage_report"
    LOAD_TEST_RESULTS = "load_test_results"


class EvidenceFormat(str, Enum):
    """Output formats for evidence exports."""

    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    ZIP = "zip"  # Bundle of multiple files


@dataclass
class EvidenceItem:
    """A single piece of evidence."""

    item_id: str
    evidence_type: EvidenceType
    title: str
    description: str
    collected_at: datetime
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Integrity
    hash: str = field(default="")

    def __post_init__(self):
        if not self.item_id:
            self.item_id = f"evi_{uuid4().hex[:12]}"
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA256 hash of evidence data."""
        data_str = json.dumps(self.data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify evidence hasn't been modified."""
        return self.hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary."""
        return {
            "item_id": self.item_id,
            "evidence_type": self.evidence_type.value,
            "title": self.title,
            "description": self.description,
            "collected_at": self.collected_at.isoformat(),
            "data": self.data,
            "metadata": self.metadata,
            "hash": self.hash,
        }


@dataclass
class EvidencePackage:
    """A complete evidence package for export."""

    package_id: str
    title: str
    purpose: str  # "audit", "regulatory", "internal_review", "incident"
    requested_by: str
    requested_at: datetime
    period_start: datetime
    period_end: datetime
    items: List[EvidenceItem] = field(default_factory=list)

    # Package metadata
    classification: str = "CONFIDENTIAL"
    retention_days: int = 2555  # 7 years default
    exported_at: Optional[datetime] = None
    exported_format: Optional[EvidenceFormat] = None

    # Integrity
    package_hash: str = field(default="")

    def __post_init__(self):
        if not self.package_id:
            self.package_id = f"pkg_{uuid4().hex[:12]}"

    def _compute_package_hash(self) -> str:
        """Compute hash of entire package."""
        item_hashes = [i.hash for i in self.items]
        combined = "|".join(sorted(item_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()

    def add_item(self, item: EvidenceItem):
        """Add an evidence item to the package."""
        self.items.append(item)
        self.package_hash = self._compute_package_hash()

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify package integrity."""
        results = {
            "package_id": self.package_id,
            "verified": True,
            "package_hash_valid": True,
            "items_verified": [],
            "issues": [],
        }

        for item in self.items:
            item_result = {
                "item_id": item.item_id,
                "valid": item.verify_integrity(),
            }
            results["items_verified"].append(item_result)

            if not item_result["valid"]:
                results["verified"] = False
                results["issues"].append(
                    f"Item {item.item_id} failed integrity check"
                )

        current_hash = self._compute_package_hash()
        if self.package_hash and self.package_hash != current_hash:
            results["verified"] = False
            results["package_hash_valid"] = False
            results["issues"].append("Package hash verification failed")

        return results

    def get_manifest(self) -> Dict[str, Any]:
        """Get package manifest."""
        return {
            "package_id": self.package_id,
            "title": self.title,
            "purpose": self.purpose,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "classification": self.classification,
            "retention_days": self.retention_days,
            "item_count": len(self.items),
            "evidence_types": list({i.evidence_type.value for i in self.items}),
            "package_hash": self.package_hash,
            "exported_at": (
                self.exported_at.isoformat() if self.exported_at else None
            ),
            "exported_format": (
                self.exported_format.value if self.exported_format else None
            ),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary."""
        return {
            **self.get_manifest(),
            "items": [i.to_dict() for i in self.items],
        }


class EvidencePackager:
    """
    Collects and packages evidence for export.

    Provides methods to collect various types of evidence
    and package them for audit or regulatory purposes.
    """

    def __init__(self, db_session=None, audit_logger=None):
        """
        Initialize evidence packager.

        Args:
            db_session: Database session for queries
            audit_logger: AuditLogger instance for access logging
        """
        self.db = db_session
        self.audit_logger = audit_logger

    def create_package(
        self,
        title: str,
        purpose: str,
        requested_by: str,
        period_start: datetime,
        period_end: datetime,
        classification: str = "CONFIDENTIAL",
    ) -> EvidencePackage:
        """
        Create a new evidence package.

        Args:
            title: Package title
            purpose: Purpose of the package
            requested_by: User/entity requesting the evidence
            period_start: Start of evidence period
            period_end: End of evidence period
            classification: Security classification

        Returns:
            New EvidencePackage
        """
        return EvidencePackage(
            package_id=f"pkg_{uuid4().hex[:12]}",
            title=title,
            purpose=purpose,
            requested_by=requested_by,
            requested_at=datetime.now(timezone.utc),
            period_start=period_start,
            period_end=period_end,
            classification=classification,
        )

    def collect_decision_chains(
        self,
        package: EvidencePackage,
        chains: List[Dict[str, Any]],
    ) -> EvidencePackage:
        """Add decision chain evidence to package."""
        item = EvidenceItem(
            item_id=f"evi_{uuid4().hex[:12]}",
            evidence_type=EvidenceType.DECISION_CHAIN,
            title="Decision Provenance Chains",
            description=(
                f"Complete decision chains from "
                f"{package.period_start.date()} to {package.period_end.date()}"
            ),
            collected_at=datetime.now(timezone.utc),
            data=chains,
            metadata={
                "chain_count": len(chains),
                "outcomes": self._count_outcomes(chains),
            },
        )
        package.add_item(item)
        return package

    def collect_signal_history(
        self,
        package: EvidencePackage,
        signals: List[Dict[str, Any]],
    ) -> EvidencePackage:
        """Add signal history evidence to package."""
        item = EvidenceItem(
            item_id=f"evi_{uuid4().hex[:12]}",
            evidence_type=EvidenceType.SIGNAL_HISTORY,
            title="Signal Gate History",
            description=(
                f"All signals processed from "
                f"{package.period_start.date()} to {package.period_end.date()}"
            ),
            collected_at=datetime.now(timezone.utc),
            data=signals,
            metadata={
                "total_signals": len(signals),
                "passed": sum(1 for s in signals if s.get("passed")),
                "blocked": sum(1 for s in signals if not s.get("passed")),
            },
        )
        package.add_item(item)
        return package

    def collect_trade_history(
        self,
        package: EvidencePackage,
        trades: List[Dict[str, Any]],
    ) -> EvidencePackage:
        """Add trade history evidence to package."""
        item = EvidenceItem(
            item_id=f"evi_{uuid4().hex[:12]}",
            evidence_type=EvidenceType.TRADE_HISTORY,
            title="Trade Execution History",
            description=(
                f"All executed trades from "
                f"{package.period_start.date()} to {package.period_end.date()}"
            ),
            collected_at=datetime.now(timezone.utc),
            data=trades,
            metadata={
                "total_trades": len(trades),
                "total_pnl": sum(t.get("pnl", 0) for t in trades),
                "symbols_traded": list({t.get("symbol") for t in trades}),
            },
        )
        package.add_item(item)
        return package

    def collect_risk_alerts(
        self,
        package: EvidencePackage,
        alerts: List[Dict[str, Any]],
    ) -> EvidencePackage:
        """Add risk alert evidence to package."""
        item = EvidenceItem(
            item_id=f"evi_{uuid4().hex[:12]}",
            evidence_type=EvidenceType.RISK_ALERTS,
            title="Risk Alert Log",
            description=(
                f"All risk alerts from "
                f"{package.period_start.date()} to {package.period_end.date()}"
            ),
            collected_at=datetime.now(timezone.utc),
            data=alerts,
            metadata={
                "total_alerts": len(alerts),
                "by_severity": self._count_by_field(alerts, "severity"),
                "acknowledged": sum(1 for a in alerts if a.get("acknowledged")),
            },
        )
        package.add_item(item)
        return package

    def collect_admin_actions(
        self,
        package: EvidencePackage,
        actions: List[Dict[str, Any]],
    ) -> EvidencePackage:
        """Add admin action evidence to package."""
        item = EvidenceItem(
            item_id=f"evi_{uuid4().hex[:12]}",
            evidence_type=EvidenceType.ADMIN_ACTIONS,
            title="Administrative Actions Log",
            description=(
                f"All admin actions from "
                f"{package.period_start.date()} to {package.period_end.date()}"
            ),
            collected_at=datetime.now(timezone.utc),
            data=actions,
            metadata={
                "total_actions": len(actions),
                "by_action_type": self._count_by_field(actions, "action_type"),
                "by_actor": self._count_by_field(actions, "actor"),
            },
        )
        package.add_item(item)
        return package

    def collect_test_evidence(
        self,
        package: EvidencePackage,
        test_results: Dict[str, Any],
    ) -> EvidencePackage:
        """Add test evidence to package."""
        item = EvidenceItem(
            item_id=f"evi_{uuid4().hex[:12]}",
            evidence_type=EvidenceType.TEST_RESULTS,
            title="Test Suite Results",
            description="Automated test suite execution results",
            collected_at=datetime.now(timezone.utc),
            data=test_results,
            metadata={
                "total_tests": test_results.get("total", 0),
                "passed": test_results.get("passed", 0),
                "failed": test_results.get("failed", 0),
                "coverage": test_results.get("coverage", 0),
            },
        )
        package.add_item(item)
        return package

    def _count_outcomes(self, chains: List[Dict]) -> Dict[str, int]:
        """Count outcomes in decision chains."""
        counts = {}
        for chain in chains:
            outcome = chain.get("outcome", "unknown")
            counts[outcome] = counts.get(outcome, 0) + 1
        return counts

    def _count_by_field(
        self, items: List[Dict], field: str
    ) -> Dict[str, int]:
        """Count items by a field value."""
        counts = {}
        for item in items:
            value = str(item.get(field, "unknown"))
            counts[value] = counts.get(value, 0) + 1
        return counts


def export_evidence_package(
    package: EvidencePackage,
    format: EvidenceFormat = EvidenceFormat.ZIP,
    output_path: Optional[Path] = None,
) -> bytes:
    """
    Export evidence package to specified format.

    Args:
        package: The EvidencePackage to export
        format: Output format
        output_path: Optional path to write file

    Returns:
        Bytes of the exported package
    """
    package.exported_at = datetime.now(timezone.utc)
    package.exported_format = format

    if format == EvidenceFormat.JSON:
        content = json.dumps(package.to_dict(), indent=2, default=str)
        data = content.encode("utf-8")

    elif format == EvidenceFormat.ZIP:
        data = _create_zip_bundle(package)

    else:
        # Default to JSON for unsupported formats
        content = json.dumps(package.to_dict(), indent=2, default=str)
        data = content.encode("utf-8")

    if output_path:
        output_path.write_bytes(data)

    return data


def _create_zip_bundle(package: EvidencePackage) -> bytes:
    """Create a ZIP bundle of the evidence package."""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add manifest
        manifest = json.dumps(package.get_manifest(), indent=2, default=str)
        zf.writestr("MANIFEST.json", manifest)

        # Add README
        readme = _generate_readme(package)
        zf.writestr("README.md", readme)

        # Add each evidence item
        for item in package.items:
            filename = f"evidence/{item.evidence_type.value}/{item.item_id}.json"
            content = json.dumps(item.to_dict(), indent=2, default=str)
            zf.writestr(filename, content)

        # Add integrity verification
        integrity = package.verify_integrity()
        zf.writestr("INTEGRITY.json", json.dumps(integrity, indent=2))

    return buffer.getvalue()


def _generate_readme(package: EvidencePackage) -> str:
    """Generate README for evidence package."""
    return f"""# Evidence Package: {package.title}

## Package Information

- **Package ID:** {package.package_id}
- **Purpose:** {package.purpose}
- **Requested By:** {package.requested_by}
- **Requested At:** {package.requested_at.isoformat()}
- **Classification:** {package.classification}

## Evidence Period

- **Start:** {package.period_start.isoformat()}
- **End:** {package.period_end.isoformat()}

## Contents

This package contains {len(package.items)} evidence items:

| Type | Title | Hash |
|------|-------|------|
{chr(10).join(f"| {i.evidence_type.value} | {i.title} | {i.hash[:16]}... |" for i in package.items)}

## Integrity Verification

Package Hash: `{package.package_hash}`

To verify integrity, compare the hashes in INTEGRITY.json with
the computed hashes of each evidence item.

## Retention

This package must be retained for {package.retention_days} days
({package.retention_days // 365} years) from the export date.

## Legal Notice

This evidence package is {package.classification} and contains
sensitive trading and operational data. Unauthorized disclosure
is prohibited.

---
Generated by ARCHON PRIME Compliance Module
Exported: {package.exported_at.isoformat() if package.exported_at else "Not yet exported"}
"""


def create_audit_bundle(
    packager: EvidencePackager,
    purpose: str,
    requested_by: str,
    period_start: datetime,
    period_end: datetime,
    include_types: List[EvidenceType],
    data_sources: Dict[EvidenceType, List[Dict[str, Any]]],
) -> EvidencePackage:
    """
    Create a complete audit bundle with multiple evidence types.

    Args:
        packager: EvidencePackager instance
        purpose: Purpose of the audit
        requested_by: Requester identity
        period_start: Start of audit period
        period_end: End of audit period
        include_types: Types of evidence to include
        data_sources: Data for each evidence type

    Returns:
        Complete EvidencePackage
    """
    package = packager.create_package(
        title=f"Audit Bundle - {purpose}",
        purpose=purpose,
        requested_by=requested_by,
        period_start=period_start,
        period_end=period_end,
    )

    # Add requested evidence types
    collectors = {
        EvidenceType.DECISION_CHAIN: packager.collect_decision_chains,
        EvidenceType.SIGNAL_HISTORY: packager.collect_signal_history,
        EvidenceType.TRADE_HISTORY: packager.collect_trade_history,
        EvidenceType.RISK_ALERTS: packager.collect_risk_alerts,
        EvidenceType.ADMIN_ACTIONS: packager.collect_admin_actions,
        EvidenceType.TEST_RESULTS: packager.collect_test_evidence,
    }

    for evidence_type in include_types:
        if evidence_type in collectors and evidence_type in data_sources:
            collectors[evidence_type](package, data_sources[evidence_type])

    return package


def hash_evidence(data: Any) -> str:
    """
    Compute SHA256 hash of evidence data.

    Args:
        data: Data to hash

    Returns:
        Hexadecimal hash string
    """
    data_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(data_str.encode()).hexdigest()
