"""LangGraph workflow construction, conditional routing, and inspection for PaperTrail."""

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.db.repository import PaperTrailRepository
from app.schemas import GraphEdgeInfo, GraphNodeInfo, GraphStructureResponse
from app.services.graph.nodes import ResearchWorkflowNodes
from app.services.graph.state import ResearchAnalysisState
from app.services.paper_extractor import ScientificPaperExtractor

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Conditional Routing Functions
# -----------------------------------------------------------------------------


def route_after_validate_project(state: ResearchAnalysisState) -> str:
    """Route to record_failure if project validation failed; else load papers."""
    if state.get("status") == "failed":
        return "record_failure"
    return "load_selected_papers"


def route_after_load_selected_papers(state: ResearchAnalysisState) -> str:
    """Route to record_failure if loading failed; else check document availability."""
    if state.get("status") == "failed":
        return "record_failure"
    return "check_document_availability"


def route_after_check_document_availability(state: ResearchAnalysisState) -> str:
    """Route to extraction if pending documents exist; else skip directly to validation."""
    if state.get("status") == "failed":
        return "record_failure"
    pending = state.get("pending_document_ids", [])
    if pending:
        return "extract_missing_information"
    return "validate_extracted_results"


def route_after_extract_missing_information(state: ResearchAnalysisState) -> str:
    """Handle recoverable extraction failures with bounded retry or forward to validation."""
    if state.get("status") == "failed":
        return "record_failure"
    pending = state.get("pending_document_ids", [])
    retries = state.get("retry_counts", {}).get("extract_missing_information", 0)
    max_retries = state.get("max_retries_per_node", 2)
    if pending and retries <= max_retries:
        return "extract_missing_information"
    return "validate_extracted_results"


def route_after_validate_extracted_results(state: ResearchAnalysisState) -> str:
    """Handle extraction validation discrepancies or forward to comparison."""
    if state.get("status") == "failed":
        return "record_failure"
    pending = state.get("pending_document_ids", [])
    retries = state.get("retry_counts", {}).get("validate_extracted_results", 0)
    max_retries = state.get("max_retries_per_node", 2)
    if pending and retries <= max_retries:
        return "extract_missing_information"
    return "compare_paper_findings"


def route_after_verify_supporting_evidence(state: ResearchAnalysisState) -> str:
    """Route to failure if evidence verification failed; else proceed to report generation."""
    if state.get("status") == "failed":
        return "record_failure"
    retries = state.get("retry_counts", {}).get("verify_supporting_evidence", 0)
    max_retries = state.get("max_retries_per_node", 2)
    # If a discrepancy triggered a retry attempt and under limit, re-compare
    if retries > 0 and retries <= max_retries and state.get("current_node") == "verify_supporting_evidence":
        # If verify requested a retry pass
        discrepancies = state.get("node_history", [])[-1].get("error") if state.get("node_history") else None
        if discrepancies and "retrying" in discrepancies:
            return "compare_paper_findings"
    return "generate_report"


# -----------------------------------------------------------------------------
# Graph Assembly
# -----------------------------------------------------------------------------


