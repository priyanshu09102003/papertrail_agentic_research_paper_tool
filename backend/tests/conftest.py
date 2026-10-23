"""Shared pytest fixtures ensuring all tests use an isolated temporary database and storage folder."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.api.projects import get_repository
from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.main import app


@pytest.fixture(autouse=True)
def isolated_test_repository(tmp_path: Path) -> Iterator[PaperTrailRepository]:
    """Automatically isolate every test with a temporary SQLite database and storage directory.

    Guarantees that running pytest never creates or modifies real user data in backend/data/.
    """
    test_db_path = tmp_path / "test_papertrail.db"
    test_storage_dir = tmp_path / "uploads"
    db_manager = DatabaseManager(db_path=test_db_path)
    repo = PaperTrailRepository(db=db_manager, storage_dir=test_storage_dir)

    app.dependency_overrides[get_repository] = lambda: repo
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(get_repository, None)
