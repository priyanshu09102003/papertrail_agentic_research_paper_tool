"""Tests for LangGraph research analysis workflow orchestration, retry bounding, and API endpoints."""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.llm.base import BaseLLMProvider
from app.main import app
from app.schemas import (
    ExtractedClaim,
    ExtractedDocument,
    ExtractedPage,
    LLMStatusResponse,
    QuantitativeResult,
    ScientificPaperExtraction,
    SupportingPassage,
)
from app.services.graph.workflow import build_research_graph, get_graph_structure, run_research_workflow
from app.services.paper_extractor import ScientificPaperExtractor


class MockGraphLLMProvider(BaseLLMProvider):
    """Mock provider for graph extraction tests."""

    def __init__(self, response_map: dict[str, Any] | None = None) -> None:
        super().__init__(provider_name="mock_graph_llm", model_name="mock-model")
        self.response_map = response_map or {}
        self.call_count = 0

    async def check_health(self) -> LLMStatusResponse:
        return LLMStatusResponse(
            provider=self.provider_name,
            model=self.model_name,
            service_reachable=True,
            model_available=True,
            status="ready",
            message="Mock LLM ready.",
        )

    async def _raw_generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        self.call_count += 1
        return json.dumps(self.response_map)


@pytest.fixture
def temp_repo(tmp_path: Path) -> PaperTrailRepository:
    db = DatabaseManager(db_path=tmp_path / "test_papertrail.db")
    return PaperTrailRepository(db=db, storage_dir=tmp_path / "uploads")


def _make_sample_doc(
    doc_id: str, title: str, text: str, page_num: int = 1, project_id: str = "test_proj"
) -> ExtractedDocument:
    return ExtractedDocument(
        document_id=doc_id,
        project_id=project_id,
        filename=f"{doc_id}.pdf",
        stored_path=f"{doc_id}.pdf",
        file_size_bytes=len(text) * 2,
        page_count=1,
        total_characters=len(text),
        total_words=len(text.split()),
        extraction_status="completed",
        pages=[
            ExtractedPage(
                page_number=page_num,
                text=text,
                character_count=len(text),
                word_count=len(text.split()),
            )
        ],
    )


def test_graph_structure_inspection() -> None:
    """Requirement 15: Verify static graph structure, node inventory, and mermaid diagram."""
    structure = get_graph_structure()
    node_names = {n.name for n in structure.nodes}
    assert "validate_project" in node_names
    assert "load_selected_papers" in node_names
    assert "check_document_availability" in node_names
    assert "extract_missing_information" in node_names
    assert "validate_extracted_results" in node_names
    assert "compare_paper_findings" in node_names
    assert "analyze_potential_conflicts" in node_names
    assert "verify_supporting_evidence" in node_names
    assert "generate_report" in node_names
    assert "persist_results" in node_names
    assert "record_failure" in node_names
    assert "graph TD" in structure.mermaid_diagram


@pytest.mark.anyio
async def test_successful_research_analysis_workflow_end_to_end(
    temp_repo: PaperTrailRepository,
) -> None:
    """Requirements 2, 3, 7, 8, 9, 20: Test end-to-end success with cached extraction reuse."""
    project = temp_repo.create_project(name="NLP Attention Study")
    p_id = project.id

    # Create two documents
    doc1 = _make_sample_doc(
        "doc_attention",
        "Attention Paper",
        "Page 1 text. We propose the Transformer model using self-attention. BLEU score of 28.4 on WMT 2014.",
        project_id=p_id,
    )
    doc2 = _make_sample_doc(
        "doc_convs2s",
        "ConvS2S Paper",
        "Page 1 text. Convolutional sequence to sequence learning achieves BLEU score of 25.16.",
        project_id=p_id,
    )
    saved_doc1 = temp_repo.save_document_and_file(doc1, b"%PDF-doc1")
    saved_doc2 = temp_repo.save_document_and_file(doc2, b"%PDF-doc2")

    # Associate doc1 with a pre-cached extraction (Requirement 9: reuse existing extraction)
    cached_extraction = ScientificPaperExtraction(
        extraction_id=f"ext_{saved_doc1.document_id}",
        document_id=saved_doc1.document_id,
        paper_title="Attention Is All You Need",
        research_methodology="Self-attention mechanism",
        dataset_or_material=["WMT 2014 English-German"],
        sample_size="4.5M pairs",
        model_architecture_or_intervention="Transformer",
        evaluation_metrics=["BLEU score"],
        quantitative_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="28.4",
                supporting_quote="BLEU score of 28.4",
                page_number=1,
            )
        ],
        supporting_passages=[
            SupportingPassage(
                document_id=saved_doc1.document_id,
                page_number=1,
                field_supported="methodology",
                quote="Transformer model using self-attention",
            ),
            SupportingPassage(
                document_id=saved_doc1.document_id,
                page_number=1,
                field_supported="quantitative_results",
                quote="BLEU score of 28.4",
            ),
        ],
        page_numbers=[1],
        extraction_status="completed",
        chunk_count=1,
        failed_chunks=0,
        warnings=[],
        created_at="2026-10-23T00:00:00Z",
        updated_at="2026-10-23T00:00:00Z",
    )
    temp_repo.save_scientific_extraction(cached_extraction)

    # doc2 will be extracted by mock LLM
    mock_llm = MockGraphLLMProvider(
        response_map={
            "paper_title": "Convolutional Sequence to Sequence Learning",
            "research_methodology": "Convolutional sequence network",
            "dataset_or_material": ["WMT 2014"],
            "model_architecture_or_intervention": "ConvS2S",
            "evaluation_metrics": ["BLEU score"],
            "quantitative_results": [
                {
                    "metric_name": "BLEU score",
                    "value": "25.16",
                    "supporting_quote": "BLEU score of 25.16",
                    "page_number": 1,
                }
            ],
            "supporting_passages": [
                {
                    "field_supported": "methodology",
                    "quote": "Convolutional sequence to sequence learning",
                    "page_number": 1,
                },
                {
                    "field_supported": "quantitative_results",
                    "quote": "BLEU score of 25.16",
                    "page_number": 1,
                },
            ],
        }
    )
    extractor = ScientificPaperExtractor(llm_provider=mock_llm)

    final_state = await run_research_workflow(
        project_id=p_id,
        repository=temp_repo,
        extractor=extractor,
    )

    assert final_state["status"] == "completed"
    assert saved_doc1.document_id in final_state["cached_document_ids"]
    assert saved_doc2.document_id not in final_state["cached_document_ids"]

    # Verify report generated
    report = final_state["report"]
    assert report is not None
    assert report["paper_count"] == 2
    assert len(report["comparisons"]) >= 2

    # Verify database persistence
    saved_analysis = temp_repo.get_research_analysis(p_id)
    assert saved_analysis is not None
    assert saved_analysis.status == "completed"
    assert saved_analysis.report is not None
    assert saved_analysis.report.paper_count == 2
    assert len(saved_analysis.node_history) >= 10