def build_research_graph(
    repository: PaperTrailRepository,
    extractor: ScientificPaperExtractor,
) -> CompiledStateGraph:
    """Build and compile the LangGraph StateGraph orchestrating PaperTrail research analysis."""
    nodes = ResearchWorkflowNodes(repository=repository, extractor=extractor)
    workflow = StateGraph(ResearchAnalysisState)

    # Register Nodes
    workflow.add_node("validate_project", nodes.validate_project)
    workflow.add_node("load_selected_papers", nodes.load_selected_papers)
    workflow.add_node("check_document_availability", nodes.check_document_availability)
    workflow.add_node("extract_missing_information", nodes.extract_missing_information)
    workflow.add_node("validate_extracted_results", nodes.validate_extracted_results)
    workflow.add_node("compare_paper_findings", nodes.compare_paper_findings)
    workflow.add_node("analyze_potential_conflicts", nodes.analyze_potential_conflicts)
    workflow.add_node("verify_supporting_evidence", nodes.verify_supporting_evidence)
    workflow.add_node("generate_report", nodes.generate_report)
    workflow.add_node("persist_results", nodes.persist_results)
    workflow.add_node("record_failure", nodes.record_failure)

    # Entry edge
    workflow.add_edge(START, "validate_project")

    # Conditional Transitions
    workflow.add_conditional_edges(
        "validate_project",
        route_after_validate_project,
        {
            "load_selected_papers": "load_selected_papers",
            "record_failure": "record_failure",
        },
    )

    workflow.add_conditional_edges(
        "load_selected_papers",
        route_after_load_selected_papers,
        {
            "check_document_availability": "check_document_availability",
            "record_failure": "record_failure",
        },
    )

    workflow.add_conditional_edges(
        "check_document_availability",
        route_after_check_document_availability,
        {
            "extract_missing_information": "extract_missing_information",
            "validate_extracted_results": "validate_extracted_results",
            "record_failure": "record_failure",
        },
    )

    workflow.add_conditional_edges(
        "extract_missing_information",
        route_after_extract_missing_information,
        {
            "extract_missing_information": "extract_missing_information",
            "validate_extracted_results": "validate_extracted_results",
            "record_failure": "record_failure",
        },
    )

    workflow.add_conditional_edges(
        "validate_extracted_results",
        route_after_validate_extracted_results,
        {
            "extract_missing_information": "extract_missing_information",
            "compare_paper_findings": "compare_paper_findings",
            "record_failure": "record_failure",
        },
    )

    # Linear analysis sequence
    workflow.add_edge("compare_paper_findings", "analyze_potential_conflicts")
    workflow.add_edge("analyze_potential_conflicts", "verify_supporting_evidence")

    workflow.add_conditional_edges(
        "verify_supporting_evidence",
        route_after_verify_supporting_evidence,
        {
            "compare_paper_findings": "compare_paper_findings",
            "generate_report": "generate_report",
            "record_failure": "record_failure",
        },
    )

    workflow.add_edge("generate_report", "persist_results")
    workflow.add_edge("persist_results", END)
    workflow.add_edge("record_failure", END)

    return workflow.compile()


# -----------------------------------------------------------------------------
# Graph Inspection & Execution Helper
# -----------------------------------------------------------------------------


