"""
ARCHON PRIME - Decision Provenance Tracking

Provides complete chain-of-custody for every trading decision.
Answers: "Why did this trade happen?"
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Dict, Optional, Any, Set
from uuid import uuid4


class DecisionType(str, Enum):
    """Types of decisions in the trading chain."""

    # Signal Generation
    SIGNAL_GENERATED = "signal.generated"
    SIGNAL_VALIDATED = "signal.validated"
    SIGNAL_REJECTED = "signal.rejected"

    # Gate Decisions
    GATE_PASSED = "gate.passed"
    GATE_BLOCKED = "gate.blocked"
    GATE_OVERRIDE = "gate.override"

    # Risk Evaluation
    RISK_APPROVED = "risk.approved"
    RISK_REDUCED = "risk.reduced"
    RISK_REJECTED = "risk.rejected"

    # Position Actions
    POSITION_OPENED = "position.opened"
    POSITION_MODIFIED = "position.modified"
    POSITION_CLOSED = "position.closed"

    # Emergency Actions
    KILL_SWITCH_ACTIVATED = "emergency.kill_switch"
    PANIC_HEDGE_TRIGGERED = "emergency.panic_hedge"
    MANUAL_INTERVENTION = "emergency.manual"


class DecisionSource(str, Enum):
    """Source of a decision."""

    AI_AGENT = "ai_agent"
    SIGNAL_GATE = "signal_gate"
    RISK_ENGINE = "risk_engine"
    POSITION_MANAGER = "position_manager"
    ADMIN_USER = "admin_user"
    RISK_OFFICER = "risk_officer"
    SYSTEM_AUTO = "system_auto"
    EXTERNAL_SIGNAL = "external_signal"


@dataclass
class DecisionNode:
    """A single node in the decision chain."""

    node_id: str
    decision_type: DecisionType
    source: DecisionSource
    timestamp: datetime
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    rationale: str
    confidence: float  # 0.0 to 1.0
    parent_node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Integrity
    hash: str = field(default="")

    def __post_init__(self):
        if not self.node_id:
            self.node_id = f"node_{uuid4().hex[:12]}"
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA256 hash for integrity verification."""
        data = {
            "node_id": self.node_id,
            "decision_type": self.decision_type.value,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "input_data": self.input_data,
            "output_data": self.output_data,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "parent_node_id": self.parent_node_id,
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify node hasn't been tampered with."""
        return self.hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary."""
        return {
            "node_id": self.node_id,
            "decision_type": self.decision_type.value,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "input_data": self.input_data,
            "output_data": self.output_data,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "parent_node_id": self.parent_node_id,
            "metadata": self.metadata,
            "hash": self.hash,
        }


@dataclass
class DecisionChain:
    """A complete chain of decisions leading to an outcome."""

    chain_id: str
    root_node_id: str
    terminal_node_id: str
    outcome: str  # "executed", "rejected", "emergency_closed"
    created_at: datetime
    completed_at: datetime
    nodes: List[DecisionNode] = field(default_factory=list)

    # Chain integrity
    chain_hash: str = field(default="")

    def __post_init__(self):
        if not self.chain_id:
            self.chain_id = f"chain_{uuid4().hex[:12]}"
        if not self.chain_hash:
            self.chain_hash = self._compute_chain_hash()

    def _compute_chain_hash(self) -> str:
        """Compute hash of entire chain."""
        node_hashes = [n.hash for n in self.nodes]
        combined = "|".join(node_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def verify_chain_integrity(self) -> bool:
        """Verify entire chain hasn't been tampered with."""
        # Verify each node
        for node in self.nodes:
            if not node.verify_integrity():
                return False

        # Verify chain hash
        return self.chain_hash == self._compute_chain_hash()

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Get chronological timeline of decisions."""
        sorted_nodes = sorted(self.nodes, key=lambda n: n.timestamp)
        return [
            {
                "timestamp": n.timestamp.isoformat(),
                "decision": n.decision_type.value,
                "source": n.source.value,
                "rationale": n.rationale,
                "confidence": n.confidence,
            }
            for n in sorted_nodes
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary."""
        return {
            "chain_id": self.chain_id,
            "root_node_id": self.root_node_id,
            "terminal_node_id": self.terminal_node_id,
            "outcome": self.outcome,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "nodes": [n.to_dict() for n in self.nodes],
            "chain_hash": self.chain_hash,
            "timeline": self.get_timeline(),
        }


@dataclass
class ProvenanceQuery:
    """Query parameters for provenance searches."""

    # Time range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Filters
    decision_types: Optional[Set[DecisionType]] = None
    sources: Optional[Set[DecisionSource]] = None
    outcome: Optional[str] = None

    # Identifiers
    trade_id: Optional[str] = None
    signal_id: Optional[str] = None
    profile_id: Optional[str] = None
    user_id: Optional[str] = None

    # Options
    include_rejected: bool = True
    include_emergency: bool = True
    max_results: int = 100


class ProvenanceTracker:
    """
    Tracks and queries decision provenance.

    Maintains a complete audit trail of every decision
    from signal generation to trade execution.
    """

    def __init__(self, storage_backend=None):
        """
        Initialize provenance tracker.

        Args:
            storage_backend: Database or file storage for persistence
        """
        self.storage = storage_backend
        self._chains: Dict[str, DecisionChain] = {}
        self._nodes_by_id: Dict[str, DecisionNode] = {}
        self._active_chains: Dict[str, str] = {}  # context_id -> chain_id

    def start_chain(
        self,
        context_id: str,
        initial_decision: DecisionType,
        source: DecisionSource,
        input_data: Dict[str, Any],
        rationale: str,
        confidence: float = 1.0,
    ) -> DecisionChain:
        """
        Start a new decision chain.

        Args:
            context_id: Identifier for this decision context (e.g., signal_id)
            initial_decision: The first decision type
            source: Source of the decision
            input_data: Input data for the decision
            rationale: Human-readable rationale
            confidence: Confidence score (0.0 to 1.0)

        Returns:
            New DecisionChain
        """
        now = datetime.now(timezone.utc)

        # Create root node
        root_node = DecisionNode(
            node_id=f"node_{uuid4().hex[:12]}",
            decision_type=initial_decision,
            source=source,
            timestamp=now,
            input_data=input_data,
            output_data={},
            rationale=rationale,
            confidence=confidence,
        )

        # Create chain
        chain = DecisionChain(
            chain_id=f"chain_{uuid4().hex[:12]}",
            root_node_id=root_node.node_id,
            terminal_node_id=root_node.node_id,
            outcome="pending",
            created_at=now,
            completed_at=now,
            nodes=[root_node],
        )

        # Store
        self._chains[chain.chain_id] = chain
        self._nodes_by_id[root_node.node_id] = root_node
        self._active_chains[context_id] = chain.chain_id

        return chain

    def add_decision(
        self,
        context_id: str,
        decision_type: DecisionType,
        source: DecisionSource,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        rationale: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[DecisionNode]:
        """
        Add a decision to an active chain.

        Args:
            context_id: The context identifier
            decision_type: Type of decision
            source: Source of the decision
            input_data: Input data
            output_data: Output data
            rationale: Human-readable rationale
            confidence: Confidence score
            metadata: Additional metadata

        Returns:
            New DecisionNode or None if chain not found
        """
        chain_id = self._active_chains.get(context_id)
        if not chain_id:
            return None

        chain = self._chains.get(chain_id)
        if not chain:
            return None

        now = datetime.now(timezone.utc)

        # Create new node
        node = DecisionNode(
            node_id=f"node_{uuid4().hex[:12]}",
            decision_type=decision_type,
            source=source,
            timestamp=now,
            input_data=input_data,
            output_data=output_data,
            rationale=rationale,
            confidence=confidence,
            parent_node_id=chain.terminal_node_id,
            metadata=metadata or {},
        )

        # Update chain
        chain.nodes.append(node)
        chain.terminal_node_id = node.node_id
        chain.completed_at = now
        chain.chain_hash = chain._compute_chain_hash()

        # Store node
        self._nodes_by_id[node.node_id] = node

        return node

    def complete_chain(
        self,
        context_id: str,
        outcome: str,
        final_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[DecisionChain]:
        """
        Mark a decision chain as complete.

        Args:
            context_id: The context identifier
            outcome: Final outcome ("executed", "rejected", etc.)
            final_data: Optional final data to attach

        Returns:
            Completed DecisionChain or None
        """
        chain_id = self._active_chains.get(context_id)
        if not chain_id:
            return None

        chain = self._chains.get(chain_id)
        if not chain:
            return None

        # Update chain
        chain.outcome = outcome
        chain.completed_at = datetime.now(timezone.utc)

        # Attach final data to terminal node
        if final_data and chain.nodes:
            terminal = chain.nodes[-1]
            terminal.metadata["final_data"] = final_data

        # Recompute chain hash
        chain.chain_hash = chain._compute_chain_hash()

        # Remove from active
        del self._active_chains[context_id]

        # Persist if storage available
        if self.storage:
            self._persist_chain(chain)

        return chain

    def _persist_chain(self, chain: DecisionChain):
        """Persist chain to storage backend."""
        # Implementation depends on storage backend
        pass

    def query(self, query: ProvenanceQuery) -> List[DecisionChain]:
        """
        Query decision chains.

        Args:
            query: Query parameters

        Returns:
            List of matching DecisionChains
        """
        results = []

        for chain in self._chains.values():
            if self._matches_query(chain, query):
                results.append(chain)

        # Sort by created_at descending
        results.sort(key=lambda c: c.created_at, reverse=True)

        # Apply limit
        return results[:query.max_results]

    def _matches_query(
        self, chain: DecisionChain, query: ProvenanceQuery
    ) -> bool:
        """Check if chain matches query criteria."""
        # Time range
        if query.start_time and chain.created_at < query.start_time:
            return False
        if query.end_time and chain.created_at > query.end_time:
            return False

        # Outcome filter
        if query.outcome and chain.outcome != query.outcome:
            return False

        # Emergency filter
        if not query.include_emergency:
            for node in chain.nodes:
                if node.decision_type in (
                    DecisionType.KILL_SWITCH_ACTIVATED,
                    DecisionType.PANIC_HEDGE_TRIGGERED,
                ):
                    return False

        # Decision type filter
        if query.decision_types:
            chain_types = {n.decision_type for n in chain.nodes}
            if not chain_types & query.decision_types:
                return False

        # Source filter
        if query.sources:
            chain_sources = {n.source for n in chain.nodes}
            if not chain_sources & query.sources:
                return False

        return True


def query_decision_chain(
    chain_id: str,
    tracker: ProvenanceTracker,
) -> Optional[DecisionChain]:
    """
    Query a specific decision chain by ID.

    Args:
        chain_id: The chain identifier
        tracker: ProvenanceTracker instance

    Returns:
        DecisionChain or None
    """
    return tracker._chains.get(chain_id)


def get_trade_provenance(
    trade_id: str,
    tracker: ProvenanceTracker,
) -> Optional[DecisionChain]:
    """
    Get the complete provenance for a trade.

    Args:
        trade_id: The trade/position identifier
        tracker: ProvenanceTracker instance

    Returns:
        DecisionChain showing full decision history
    """
    query = ProvenanceQuery(
        trade_id=trade_id,
        max_results=1,
    )
    results = tracker.query(query)
    return results[0] if results else None


def get_signal_provenance(
    signal_id: str,
    tracker: ProvenanceTracker,
) -> Optional[DecisionChain]:
    """
    Get the complete provenance for a signal.

    Args:
        signal_id: The signal identifier
        tracker: ProvenanceTracker instance

    Returns:
        DecisionChain showing signal's journey
    """
    return tracker._chains.get(tracker._active_chains.get(signal_id))


def verify_decision_integrity(chain: DecisionChain) -> Dict[str, Any]:
    """
    Verify integrity of a decision chain.

    Args:
        chain: The DecisionChain to verify

    Returns:
        Verification results with details
    """
    results = {
        "chain_id": chain.chain_id,
        "verified": True,
        "chain_hash_valid": True,
        "nodes_verified": [],
        "issues": [],
    }

    # Verify each node
    for node in chain.nodes:
        node_result = {
            "node_id": node.node_id,
            "valid": node.verify_integrity(),
        }
        results["nodes_verified"].append(node_result)

        if not node_result["valid"]:
            results["verified"] = False
            results["issues"].append(
                f"Node {node.node_id} failed integrity check"
            )

    # Verify chain hash
    if not chain.verify_chain_integrity():
        results["verified"] = False
        results["chain_hash_valid"] = False
        results["issues"].append("Chain hash verification failed")

    return results
