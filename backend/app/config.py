"""Configuration constants for the PaperTrail backend."""

from pathlib import Path
from typing import Final

from app import __version__

APP_NAME: Final[str] = "PaperTrail"
APP_VERSION: Final[str] = __version__
ALLOWED_ORIGINS: Final[list[str]] = [
    "http://localhost:3000",
]

# External Scholarly API Configuration
OPENALEX_BASE_URL: Final[str] = "https://api.openalex.org"
CROSSREF_BASE_URL: Final[str] = "https://api.crossref.org"
HTTP_TIMEOUT_SECONDS: Final[float] = 10.0
HTTP_CONNECT_TIMEOUT_SECONDS: Final[float] = 5.0
MAX_CONCURRENT_UPSTREAM_REQUESTS: Final[int] = 4
USER_AGENT: Final[str] = f"{APP_NAME}/{APP_VERSION} (Scholarly Research Discovery)"

# Search & Cache Configuration
DEFAULT_SEARCH_LIMIT: Final[int] = 10
MAX_SEARCH_LIMIT: Final[int] = 50
CACHE_TTL_SECONDS: Final[int] = 900  # 15 minutes
CACHE_MAX_ENTRIES: Final[int] = 128
CACHE_FILE_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent / ".cache" / "paper_search_cache.json"
)

# PDF Ingestion & Extraction Configuration
MAX_PDF_UPLOAD_SIZE_BYTES: Final[int] = 20 * 1024 * 1024  # 20 MB maximum upload size
MAX_PDF_UPLOAD_SIZE_MB: Final[int] = 20
PDF_READ_CHUNK_SIZE_BYTES: Final[int] = 64 * 1024  # 64 KB streaming read chunks
MIN_EXTRACTABLE_TEXT_CHARS: Final[int] = 50  # Minimum non-whitespace characters across PDF
MAX_STORED_DOCUMENTS: Final[int] = 50  # In-memory bounded structured document store limit