def get_graph_structure() -> GraphStructureResponse:
    """Return an inspected representation of the LangGraph research analysis workflow."""
    node_descriptions = {
        "validate_project": "Validates research project existence in persistent storage.",
        "load_selected_papers": "Loads papers and document records linked to the project.",
        "check_document_availability": "Checks document availability and reuses cached extractions.",
        "extract_missing_information": "Performs bounded LLM extraction on documents lacking completed results.",
        "validate_extracted_results": "Enforces scientific integrity rules on extracted representations.",
        "compare_paper_findings": "Synthesizes methodologies, datasets, sample sizes, and metrics across papers.",
        "analyze_potential_conflicts": "Analyzes potential conflicts, empirical tensions, or diverging outcomes.",
        "verify_supporting_evidence": "Verifies that comparative claims and quotes link to genuine source page text.",
        "generate_report": "Generates structured ResearchReport with executive summary and findings.",
        "persist_results": "Persists completed report and node audit history into database.",
        "record_failure": "Persists controlled failure status, error cause, and audit trail into database.",
    }

    nodes_info = [
        GraphNodeInfo(name=name, description=desc)
        for name, desc in node_descriptions.items()
    ]

    edges_info = [
        GraphEdgeInfo(source="START", target="validate_project", is_conditional=False),
        GraphEdgeInfo(source="validate_project", target="load_selected_papers", is_conditional=True, condition_description="project exists"),
        GraphEdgeInfo(source="validate_project", target="record_failure", is_conditional=True, condition_description="project missing"),
        GraphEdgeInfo(source="load_selected_papers", target="check_document_availability", is_conditional=True, condition_description="papers/docs found"),
        GraphEdgeInfo(source="load_selected_papers", target="record_failure", is_conditional=True, condition_description="no papers/docs"),
        GraphEdgeInfo(source="check_document_availability", target="extract_missing_information", is_conditional=True, condition_description="pending extractions"),
        GraphEdgeInfo(source="check_document_availability", target="validate_extracted_results", is_conditional=True, condition_description="all cached"),
        GraphEdgeInfo(source="check_document_availability", target="record_failure", is_conditional=True, condition_description="no extractable docs"),
        GraphEdgeInfo(source="extract_missing_information", target="extract_missing_information", is_conditional=True, condition_description="retry on recoverable error"),
        GraphEdgeInfo(source="extract_missing_information", target="validate_extracted_results", is_conditional=True, condition_description="extraction succeeded"),
        GraphEdgeInfo(source="extract_missing_information", target="record_failure", is_conditional=True, condition_description="retries exhausted"),
        GraphEdgeInfo(source="validate_extracted_results", target="compare_paper_findings", is_conditional=True, condition_description="extractions valid"),
        GraphEdgeInfo(source="validate_extracted_results", target="extract_missing_information", is_conditional=True, condition_description="retry invalid extraction"),
        GraphEdgeInfo(source="validate_extracted_results", target="record_failure", is_conditional=True, condition_description="validation failed"),
        GraphEdgeInfo(source="compare_paper_findings", target="analyze_potential_conflicts", is_conditional=False),
        GraphEdgeInfo(source="analyze_potential_conflicts", target="verify_supporting_evidence", is_conditional=False),
        GraphEdgeInfo(source="verify_supporting_evidence", target="generate_report", is_conditional=True, condition_description="evidence verified"),
        GraphEdgeInfo(source="verify_supporting_evidence", target="compare_paper_findings", is_conditional=True, condition_description="retry comparison"),
        GraphEdgeInfo(source="verify_supporting_evidence", target="record_failure", is_conditional=True, condition_description="evidence unverified"),
        GraphEdgeInfo(source="generate_report", target="persist_results", is_conditional=False),
        GraphEdgeInfo(source="persist_results", target="END", is_conditional=False),
        GraphEdgeInfo(source="record_failure", target="END", is_conditional=False),
    ]

    mermaid = (
        "graph TD\n"
        "  START --> validate_project\n"
        "  validate_project -->|Valid| load_selected_papers\n"
        "  validate_project -->|Missing| record_failure\n"
        "  load_selected_papers -->|Found| check_document_availability\n"
        "  load_selected_papers -->|Empty| record_failure\n"
        "  check_document_availability -->|Extract Needed| extract_missing_information\n"
        "  check_document_availability -->|All Cached| validate_extracted_results\n"
        "  check_document_availability -->|No Docs| record_failure\n"
        "  extract_missing_information -->|Retry| extract_missing_information\n"
        "  extract_missing_information -->|Done| validate_extracted_results\n"
        "  extract_missing_information -->|Exhausted| record_failure\n"
        "  validate_extracted_results -->|Valid| compare_paper_findings\n"
        "  validate_extracted_results -->|Retry| extract_missing_information\n"
        "  validate_extracted_results -->|Invalid| record_failure\n"
        "  compare_paper_findings --> analyze_potential_conflicts\n"
        "  analyze_potential_conflicts --> verify_supporting_evidence\n"
        "  verify_supporting_evidence -->|Verified| generate_report\n"
        "  verify_supporting_evidence -->|Retry| compare_paper_findings\n"
        "  verify_supporting_evidence -->|Failed| record_failure\n"
        "  generate_report --> persist_results\n"
        "  persist_results --> END\n"
        "  record_failure --> END"
    )

    return GraphStructureResponse(
        workflow_name="PaperTrail Research Analysis Workflow",
        nodes=nodes_info,
        edges=edges_info,
        mermaid_diagram=mermaid,
    )


async def run_research_workflow(
    project_id: str,
    repository: PaperTrailRepository,
    extractor: ScientificPaperExtractor,
    *,
    max_retries_per_node: int = 2,
) -> dict[str, Any]:
    """Execute the compiled LangGraph research workflow asynchronously."""
    graph = build_research_graph(repository=repository, extractor=extractor)
    initial_state: ResearchAnalysisState = {
        "analysis_id": f"analysis_{project_id}",
        "project_id": project_id,
        "status": "pending",
        "current_node": None,
        "project_name": None,
        "project_description": None,
        "paper_ids": [],
        "document_ids": [],
        "extractions": {},
        "cached_document_ids": [],
        "pending_document_ids": [],
        "comparisons": [],
        "conflicts": [],
        "verified_evidence": [],
        "report": None,
        "retry_counts": {},
        "max_retries_per_node": max_retries_per_node,
        "node_history": [],
        "error_message": None,
    }

    final_state = await graph.ainvoke(initial_state)
    return dict(final_state)
