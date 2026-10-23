"""Typed state definition for the LangGraph research analysis workflow."""

from datetime import datetime, timezone
import operator
from typing import Annotated, Any, Literal, TypedDict

AnalysisStatus = Literal["pending", "in_progress", "completed", "failed"]
NodeStatus = Literal["pending", "running", "completed", "failed", "skipped"]


def utc_now_iso() -> str:
    """Return current UTC ISO-8601 timestamp string."""
    return datetime.now(timezone.utc).isoformat()


class NodeExecutionState(TypedDict, total=False):
    """Execution audit trail item for a single node."""

    node_name: str
    status: NodeStatus
    started_at: str
    completed_at: str | None
    error: str | None
    details: dict[str, Any]


class ResearchAnalysisState(TypedDict, total=False):
    """Complete typed state passed across LangGraph nodes."""

    # Identifiers & Execution status
    analysis_id: str
    project_id: str
    status: AnalysisStatus
    current_node: str | None

    # Loaded Assets
    project_name: str | None
    project_description: str | None
    paper_ids: list[str]
    document_ids: list[str]

    # Extraction Stage
    extractions: dict[str, dict[str, Any]]  # document_id -> ScientificPaperExtraction dict
    cached_document_ids: list[str]          # Reused without duplicate LLM calls
    pending_document_ids: list[str]         # Documents requiring extraction

    # Analysis & Synthesis
    comparisons: list[dict[str, Any]]       # Cross-paper comparison items
    conflicts: list[dict[str, Any]]         # Identified contradictions / divergences
    claim_relationships: list[dict[str, Any]] # Structured scientific claim relationships
    verified_evidence: list[dict[str, Any]] # Ground-truth quotes verified on source pages
    report: dict[str, Any] | None           # Synthesized ResearchReport dict

    # Resiliency & Node Execution Tracking
    retry_counts: dict[str, int]            # node_name -> retry count
    max_retries_per_node: int               # Hard cap (default: 2)
    node_history: Annotated[list[NodeExecutionState], operator.add]
    error_message: str | None
