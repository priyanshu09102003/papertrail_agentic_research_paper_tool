"""Tests for the interactive claim-to-evidence graph transformation, validation, and API routes."""

import pytest
from fastapi.testclient import TestClient

from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.main import app
from app.schemas import (
    ClaimRelationship,
    ExtractedClaim,
    ExtractedDocument,
    ExtractedPage,
    QuantitativeResult,
    ScientificPaperExtraction,
    SupportingPassage,
)
from app.services.claim_graph import ClaimGraphService


@pytest.fixture
def test_repo(tmp_path):
    db_file = tmp_path / "test_graph.db"
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    db = DatabaseManager(db_path=db_file)
    return PaperTrailRepository(db=db, storage_dir=storage_dir)


def test_empty_project_graph(test_repo):
    """Empty or non-existent project returns an empty graph safely without errors."""
    service = ClaimGraphService(repository=test_repo)

    # 1. Non-existent project
    resp_none = service.build_claim_graph("non_existent_project")
    assert resp_none.is_empty is True
    assert len(resp_none.nodes) == 0
    assert len(resp_none.edges) == 0

    # 2. Existing empty project
    proj = test_repo.create_project(name="Empty Project")
    resp_empty = service.build_claim_graph(proj.id)
    assert resp_empty.is_empty is True
    assert len(resp_empty.nodes) == 0
    assert len(resp_empty.edges) == 0
    assert "No analyzed research papers" in (resp_empty.message or "")


def test_claim_graph_transformation_and_distinct_node_types(test_repo):
    """Verifies that papers, claims, evidence, datasets, methods, and metrics are transformed into distinct node types."""
    proj = test_repo.create_project(name="Quantum NLP")

    doc = ExtractedDocument(
        document_id="doc_nlp_01",
        project_id=proj.id,
        filename="attention_paper.pdf",
        file_size_bytes=1024,
        page_count=5,
        total_characters=5000,
        total_words=800,
        extraction_status="completed",
        pages=[ExtractedPage(page_number=1, text="Sample text", character_count=11, word_count=2)],
    )
    saved_doc = test_repo.save_document_and_file(doc, b"%PDF-1.4 minimal binary header", project_id=proj.id)

    extraction = ScientificPaperExtraction(
        extraction_id=f"ext_{saved_doc.document_id}",
        document_id=saved_doc.document_id,
        paper_title="Attention Is All You Need",
        research_methodology="Self-attention Transformer architecture without recurrence",
        dataset_or_material=["WMT 2014 English-German", "WMT 2014 English-French"],
        evaluation_metrics=["BLEU score"],
        quantitative_results=[
            QuantitativeResult(metric_name="BLEU score", value="28.4", unit="BLEU", supporting_quote="28.4 BLEU", page_number=2)
        ],
        main_findings=[
            ExtractedClaim(author_claim="Self-attention enables massive parallelization and state-of-the-art BLEU.")
        ],
        supporting_passages=[
            SupportingPassage(
                document_id=saved_doc.document_id,
                page_number=2,
                field_supported="main_findings",
                quote="The Transformer allows for significantly more parallelization and reaches a new state of the art.",
            )
        ],
        extraction_status="completed",
        created_at="2026-10-23T00:00:00Z",
        updated_at="2026-10-23T00:00:00Z",
    )
    test_repo.save_scientific_extraction(extraction)

    service = ClaimGraphService(repository=test_repo)
    graph = service.build_claim_graph(proj.id)

    assert graph.is_empty is False
    assert len(graph.nodes) > 0

    node_types = {n.type for n in graph.nodes}
    assert "paper" in node_types
    assert "claim" in node_types
    assert "evidence" in node_types
    assert "dataset" in node_types
    assert "method" in node_types
    assert "metric" in node_types

    # Node attributes check
    paper_node = next(n for n in graph.nodes if n.type == "paper")
    assert paper_node.title == "Attention Is All You Need"
    assert paper_node.pdf_url == f"/api/documents/{saved_doc.document_id}/file"

    evidence_node = next(n for n in graph.nodes if n.type == "evidence")
    assert evidence_node.page_number == 2
    assert "parallelization" in (evidence_node.quote or "")
    assert evidence_node.pdf_url == f"/api/documents/{saved_doc.document_id}/file#page=2"

    # Edge checks
    edge_types = {e.relationship_type for e in graph.edges}
    assert "reports" in edge_types
    assert "supported_by" in edge_types
    assert "uses_dataset" in edge_types
    assert "depends_on" in edge_types
    assert "evaluated_using" in edge_types

    # Ensure no duplicates
    node_ids = [n.id for n in graph.nodes]
    assert len(node_ids) == len(set(node_ids)), "Duplicate node IDs detected in claim graph!"
    edge_keys = [(e.source, e.relationship_type, e.target) for e in graph.edges]
    assert len(edge_keys) == len(set(edge_keys)), "Duplicate edges detected in claim graph!"


