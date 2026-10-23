"""Configuration constants for the PaperTrail backend."""

import os
from pathlib import Path
from typing import Final

from app import __version__

APP_NAME: Final[str] = "PaperTrail"
APP_VERSION: Final[str] = __version__
ALLOWED_ORIGINS: Final[list[str]] = [
    "http://localhost:3000",
]

BACKEND_ROOT_DIR: Final[Path] = Path(__file__).resolve().parent.parent
PROJECT_ROOT_DIR: Final[Path] = BACKEND_ROOT_DIR.parent


def load_dotenv_files() -> None:
    """Safely load key=value pairs from project .env files (handling UTF-8 BOM, UTF-16, and quotes)."""
    candidate_paths = [
        BACKEND_ROOT_DIR / ".env",
        PROJECT_ROOT_DIR / ".env",
        BACKEND_ROOT_DIR / ".env.example",
    ]
    for env_path in candidate_paths:
        if not env_path.is_file():
            continue
        try:
            try:
                content = env_path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                content = env_path.read_text(encoding="utf-16")

            for raw_line in content.splitlines():
                line = raw_line.strip().lstrip("\ufeff")
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    if line.startswith("AIza") and not os.environ.get("GEMINI_API_KEY"):
                        os.environ["GEMINI_API_KEY"] = line
                    continue
                key, _, val = line.partition("=")
                key = key.strip().lstrip("\ufeff")
                if key.lower().startswith("export "):
                    key = key[7:].strip()
                elif key.lower().startswith("$env:"):
                    key = key[5:].strip()
                val = val.strip().strip('"').strip("'")
                if key and val and not os.environ.get(key):
                    os.environ[key] = val
        except OSError:
            continue


load_dotenv_files()

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
CACHE_FILE_PATH: Final[Path] = BACKEND_ROOT_DIR / ".cache" / "paper_search_cache.json"

# PDF Ingestion & Extraction Configuration
MAX_PDF_UPLOAD_SIZE_BYTES: Final[int] = 20 * 1024 * 1024  # 20 MB maximum upload size
MAX_PDF_UPLOAD_SIZE_MB: Final[int] = 20
PDF_READ_CHUNK_SIZE_BYTES: Final[int] = 64 * 1024  # 64 KB streaming read chunks
MIN_EXTRACTABLE_TEXT_CHARS: Final[int] = 50  # Minimum non-whitespace characters across PDF
MAX_STORED_DOCUMENTS: Final[int] = 50  # In-memory bounded structured document store limit

# Persistent SQLite & Managed File Storage Configuration
DATA_DIR: Final[Path] = BACKEND_ROOT_DIR / "data"
SQLITE_DB_PATH: Final[Path] = DATA_DIR / "papertrail.db"
MANAGED_STORAGE_DIR: Final[Path] = DATA_DIR / "uploads"

# Local LLM (Ollama) Configuration
OLLAMA_BASE_URL: Final[str] = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_DEFAULT_MODEL: Final[str] = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_TIMEOUT_SECONDS: Final[float] = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300.0"))
OLLAMA_CONNECT_TIMEOUT_SECONDS: Final[float] = float(
    os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "5.0")
)
OLLAMA_DEFAULT_TEMPERATURE: Final[float] = 0.1
OLLAMA_DEFAULT_MAX_TOKENS: Final[int] = 350
OLLAMA_CONTEXT_WINDOW: Final[int] = 2048
OLLAMA_MAX_STRUCTURED_RETRIES: Final[int] = 2
OLLAMA_HARD_MAX_RETRIES_CAP: Final[int] = 3
OLLAMA_MAX_PROMPT_CHARS: Final[int] = 32000

# Optional Fast Cloud Extraction LLM (Google Gemini API) Configuration
GEMINI_API_BASE_URL: Final[str] = os.getenv(
    "GEMINI_API_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
)
GEMINI_DEFAULT_MODEL: Final[str] = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_TIMEOUT_SECONDS: Final[float] = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30.0"))
GEMINI_MAX_TOKENS_PER_CHUNK: Final[int] = 1024


def get_gemini_api_key() -> str | None:
    """Return GEMINI_API_KEY (or GOOGLE_API_KEY) from environment or .env files if configured."""
    load_dotenv_files()
    raw = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return raw if raw else None


# Scientific Paper Structured Extraction Configuration
EXTRACTION_MAX_CHUNK_CHARS: Final[int] = 2400
EXTRACTION_MAX_CHUNKS_PER_DOC: Final[int] = 12
EXTRACTION_MAX_TOKENS_PER_CHUNK: Final[int] = 120
EXTRACTION_CHUNK_RETRIES: Final[int] = 1
