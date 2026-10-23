"""Initialize and apply non-destructive SQLite migrations for PaperTrail.

Usage (from backend directory in PowerShell):
    .\.venv\Scripts\python.exe -m scripts.init_db
"""

from app.config import MANAGED_STORAGE_DIR, SQLITE_DB_PATH
from app.db.database import DatabaseManager


def main() -> None:
    MANAGED_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    db_manager = DatabaseManager(db_path=SQLITE_DB_PATH)
    applied = db_manager.initialize_and_migrate()
    if applied:
        print(f"[OK] Applied SQLite migrations: {', '.join(applied)}")
    else:
        print("[OK] SQLite database is already up to date (no pending migrations).")
    print(f"Database location: {SQLITE_DB_PATH}")
    print(f"Managed storage directory: {MANAGED_STORAGE_DIR}")


if __name__ == "__main__":
    main()
