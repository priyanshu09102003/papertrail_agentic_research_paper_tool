"""SQLite connection management and non-destructive schema migrations."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
from typing import Final

from app.config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)

MIGRATIONS: Final[list[tuple[int, str, str]]] = [
    (
        1,
        "001_initial_schema",
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS papers (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            authors_json TEXT NOT NULL,
            publication_year INTEGER,
            doi TEXT UNIQUE,
            abstract TEXT,
            source TEXT NOT NULL,
            landing_page_url TEXT,
            open_access_pdf_url TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);

        CREATE TABLE IF NOT EXISTS project_papers (
            project_id TEXT NOT NULL,
            paper_id TEXT NOT NULL,
            added_at TEXT NOT NULL,
            PRIMARY KEY (project_id, paper_id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_project_papers_project_id
            ON project_papers(project_id);

        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            project_id TEXT,
            paper_id TEXT,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            sha256_hash TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            page_count INTEGER NOT NULL,
            total_characters INTEGER NOT NULL,
            total_words INTEGER NOT NULL,
            extraction_status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_documents_project_id
            ON documents(project_id);
        CREATE INDEX IF NOT EXISTS idx_documents_stored_path
            ON documents(stored_path);

        CREATE TABLE IF NOT EXISTS document_pages (
            document_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            text TEXT NOT NULL,
            character_count INTEGER NOT NULL,
            word_count INTEGER NOT NULL,
            PRIMARY KEY (document_id, page_number),
            FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
        );
        """,
    ),
    (
        2,
        "002_scientific_extractions",
        """
        CREATE TABLE IF NOT EXISTS scientific_extractions (
            extraction_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL UNIQUE,
            extraction_status TEXT NOT NULL,
            extraction_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_scientific_extractions_document_id
            ON scientific_extractions(document_id);
        """,
    ),
    (
        3,
        "003_research_analyses",
        """
        CREATE TABLE IF NOT EXISTS research_analyses (
            analysis_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            current_node TEXT,
            retry_counts_json TEXT NOT NULL,
            node_history_json TEXT NOT NULL,
            report_json TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_research_analyses_project_id
            ON research_analyses(project_id);
        """,
    ),
    (
        4,
        "004_claim_relationships",
        """
        CREATE TABLE IF NOT EXISTS claim_relationships (
            relationship_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            analysis_id TEXT,
            relationship_label TEXT NOT NULL,
            verification_status TEXT NOT NULL,
            relationship_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_claim_relationships_project_id
            ON claim_relationships(project_id);
        CREATE INDEX IF NOT EXISTS idx_claim_relationships_label
            ON claim_relationships(relationship_label);
        """,
    ),
]


class DatabaseManager:
    """Manages SQLite connections with foreign-key enforcement and non-destructive migrations."""

    def __init__(self, db_path: Path = SQLITE_DB_PATH) -> None:
        self._db_path = Path(db_path)

    @property
    def db_path(self) -> Path:
        """Return the filesystem path of the SQLite database."""
        return self._db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a SQLite connection with foreign keys enabled and automatic transaction commit/rollback."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_and_migrate(self) -> list[str]:
        """Apply any pending schema migrations without resetting or dropping existing tables."""
        applied_now: list[str] = []
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                """
            )
            rows = conn.execute("SELECT version FROM schema_migrations;").fetchall()
            applied_versions = {int(row["version"]) for row in rows}

            for version, name, sql_script in MIGRATIONS:
                if version in applied_versions:
                    continue
                logger.info("Applying SQLite migration v%d (%s)...", version, name)
                conn.executescript(sql_script)
                conn.execute("PRAGMA foreign_keys = ON;")
                now_iso = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?);",
                    (version, name, now_iso),
                )
                applied_now.append(name)

        return applied_now