def test_contradiction_vs_supporting_evidence_distinction(test_repo):
    """Ensures potential contradictions are clearly distinguished from supporting evidence."""
    proj = test_repo.create_project(name="Sparse Attention Contradiction Suite")

    saved_doc_ids = []
    for i, title, claim in [
        ("p1", "Fast Sparse Paper", "Sparse attention reduces compute with zero loss."),
        ("p2", "Evaluating Sparse Paper", "Sparse attention causes severe degradation in quality."),
    ]:
        doc = ExtractedDocument(
            document_id=f"doc_{i}",
            project_id=proj.id,
            filename=f"{i}.pdf",
            file_size_bytes=500,
            page_count=2,
            total_characters=200,
            total_words=30,
            extraction_status="completed",
            pages=[ExtractedPage(page_number=1, text="Text", character_count=4, word_count=1)],
        )
        saved_d = test_repo.save_document_and_file(doc, f"%PDF-1.4 minimal paper {i}".encode(), project_id=proj.id)
        saved_doc_ids.append(saved_d.document_id)
        ext = ScientificPaperExtraction(
            extraction_id=f"ext_{saved_d.document_id}",
            document_id=saved_d.document_id,
            paper_title=title,
            research_methodology="Transformer with sparse block attention",
            dataset_or_material=["WMT 2014 En-De"],
            evaluation_metrics=["BLEU score"],
            main_findings=[ExtractedClaim(author_claim=claim)],
            supporting_passages=[
                SupportingPassage(document_id=saved_d.document_id, page_number=1, field_supported="main_findings", quote=f"Quote from {title}")
            ],
            extraction_status="completed",
            created_at="2026-10-23T00:00:00Z",
            updated_at="2026-10-23T00:00:00Z",
        )
        test_repo.save_scientific_extraction(ext)

    # Persist a verified potential contradiction relationship
    contra_rel = ClaimRelationship(
        relationship_id="rel_contra_test",
        claim_ids=[f"claim_{saved_doc_ids[0]}", f"claim_{saved_doc_ids[1]}"],
        source_paper_ids=saved_doc_ids,
        paper_titles=["Fast Sparse Paper", "Evaluating Sparse Paper"],
        source_passages=[],
        research_question_compatibility="compatible",
        dataset_or_population_compatibility="compatible",
        methodology_compatibility="compatible",
        metric_compatibility="compatible",
        relationship_label="potential_contradiction",
        supporting_rationale="Under comparable conditions, the papers report opposing qualitative outcomes.",
        verification_status="verified",
    )
    test_repo.save_claim_relationships(proj.id, [contra_rel])

    service = ClaimGraphService(repository=test_repo)
    graph = service.build_claim_graph(proj.id)

    # Check distinction between contradiction and supporting evidence
    contra_edges = [e for e in graph.edges if e.is_contradiction]
    assert len(contra_edges) == 1
    c_edge = contra_edges[0]
    assert c_edge.relationship_type == "potential_contradiction"
    assert c_edge.label == "potentially contradicts"
    assert c_edge.verification_status == "verified"

    # Supporting evidence edge must have is_contradiction = False
    support_edges = [e for e in graph.edges if e.relationship_type == "supported_by"]
    assert len(support_edges) >= 2
    for s_edge in support_edges:
        assert s_edge.is_contradiction is False
        assert s_edge.label == "supported by"


def test_claim_graph_api_endpoint(test_repo):
    """Tests the FastAPI GET /api/projects/{project_id}/claim-graph endpoint."""
    proj = test_repo.create_project(name="API Graph Test")
    client = TestClient(app)

    # Override repository dependency for API tests
    from app.api.projects import get_repository
    app.dependency_overrides[get_repository] = lambda: test_repo

    try:
        # Non-existent project -> 404
        r_not_found = client.get("/api/projects/unknown_id/claim-graph")
        assert r_not_found.status_code == 404

        # Existing empty project -> 200 with empty graph
        r_empty = client.get(f"/api/projects/{proj.id}/claim-graph")
        assert r_empty.status_code == 200
        data = r_empty.json()
        assert data["project_id"] == proj.id
        assert data["is_empty"] is True
        assert data["nodes"] == []
        assert data["edges"] == []
    finally:
        app.dependency_overrides.pop(get_repository, None)


def test_pdf_file_streaming_endpoint(test_repo):
    """Tests the GET /api/documents/{document_id}/file endpoint."""
    proj = test_repo.create_project(name="PDF Stream Test")
    doc = ExtractedDocument(
        document_id="doc_stream_01",
        project_id=proj.id,
        filename="test_paper.pdf",
        file_size_bytes=24,
        page_count=1,
        total_characters=10,
        total_words=2,
        extraction_status="completed",
        pages=[ExtractedPage(page_number=1, text="Test", character_count=4, word_count=1)],
    )
    pdf_bytes = b"%PDF-1.4\n%test pdf stream"
    saved_doc = test_repo.save_document_and_file(doc, pdf_bytes, project_id=proj.id)

    client = TestClient(app)
    from app.api.projects import get_repository
    app.dependency_overrides[get_repository] = lambda: test_repo

    try:
        resp = client.get(f"/api/documents/{saved_doc.document_id}/file")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == pdf_bytes
    finally:
        app.dependency_overrides.pop(get_repository, None)