@pytest.mark.anyio
async def test_extraction_failure_and_retry_exhaustion(
    temp_repo: PaperTrailRepository,
) -> None:
    """Requirements 4, 5, 6, 14: Bounded retries exhaust and transition to controlled failure."""
    project = temp_repo.create_project(name="Faulty Extraction Study")
    p_id = project.id

    doc = _make_sample_doc("doc_broken", "Broken Paper", "Corrupted text without details.", project_id=p_id)
    temp_repo.save_document_and_file(doc, b"%PDF-broken")

    # Mock provider that returns invalid empty JSON causing extraction failures
    mock_llm = MockGraphLLMProvider(response_map={})
    extractor = ScientificPaperExtractor(llm_provider=mock_llm)

    final_state = await run_research_workflow(
        project_id=p_id,
        repository=temp_repo,
        extractor=extractor,
        max_retries_per_node=1,
    )

    assert final_state["status"] == "failed"
    assert final_state["error_message"] is not None
    assert "retry budget exhausted" in final_state["error_message"].lower()

    # Ensure recorded in DB as failed
    saved = temp_repo.get_research_analysis(p_id)
    assert saved is not None
    assert saved.status == "failed"
    assert saved.error_message is not None


@pytest.mark.anyio
async def test_verification_failure_discrepancy(
    temp_repo: PaperTrailRepository,
) -> None:
    """Requirements 4, 14: Discovering unverified quote discrepancy exhausts retries and records failure."""
    project = temp_repo.create_project(name="Hallucinated Evidence Study")
    p_id = project.id

    doc = _make_sample_doc(
        "doc_real",
        "Real Paper",
        "Genuine text about neural models and architectures.",
        project_id=p_id,
    )
    saved_doc = temp_repo.save_document_and_file(doc, b"%PDF-real")

    # Injection of an extraction with a quote not present on page
    bad_extraction = ScientificPaperExtraction(
        extraction_id=f"ext_{saved_doc.document_id}",
        document_id=saved_doc.document_id,
        paper_title="Real Paper Title",
        research_methodology="Neural model",
        supporting_passages=[
            SupportingPassage(
                document_id=saved_doc.document_id,
                page_number=1,
                field_supported="methodology",
                quote="This quote never exists anywhere in the real paper text",
            )
        ],
        page_numbers=[1],
        extraction_status="completed",
        chunk_count=1,
        failed_chunks=0,
        warnings=[],
        created_at="2026-10-23T00:00:00Z",
        updated_at="2026-10-23T00:00:00Z",
    )
    temp_repo.save_scientific_extraction(bad_extraction)

    mock_llm = MockGraphLLMProvider(response_map={})
    extractor = ScientificPaperExtractor(llm_provider=mock_llm)

    final_state = await run_research_workflow(
        project_id=p_id,
        repository=temp_repo,
        extractor=extractor,
        max_retries_per_node=1,
    )

    assert final_state["status"] == "failed"
    assert "evidence verification failed" in final_state["error_message"].lower()


