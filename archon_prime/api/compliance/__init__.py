"""
ARCHON PRIME - Compliance & Evidence Module

Provides evidence exports, provenance queries, and audit trail interfaces
for regulatory and internal compliance requirements.

Components:
- provenance.py: Decision provenance tracking and queries
- evidence.py: Evidence packaging and export functionality
- reports.py: Compliance report generation
- COMPLIANCE_GUIDE.md: Complete compliance documentation

Usage:
    from archon_prime.api.compliance import (
        ProvenanceTracker,
        EvidencePackager,
        ComplianceReporter,
        query_decision_chain,
        export_evidence_package,
        generate_compliance_report,
    )
"""

from archon_prime.api.compliance.provenance import (
    ProvenanceTracker,
    DecisionNode,
    DecisionChain,
    ProvenanceQuery,
    query_decision_chain,
    get_trade_provenance,
    get_signal_provenance,
    verify_decision_integrity,
)

from archon_prime.api.compliance.evidence import (
    EvidencePackager,
    EvidencePackage,
    EvidenceType,
    EvidenceFormat,
    export_evidence_package,
    create_audit_bundle,
    hash_evidence,
)

from archon_prime.api.compliance.reports import (
    ComplianceReporter,
    ReportType,
    ReportPeriod,
    ComplianceReport,
    generate_compliance_report,
    generate_regulatory_summary,
    generate_risk_disclosure,
)

__all__ = [
    # Provenance
    "ProvenanceTracker",
    "DecisionNode",
    "DecisionChain",
    "ProvenanceQuery",
    "query_decision_chain",
    "get_trade_provenance",
    "get_signal_provenance",
    "verify_decision_integrity",

    # Evidence
    "EvidencePackager",
    "EvidencePackage",
    "EvidenceType",
    "EvidenceFormat",
    "export_evidence_package",
    "create_audit_bundle",
    "hash_evidence",

    # Reports
    "ComplianceReporter",
    "ReportType",
    "ReportPeriod",
    "ComplianceReport",
    "generate_compliance_report",
    "generate_regulatory_summary",
    "generate_risk_disclosure",
]
