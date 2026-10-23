"""Repository layer for persistent research projects, papers, and document metadata."""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import uuid

from app.config import MANAGED_STORAGE_DIR
from app.db.database import DatabaseManager
from app.schemas import (
    ClaimRelationship,
    DocumentMetadata,
    ExtractedDocument,
    ExtractedPage,
    Paper,
    ProjectDeleteResponse,
    ProjectDetailResponse,
    ProjectResponse,
    ResearchAnalysisRecord,
    ResearchReport,
    ScientificPaperExtraction,
)
from app.services.normalization import build_paper_id, normalize_doi
from app.services.pdf_ingestion import sanitize_pdf_filename

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class PaperTrailRepository:
    """Maintainable data access layer for SQLite tables and application-managed file storage."""

    def __init__(
        self,
        db: DatabaseManager,
        storage_dir: Path = MANAGED_STORAGE_DIR,
    ) -> None:
        self._db = db
        self._storage_dir = Path(storage_dir).resolve()
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._db.initialize_and_migrate()

    @property
    def storage_dir(self) -> Path:
        """Return the resolved application-managed file storage directory."""
        return self._storage_dir

    # -------------------------------------------------------------------------
    # Research Projects
    # -------------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str | None = None,
    ) -> ProjectResponse:
        """Create and persist a new research project with a stable internal ID."""
        project_id = f"proj_{uuid.uuid4().hex[:16]}"
        cleaned_name = name.strip()
        cleaned_desc = description.strip() if isinstance(description, str) and description.strip() else None
        now_iso = _utc_now_iso()

        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (project_id, cleaned_name, cleaned_desc, now_iso, now_iso),
            )

        return ProjectResponse(
            id=project_id,
            name=cleaned_name,
            description=cleaned_desc,
            created_at=now_iso,
            updated_at=now_iso,
        )

    def list_projects(self) -> list[ProjectResponse]:
        """List all persisted research projects ordered by newest first."""
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, description, created_at, updated_at
                FROM projects
                ORDER BY created_at DESC, id ASC;
                """
            ).fetchall()

        return [self._row_to_project(row) for row in rows]

    def project_exists(self, project_id: str) -> bool:
        """Return True if a project with the given ID exists."""
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM projects WHERE id = ?;",
                (project_id,),
            ).fetchone()
        return row is not None

    def get_project(self, project_id: str) -> ProjectDetailResponse | None:
        """Retrieve a project along with its associated papers and document metadata."""
        with self._db.connect() as conn:
            project_row = conn.execute(
                """
                SELECT id, name, description, created_at, updated_at
                FROM projects
                WHERE id = ?;
                """,
                (project_id,),
            ).fetchone()
            if project_row is None:
                return None

            paper_rows = conn.execute(
                """
                SELECT p.id, p.title, p.authors_json, p.publication_year, p.doi,
                       p.abstract, p.source, p.landing_page_url, p.open_access_pdf_url
                FROM papers p
                INNER JOIN project_papers pp ON pp.paper_id = p.id
                WHERE pp.project_id = ?
                ORDER BY pp.added_at DESC, p.id ASC;
                """,
                (project_id,),
            ).fetchall()

            doc_rows = conn.execute(
                """
                SELECT document_id, project_id, paper_id, filename, stored_path,
                       file_size_bytes, page_count, total_characters, total_words,
                       extraction_status, created_at
                FROM documents
                WHERE project_id = ?
                ORDER BY created_at DESC, document_id ASC;
                """,
                (project_id,),
            ).fetchall()

        return ProjectDetailResponse(
            id=str(project_row["id"]),
            name=str(project_row["name"]),
            description=project_row["description"],
            created_at=str(project_row["created_at"]),
            updated_at=str(project_row["updated_at"]),
            papers=[self._row_to_paper(row) for row in paper_rows],
            documents=[self._row_to_document_metadata(row) for row in doc_rows],
        )

    def delete_project(self, project_id: str) -> ProjectDeleteResponse | None:
        """Delete a research project and clean up associated database rows and unreferenced PDF files.

        Cleanup rules:
        1. Identify all managed PDF files (`stored_path`) belonging to the project's documents.
        2. Delete the project row (which cascades to `project_papers`, `documents`, and `document_pages`).
           Shared scholarly paper records in `papers` remain intact for other projects.
        3. Remove physical PDF files from `storage_dir` if no remaining document record references them.
        """
        with self._db.connect() as conn:
            project_row = conn.execute(
                "SELECT id FROM projects WHERE id = ?;",
                (project_id,),
            ).fetchone()
            if project_row is None:
                return None

            doc_rows = conn.execute(
                "SELECT stored_path FROM documents WHERE project_id = ?;",
                (project_id,),
            ).fetchall()
            candidate_paths = {str(row["stored_path"]) for row in doc_rows if row["stored_path"]}

            conn.execute("DELETE FROM projects WHERE id = ?;", (project_id,))

            unreferenced_paths: list[str] = []
            for stored_path in candidate_paths:
                still_used = conn.execute(
                    "SELECT 1 FROM documents WHERE stored_path = ? LIMIT 1;",
                    (stored_path,),
                ).fetchone()
                if still_used is None:
                    unreferenced_paths.append(stored_path)

        removed_files_count = 0
        for rel_path in unreferenced_paths:
            if self._delete_managed_file(rel_path):
                removed_files_count += 1

        return ProjectDeleteResponse(
            deleted_project_id=project_id,
            removed_files_count=removed_files_count,
            status="deleted",
        )

    # -------------------------------------------------------------------------
    # Scholarly Papers & Project Associations
    # -------------------------------------------------------------------------

    def upsert_paper(self, paper: Paper) -> Paper:
        """Insert or update a normalized Paper in SQLite, deduplicating by normalized DOI."""
        normalized_doi = normalize_doi(paper.doi)
        stable_id = build_paper_id(
            source=paper.source,
            doi=normalized_doi,
            upstream_id=paper.id,
            title=paper.title,
        )
        now_iso = _utc_now_iso()

        with self._db.connect() as conn:
            existing_row = None
            if normalized_doi is not None:
                existing_row = conn.execute(
                    "SELECT * FROM papers WHERE doi = ?;",
                    (normalized_doi,),
                ).fetchone()
            if existing_row is None:
                existing_row = conn.execute(
                    "SELECT * FROM papers WHERE id = ?;",
                    (stable_id,),
                ).fetchone()

            if existing_row is not None:
                existing_paper = self._row_to_paper(existing_row)
                merged_authors = existing_paper.authors if existing_paper.authors else paper.authors
                merged_year = (
                    existing_paper.publication_year
                    if existing_paper.publication_year is not None
                    else paper.publication_year
                )
                merged_abstract = (
                    existing_paper.abstract
                    if existing_paper.abstract is not None
                    else paper.abstract
                )
                merged_landing = (
                    existing_paper.landing_page_url
                    if existing_paper.landing_page_url is not None
                    else paper.landing_page_url
                )
                merged_pdf = (
                    existing_paper.open_access_pdf_url
                    if existing_paper.open_access_pdf_url is not None
                    else paper.open_access_pdf_url
                )
                merged_doi = existing_paper.doi or normalized_doi

                conn.execute(
                    """
                    UPDATE papers
                    SET authors_json = ?,
                        publication_year = ?,
                        doi = ?,
                        abstract = ?,
                        landing_page_url = ?,
                        open_access_pdf_url = ?
                    WHERE id = ?;
                    """,
                    (
                        json.dumps(merged_authors),
                        merged_year,
                        merged_doi,
                        merged_abstract,
                        merged_landing,
                        merged_pdf,
                        existing_paper.id,
                    ),
                )
                return Paper(
                    id=existing_paper.id,
                    title=existing_paper.title,
                    authors=merged_authors,
                    publication_year=merged_year,
                    doi=merged_doi,
                    abstract=merged_abstract,
                    source=existing_paper.source,
                    landing_page_url=merged_landing,
                    open_access_pdf_url=merged_pdf,
                )

            conn.execute(
                """
                INSERT INTO papers (
                    id, title, authors_json, publication_year, doi,
                    abstract, source, landing_page_url, open_access_pdf_url, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    stable_id,
                    paper.title.strip(),
                    json.dumps(paper.authors),
                    paper.publication_year,
                    normalized_doi,
                    paper.abstract,
                    paper.source,
                    paper.landing_page_url,
                    paper.open_access_pdf_url,
                    now_iso,
                ),
            )

        return Paper(
            id=stable_id,
            title=paper.title.strip(),
            authors=paper.authors,
            publication_year=paper.publication_year,
            doi=normalized_doi,
            abstract=paper.abstract,
            source=paper.source,
            landing_page_url=paper.landing_page_url,
            open_access_pdf_url=paper.open_access_pdf_url,
        )

    def associate_paper_with_project(self, project_id: str, paper: Paper) -> Paper | None:
        """Persist a Paper (with DOI deduplication) and link it to a research project."""
        if not self.project_exists(project_id):
            return None

        persisted_paper = self.upsert_paper(paper)
        now_iso = _utc_now_iso()

        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO project_papers (project_id, paper_id, added_at)
                VALUES (?, ?, ?);
                """,
                (project_id, persisted_paper.id, now_iso),
            )
            conn.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?;",
                (now_iso, project_id),
            )

        return persisted_paper

    def list_project_papers(self, project_id: str) -> list[Paper] | None:
        """List all scholarly papers associated with a research project."""
        if not self.project_exists(project_id):
            return None

        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT p.id, p.title, p.authors_json, p.publication_year, p.doi,
                       p.abstract, p.source, p.landing_page_url, p.open_access_pdf_url
                FROM papers p
                INNER JOIN project_papers pp ON pp.paper_id = p.id
                WHERE pp.project_id = ?
                ORDER BY pp.added_at DESC, p.id ASC;
                """,
                (project_id,),
            ).fetchall()

        return [self._row_to_paper(row) for row in rows]

    # -------------------------------------------------------------------------
    # Documents & Managed Storage
    # -------------------------------------------------------------------------

    def save_document_and_file(
        self,
        extracted: ExtractedDocument,
        file_bytes: bytes,
        *,
        project_id: str | None = None,
        paper_id: str | None = None,
    ) -> ExtractedDocument:
        """Store the uploaded PDF in the managed storage directory and persist metadata in SQLite.

        Binary PDF contents are never stored inside SQLite.
        """
        safe_filename = sanitize_pdf_filename(extracted.filename)
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        effective_project_id = project_id if project_id is not None else extracted.project_id
        effective_paper_id = paper_id if paper_id is not None else extracted.paper_id

        # Compute stable document_id (scoped by project_id when attached to a project)
        if effective_project_id:
            scoped_digest = hashlib.sha256(f"{effective_project_id}:{sha256_hash}".encode("utf-8")).hexdigest()[:16]
            document_id = f"doc_{scoped_digest}"
        else:
            document_id = extracted.document_id or f"doc_{sha256_hash[:16]}"

        stored_filename = f"{document_id}_{safe_filename}"
        target_path = (self._storage_dir / stored_filename).resolve()
        if self._storage_dir not in target_path.parents:
            raise ValueError("Resolved storage path escaped managed storage directory.")

        target_path.write_bytes(file_bytes)
        now_iso = _utc_now_iso()

        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, project_id, paper_id, filename, stored_path,
                    sha256_hash, file_size_bytes, page_count, total_characters,
                    total_words, extraction_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    project_id = excluded.project_id,
                    paper_id = excluded.paper_id,
                    filename = excluded.filename,
                    stored_path = excluded.stored_path,
                    file_size_bytes = excluded.file_size_bytes,
                    page_count = excluded.page_count,
                    total_characters = excluded.total_characters,
                    total_words = excluded.total_words,
                    extraction_status = excluded.extraction_status;
                """,
                (
                    document_id,
                    effective_project_id,
                    effective_paper_id,
                    safe_filename,
                    stored_filename,
                    sha256_hash,
                    extracted.file_size_bytes,
                    extracted.page_count,
                    extracted.total_characters,
                    extracted.total_words,
                    "completed",
                    now_iso,
                ),
            )

            conn.execute(
                "DELETE FROM document_pages WHERE document_id = ?;",
                (document_id,),
            )
            conn.executemany(
                """
                INSERT INTO document_pages (
                    document_id, page_number, text, character_count, word_count
                )
                VALUES (?, ?, ?, ?, ?);
                """,
                [
                    (
                        document_id,
                        page.page_number,
                        page.text,
                        page.character_count,
                        page.word_count,
                    )
                    for page in extracted.pages
                ],
            )

            if effective_project_id:
                conn.execute(
                    "UPDATE projects SET updated_at = ? WHERE id = ?;",
                    (now_iso, effective_project_id),
                )

        return ExtractedDocument(
            document_id=document_id,
            project_id=effective_project_id,
            paper_id=effective_paper_id,
            filename=safe_filename,
            stored_path=stored_filename,
            file_size_bytes=extracted.file_size_bytes,
            page_count=extracted.page_count,
            total_characters=extracted.total_characters,
            total_words=extracted.total_words,
            extraction_status="completed",
            created_at=now_iso,
            pages=extracted.pages,
        )

    def get_document(self, document_id: str) -> ExtractedDocument | None:
        """Retrieve a persisted ExtractedDocument (including its extracted pages) from SQLite."""
        with self._db.connect() as conn:
            doc_row = conn.execute(
                """
                SELECT document_id, project_id, paper_id, filename, stored_path,
                       file_size_bytes, page_count, total_characters, total_words,
                       extraction_status, created_at
                FROM documents
                WHERE document_id = ?;
                """,
                (document_id,),
            ).fetchone()
            if doc_row is None:
                return None

            page_rows = conn.execute(
                """
                SELECT page_number, text, character_count, word_count
                FROM document_pages
                WHERE document_id = ?
                ORDER BY page_number ASC;
                """,
                (document_id,),
            ).fetchall()

        return ExtractedDocument(
            document_id=str(doc_row["document_id"]),
            project_id=doc_row["project_id"],
            paper_id=doc_row["paper_id"],
            filename=str(doc_row["filename"]),
            stored_path=str(doc_row["stored_path"]),
            file_size_bytes=int(doc_row["file_size_bytes"]),
            page_count=int(doc_row["page_count"]),
            total_characters=int(doc_row["total_characters"]),
            total_words=int(doc_row["total_words"]),
            extraction_status=doc_row["extraction_status"],
            created_at=str(doc_row["created_at"]),
            pages=[
                ExtractedPage(
                    page_number=int(p["page_number"]),
                    text=str(p["text"]),
                    character_count=int(p["character_count"]),
                    word_count=int(p["word_count"]),
                )
                for p in page_rows
            ],
        )

    def list_project_documents(self, project_id: str) -> list[DocumentMetadata] | None:
        """List persisted document metadata records for a given project."""
        if not self.project_exists(project_id):
            return None

        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT document_id, project_id, paper_id, filename, stored_path,
                       file_size_bytes, page_count, total_characters, total_words,
                       extraction_status, created_at
                FROM documents
                WHERE project_id = ?
                ORDER BY created_at DESC, document_id ASC;
                """,
                (project_id,),
            ).fetchall()

        return [self._row_to_document_metadata(row) for row in rows]

    # -------------------------------------------------------------------------
    # Structured Scientific Extractions (Idempotent Upsert on Retry)
    # -------------------------------------------------------------------------

    def save_scientific_extraction(
        self, extraction: ScientificPaperExtraction
    ) -> ScientificPaperExtraction:
        """Persist or update a ScientificPaperExtraction without creating duplicate records on retry."""
        now_iso = _utc_now_iso()
        with self._db.connect() as conn:
            existing_row = conn.execute(
                "SELECT created_at FROM scientific_extractions WHERE document_id = ?;",
                (extraction.document_id,),
            ).fetchone()

            created_at = str(existing_row["created_at"]) if existing_row else (extraction.created_at or now_iso)
            updated_extraction = extraction.model_copy(
                update={
                    "extraction_id": f"ext_{extraction.document_id}",
                    "created_at": created_at,
                    "updated_at": now_iso,
                }
            )
            payload_json = json.dumps(updated_extraction.model_dump())

            conn.execute(
                """
                INSERT INTO scientific_extractions (
                    extraction_id, document_id, extraction_status,
                    extraction_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    extraction_id = excluded.extraction_id,
                    extraction_status = excluded.extraction_status,
                    extraction_json = excluded.extraction_json,
                    updated_at = excluded.updated_at;
                """,
                (
                    updated_extraction.extraction_id,
                    updated_extraction.document_id,
                    updated_extraction.extraction_status,
                    payload_json,
                    created_at,
                    now_iso,
                ),
            )

        return updated_extraction

    def get_scientific_extraction(
        self, document_id: str
    ) -> ScientificPaperExtraction | None:
        """Retrieve a stored ScientificPaperExtraction for a document_id, if present."""
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT extraction_json
                FROM scientific_extractions
                WHERE document_id = ?;
                """,
                (document_id,),
            ).fetchone()

        if row is None:
            return None

        raw_data = json.loads(str(row["extraction_json"]))
        return ScientificPaperExtraction.model_validate(raw_data)

    def count_scientific_extractions(self, document_id: str) -> int:
        """Return the number of extraction records stored for a document_id (always 0 or 1)."""
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM scientific_extractions WHERE document_id = ?;",
                (document_id,),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    # -------------------------------------------------------------------------
    # LangGraph Research Analysis Runs
    # -------------------------------------------------------------------------

    def save_research_analysis(
        self, record: ResearchAnalysisRecord
    ) -> ResearchAnalysisRecord:
        """Persist or update a ResearchAnalysisRecord without creating duplicate records on retry."""
        now_iso = _utc_now_iso()
        with self._db.connect() as conn:
            existing_row = conn.execute(
                "SELECT created_at FROM research_analyses WHERE project_id = ?;",
                (record.project_id,),
            ).fetchone()

            created_at = str(existing_row["created_at"]) if existing_row else (record.created_at or now_iso)
            updated_record = record.model_copy(
                update={
                    "analysis_id": f"analysis_{record.project_id}",
                    "created_at": created_at,
                    "updated_at": now_iso,
                }
            )

            retry_counts_json = json.dumps(updated_record.retry_counts)
            node_history_json = json.dumps([item.model_dump() for item in updated_record.node_history])
            report_json = json.dumps(updated_record.report.model_dump()) if updated_record.report else None

            conn.execute(
                """
                INSERT INTO research_analyses (
                    analysis_id, project_id, status, current_node,
                    retry_counts_json, node_history_json, report_json,
                    error_message, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    analysis_id = excluded.analysis_id,
                    status = excluded.status,
                    current_node = excluded.current_node,
                    retry_counts_json = excluded.retry_counts_json,
                    node_history_json = excluded.node_history_json,
                    report_json = excluded.report_json,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at;
                """,
                (
                    updated_record.analysis_id,
                    updated_record.project_id,
                    updated_record.status,
                    updated_record.current_node,
                    retry_counts_json,
                    node_history_json,
                    report_json,
                    updated_record.error_message,
                    created_at,
                    now_iso,
                ),
            )

        return updated_record

    def get_research_analysis(
        self, project_id: str
    ) -> ResearchAnalysisRecord | None:
        """Retrieve the ResearchAnalysisRecord for a project_id, if present."""
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT analysis_id, project_id, status, current_node,
                       retry_counts_json, node_history_json, report_json,
                       error_message, created_at, updated_at
                FROM research_analyses
                WHERE project_id = ?;
                """,
                (project_id,),
            ).fetchone()

        if row is None:
            return None

        retry_counts = json.loads(str(row["retry_counts_json"])) if row["retry_counts_json"] else {}
        node_history_raw = json.loads(str(row["node_history_json"])) if row["node_history_json"] else []
        report_raw = json.loads(str(row["report_json"])) if row["report_json"] else None

        return ResearchAnalysisRecord(
            analysis_id=str(row["analysis_id"]),
            project_id=str(row["project_id"]),
            status=row["status"],
            current_node=row["current_node"],
            retry_counts=retry_counts,
            node_history=node_history_raw,
            report=ResearchReport.model_validate(report_raw) if report_raw else None,
            error_message=row["error_message"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def count_research_analyses(self, project_id: str) -> int:
        """Return the number of analysis records stored for a project_id (always 0 or 1)."""
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM research_analyses WHERE project_id = ?;",
                (project_id,),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    # -------------------------------------------------------------------------
    # Scientific Claim Relationships & Contradiction Records
    # -------------------------------------------------------------------------

    def save_claim_relationships(
        self,
        project_id: str,
        relationships: list[ClaimRelationship],
        analysis_id: str | None = None,
    ) -> list[ClaimRelationship]:
        """Persist structured scientific claim relationships for a research project."""
        now_iso = _utc_now_iso()
        persisted: list[ClaimRelationship] = []
        with self._db.connect() as conn:
            # Delete previous relationships for this project to maintain idempotent re-runs
            conn.execute(
                "DELETE FROM claim_relationships WHERE project_id = ?;",
                (project_id,),
            )
            for rel in relationships:
                created_at = rel.created_at or now_iso
                updated_rel = rel.model_copy(
                    update={"created_at": created_at}
                )
                payload_json = json.dumps(updated_rel.model_dump())
                conn.execute(
                    """
                    INSERT INTO claim_relationships (
                        relationship_id, project_id, analysis_id,
                        relationship_label, verification_status,
                        relationship_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(relationship_id) DO UPDATE SET
                        project_id = excluded.project_id,
                        analysis_id = excluded.analysis_id,
                        relationship_label = excluded.relationship_label,
                        verification_status = excluded.verification_status,
                        relationship_json = excluded.relationship_json,
                        updated_at = excluded.updated_at;
                    """,
                    (
                        updated_rel.relationship_id,
                        project_id,
                        analysis_id,
                        updated_rel.relationship_label,
                        updated_rel.verification_status,
                        payload_json,
                        created_at,
                        now_iso,
                    ),
                )
                persisted.append(updated_rel)
        return persisted

    def get_claim_relationships(self, project_id: str) -> list[ClaimRelationship]:
        """Retrieve stored scientific claim relationships for a research project."""
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT relationship_json
                FROM claim_relationships
                WHERE project_id = ?
                ORDER BY created_at ASC, relationship_id ASC;
                """,
                (project_id,),
            ).fetchall()

        results: list[ClaimRelationship] = []
        for row in rows:
            raw = json.loads(str(row["relationship_json"]))
            results.append(ClaimRelationship.model_validate(raw))
        return results

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _delete_managed_file(self, relative_filename: str) -> bool:
        """Safely delete a file inside the managed storage directory."""
        safe_name = Path(relative_filename).name
        target = (self._storage_dir / safe_name).resolve()
        if self._storage_dir not in target.parents:
            logger.warning("Refused to delete path outside managed storage: %s", relative_filename)
            return False

        if target.exists() and target.is_file():
            try:
                target.unlink()
                return True
            except OSError as exc:
                logger.warning("Failed to delete managed file %s: %s", safe_name, type(exc).__name__)
        return False

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> ProjectResponse:
        return ProjectResponse(
            id=str(row["id"]),
            name=str(row["name"]),
            description=row["description"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_paper(row: sqlite3.Row) -> Paper:
        try:
            raw_authors = json.loads(row["authors_json"])
            authors = [str(a) for a in raw_authors if isinstance(a, str)] if isinstance(raw_authors, list) else []
        except (ValueError, TypeError):
            authors = []

        return Paper(
            id=str(row["id"]),
            title=str(row["title"]),
            authors=authors,
            publication_year=int(row["publication_year"]) if row["publication_year"] is not None else None,
            doi=row["doi"],
            abstract=row["abstract"],
            source=row["source"],
            landing_page_url=row["landing_page_url"],
            open_access_pdf_url=row["open_access_pdf_url"],
        )

    @staticmethod
    def _row_to_document_metadata(row: sqlite3.Row) -> DocumentMetadata:
        return DocumentMetadata(
            document_id=str(row["document_id"]),
            project_id=row["project_id"],
            paper_id=row["paper_id"],
            filename=str(row["filename"]),
            stored_path=str(row["stored_path"]),
            file_size_bytes=int(row["file_size_bytes"]),
            page_count=int(row["page_count"]),
            total_characters=int(row["total_characters"]),
            total_words=int(row["total_words"]),
            extraction_status=row["extraction_status"],
            created_at=str(row["created_at"]),
        )
