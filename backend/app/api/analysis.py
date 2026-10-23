"""API routes for LangGraph research workflow orchestration and graph inspection."""

from http import HTTPStatus
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.documents import get_scientific_extractor
from app.api.projects import get_repository
from app.db.repository import PaperTrailRepository
from app.schemas import (
    GraphStructureResponse,
    ResearchAnalysisRecord,
    ResearchAnalysisStartResponse,
)
from app.services.graph.workflow import get_graph_structure, run_research_workflow
from app.services.paper_extractor import ScientificPaperExtractor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.get(
    "/api/analysis/graph",
    response_model=GraphStructureResponse,
    status_code=HTTPStatus.OK,
    summary="Inspect Research Workflow Graph Structure",
    description="Returns the nodes, edges, conditional branches, and Mermaid diagram of the LangGraph workflow.",
)
async def inspect_workflow_graph() -> GraphStructureResponse:
    """Return the statically inspected structure of the PaperTrail research analysis graph."""
    return get_graph_structure()


@router.post(
    "/api/projects/{project_id}/analysis",
    response_model=ResearchAnalysisRecord,
    status_code=HTTPStatus.OK,
    summary="Start Research Project Analysis",
    description=(
        "Executes the LangGraph research analysis workflow asynchronously across all selected "
        "papers and uploaded documents in the project. Reuses cached extractions, enforces bounded "
        "retries on failure, performs comparative analysis, verifies supporting evidence, "
        "synthesizes a final research report, and persists results without creating duplicate records."
    ),
)
async def start_project_analysis(
    project_id: str,
    repository: PaperTrailRepository = Depends(get_repository),
    extractor: ScientificPaperExtractor = Depends(get_scientific_extractor),
) -> ResearchAnalysisRecord:
    """Run the LangGraph workflow for a research project asynchronously and return the resulting state."""
    if not repository.project_exists(project_id):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )

    # Run the compiled LangGraph workflow asynchronously
    final_state = await run_research_workflow(
        project_id=project_id,
        repository=repository,
        extractor=extractor,
    )

    record = repository.get_research_analysis(project_id)
    if not record:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Research analysis completed but record could not be retrieved from storage.",
        )

    return record


@router.get(
    "/api/projects/{project_id}/analysis",
    response_model=ResearchAnalysisRecord,
    status_code=HTTPStatus.OK,
    summary="Get Research Project Analysis Status and Result",
    description="Retrieves the current execution status, node audit history, and synthesized research report.",
)
async def get_project_analysis(
    project_id: str,
    repository: PaperTrailRepository = Depends(get_repository),
) -> ResearchAnalysisRecord:
    """Retrieve the stored research analysis record for a given project."""
    if not repository.project_exists(project_id):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )

    record = repository.get_research_analysis(project_id)
    if not record:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"No research analysis has been executed yet for project '{project_id}'.",
        )

    return record