@pytest.mark.anyio
async def test_rerunning_analysis_does_not_create_duplicates(
    temp_repo: PaperTrailRepository,
) -> None:
    """Requirement 10: Rerunning an analysis updates existing record without duplicates."""
    project = temp_repo.create_project(name="Idempotent Project")
    p_id = project.id

    doc = _make_sample_doc("doc_idempotent", "Idempotent Paper", "Text sample for idempotent test.", project_id=p_id)
    saved_doc = temp_repo.save_document_and_file(doc, b"%PDF-idempotent")

    extraction = ScientificPaperExtraction(
        extraction_id=f"ext_{saved_doc.document_id}",
        document_id=saved_doc.document_id,
        paper_title="Idempotent Paper",
        research_methodology="Test methodology",
        extraction_status="completed",
        chunk_count=1,
        failed_chunks=0,
        warnings=[],
        created_at="2026-10-23T00:00:00Z",
        updated_at="2026-10-23T00:00:00Z",
    )
    temp_repo.save_scientific_extraction(extraction)

    extractor = ScientificPaperExtractor(llm_provider=MockGraphLLMProvider({}))

    # First run
    await run_research_workflow(project_id=p_id, repository=temp_repo, extractor=extractor)
    count_1 = temp_repo.count_research_analyses(p_id)
    assert count_1 == 1

    # Second run (rerun)
    await run_research_workflow(project_id=p_id, repository=temp_repo, extractor=extractor)
    count_2 = temp_repo.count_research_analyses(p_id)
    assert count_2 == 1


def test_api_endpoints_start_and_get_analysis(temp_repo: PaperTrailRepository) -> None:
    """Requirements 16, 17: Test POST /api/projects/{id}/analysis and GET /api/projects/{id}/analysis."""
    from app.api.projects import get_repository

    app.dependency_overrides[get_repository] = lambda: temp_repo
    client = TestClient(app)

    try:
        # 1. Test GET /api/analysis/graph
        resp_graph = client.get("/api/analysis/graph")
        assert resp_graph.status_code == 200
        data_graph = resp_graph.json()
        assert "nodes" in data_graph
        assert "edges" in data_graph

        # 2. Test 404 on non-existent project
        resp_404 = client.get("/api/projects/proj_nonexistent/analysis")
        assert resp_404.status_code == 404

        # 3. Create project with document & run analysis via API
        project = temp_repo.create_project(name="API Test Project")
        doc = _make_sample_doc("doc_api", "API Paper", "API test document text with verified content.", project_id=project.id)
        saved_doc = temp_repo.save_document_and_file(doc, b"%PDF-api")

        extraction = ScientificPaperExtraction(
            extraction_id=f"ext_{saved_doc.document_id}",
            document_id=saved_doc.document_id,
            paper_title="API Paper",
            research_methodology="API extraction method",
            extraction_status="completed",
            chunk_count=1,
            failed_chunks=0,
            warnings=[],
            created_at="2026-10-23T00:00:00Z",
            updated_at="2026-10-23T00:00:00Z",
        )
        temp_repo.save_scientific_extraction(extraction)

        resp_post = client.post(f"/api/projects/{project.id}/analysis")
        assert resp_post.status_code == 200
        data_post = resp_post.json()
        assert data_post["status"] == "completed"
        assert data_post["project_id"] == project.id
        assert data_post["report"] is not None

        # 4. GET status
        resp_get = client.get(f"/api/projects/{project.id}/analysis")
        assert resp_get.status_code == 200
        data_get = resp_get.json()
        assert data_get["status"] == "completed"
        assert data_get["analysis_id"] == f"analysis_{project.id}"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_papers_only_project_materializes_documents(
    temp_repo: PaperTrailRepository,
) -> None:
    """Verify projects with only discovered papers (0 uploaded PDFs) materialize documents and succeed."""
    from app.schemas import Paper
    from app.services.graph.nodes import ResearchWorkflowNodes

    project = temp_repo.create_project(name="Papers Only Project")
    paper1 = Paper(
        id="https://openalex.org/W111111",
        title="Vision Transformer for Potato Blight",
        authors=["Alice Smith"],
        publication_year=2023,
        doi="10.1000/182",
        abstract="We demonstrate ViT achieves 96.5% accuracy on potato late blight detection.",
        source="openalex",
    )
    persisted = temp_repo.associate_paper_with_project(project.id, paper1)
    assert persisted is not None

    extractor = ScientificPaperExtractor(llm_provider=MockGraphLLMProvider())
    nodes = ResearchWorkflowNodes(repository=temp_repo, extractor=extractor)
    state = {
        "project_id": project.id,
        "status": "pending",
        "current_node": "",
        "retry_counts": {},
        "node_history": [],
        "document_ids": [],
    }

    res_load = await nodes.load_selected_papers(state)  # type: ignore[arg-type]
    assert res_load["status"] == "in_progress"
    assert len(res_load["document_ids"]) == 1

    doc_id = res_load["document_ids"][0]
    doc = temp_repo.get_document(doc_id)
    assert doc is not None
    assert doc.paper_id == persisted.id
    assert "96.5% accuracy" in doc.pages[0].text
