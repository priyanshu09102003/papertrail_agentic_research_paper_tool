"""Tests for SQLite persistence, migrations, projects CRUD, DOI deduplication, and cleanup rules."""

from pathlib import Path

import fitz  # PyMuPDF
from fastapi.testclient import TestClient

from app.config import SQLITE_DB_PATH
from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.main import app

client = TestClient(app)


def _create_sample_pdf_bytes(text: str) -> bytes:
    """Generate a valid in-memory PDF for testing."""
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(72, 72, 520, 720), text, fontsize=12)
        return doc.tobytes()
    finally:
        doc.close()


def test_non_destructive_migrations_preserve_existing_data(tmp_path: Path) -> None:
    """Verify running initialize_and_migrate() repeatedly is idempotent and non-destructive."""
    db_file = tmp_path / "migration_test.db"
    storage_dir = tmp_path / "uploads"
    db = DatabaseManager(db_path=db_file)

    first_applied = db.initialize_and_migrate()
    assert "001_initial_schema" in first_applied

    repo = PaperTrailRepository(db=db, storage_dir=storage_dir)
    created = repo.create_project(name="Persistent Project", description="Should survive re-init")

    # Re-run migrations as would happen on subsequent server startups
    second_applied = db.initialize_and_migrate()
    assert second_applied == []

    fetched = repo.get_project(created.id)
    assert fetched is not None
    assert fetched.name == "Persistent Project"


def test_project_crud_and_paper_doi_deduplication(
    isolated_test_repository: PaperTrailRepository,
) -> None:
    """Verify creating, listing, retrievingprojects and associating DOI-deduplicated papers."""
    # 1. Create a research project
    create_res = client.post(
        "/api/projects",
        json={
            "name": "Transformer Literature Review",
            "description": "Investigating attention mechanisms.",
        },
    )
    assert create_res.status_code == 201
    project = create_res.json()
    project_id = project["id"]
    assert project_id.startswith("proj_")
    assert project["name"] == "Transformer Literature Review"

    # 2. List projects
    list_res = client.get("/api/projects")
    assert list_res.status_code == 200
    assert any(p["id"] == project_id for p in list_res.json())

    # 3. Associate a paper with an unnormalized DOI URL
    paper_payload_1 = {
        "id": "openalex:W2741809807",
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani"],
        "publication_year": 2017,
        "doi": "https://doi.org/10.48550/ARXIV.1706.03762",
        "abstract": None,
        "source": "openalex",
        "landing_page_url": "https://arxiv.org/abs/1706.03762",
        "open_access_pdf_url": None,
    }
    add_res_1 = client.post(f"/api/projects/{project_id}/papers", json=paper_payload_1)
    assert add_res_1.status_code == 200
    saved_paper_1 = add_res_1.json()
    assert saved_paper_1["doi"] == "10.48550/arxiv.1706.03762"
    assert saved_paper_1["id"] == "doi:10.48550/arxiv.1706.03762"

    # 4. Associate duplicate paper with lowercase DOI and complementary abstract/PDF metadata
    paper_payload_2 = {
        "id": "crossref:10.48550/arxiv.1706.03762",
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "publication_year": 2017,
        "doi": "10.48550/arxiv.1706.03762",
        "abstract": "The dominant sequence transduction models are based on complex recurrent networks.",
        "source": "crossref",
        "landing_page_url": "https://arxiv.org/abs/1706.03762",
        "open_access_pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
    }
    add_res_2 = client.post(f"/api/projects/{project_id}/papers", json=paper_payload_2)
    assert add_res_2.status_code == 200
    merged_paper = add_res_2.json()
    assert merged_paper["id"] == "doi:10.48550/arxiv.1706.03762"
    assert merged_paper["abstract"] == (
        "The dominant sequence transduction models are based on complex recurrent networks."
    )
    assert merged_paper["open_access_pdf_url"] == "https://arxiv.org/pdf/1706.03762.pdf"

    # 5. Retrieve project details and confirm only 1 deduplicated paper is linked
    detail_res = client.get(f"/api/projects/{project_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["papers"]) == 1
    assert detail["papers"][0]["doi"] == "10.48550/arxiv.1706.03762"


def test_project_document_persistence_and_deletion_cleanup_rules(
    isolated_test_repository: PaperTrailRepository,
) -> None:
    """Verify PDF files are stored in managed storage (not SQLite) and cleaned up on project delete."""
    create_res = client.post(
        "/api/projects",
        json={"name": "Cleanup Test Project", "description": "Testing file and DB cleanup."},
    )
    assert create_res.status_code == 201
    project_id = create_res.json()["id"]

    pdf_bytes = _create_sample_pdf_bytes(
        "This research paper tests SQLite document metadata persistence, managed disk storage, "
        "and deterministic cleanup when the parent research project is deleted."
    )

    upload_res = client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("study.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 200
    doc_data = upload_res.json()
    document_id = doc_data["document_id"]
    stored_rel_path = doc_data["stored_path"]

    assert doc_data["project_id"] == project_id
    assert doc_data["extraction_status"] == "completed"
    assert stored_rel_path.endswith("_study.pdf")

    # Verify the physical PDF exists inside the dedicated managed storage directory
    physical_file = isolated_test_repository.storage_dir / stored_rel_path
    assert physical_file.exists()
    assert physical_file.read_bytes() == pdf_bytes

    # Verify no binary PDF column exists in the SQLite `documents` table
    with isolated_test_repository._db.connect() as conn:
        col_rows = conn.execute("PRAGMA table_info(documents);").fetchall()
        col_names = {row["name"] for row in col_rows}
        assert "file_bytes" not in col_names
        assert "pdf_blob" not in col_names

    # Delete the project and verify cleanup rules
    del_res = client.delete(f"/api/projects/{project_id}")
    assert del_res.status_code == 200
    del_body = del_res.json()
    assert del_body["deleted_project_id"] == project_id
    assert del_body["removed_files_count"] == 1
    assert del_body["status"] == "deleted"

    # Project, document metadata, and managed PDF file should all be removed
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.get(f"/api/documents/{document_id}").status_code == 404
    assert not physical_file.exists()

    # Ensure real user SQLite path was not modified by tests
    assert isolated_test_repository._db.db_path != SQLITE_DB_PATH
