# PaperTrail Backend

FastAPI backend service for **PaperTrail**, an AI research analysis platform.

## Project Structure

```text
backend/
├── app/
│   ├── __init__.py                 # Package version definition
│   ├── config.py                   # App, API timeout, cache, PDF limits, SQLite, and Ollama settings
│   ├── main.py                     # FastAPI application entry point and error handlers
│   ├── schemas.py                  # Pydantic models for health, papers, documents, projects, and LLM
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py               # GET /api/health and GET /api/version endpoints
│   │   ├── papers.py               # GET /api/papers/search endpoint
│   │   ├── documents.py            # POST /api/documents/upload, GET /api/documents/{id}, POST/GET extraction
│   │   ├── projects.py             # /api/projects CRUD, paper associations, and project PDFs
│   │   └── llm.py                  # GET /api/llm/status readiness check endpoint
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite connection manager and non-destructive migrations
│   │   └── repository.py           # Data access layer and managed storage file cleanup
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                 # Workflow-independent BaseLLMProvider & bounded JSON validation
│   │   ├── exceptions.py           # Controlled LLM exceptions (safe user-facing messages)
│   │   └── ollama_provider.py      # Local Ollama HTTP API client (qwen2.5:1.5b)
│   └── services/
│       ├── __init__.py
│       ├── cache.py                # Local TTL search response cache
│       ├── crossref_client.py      # Async Crossref REST API client
│       ├── discovery.py            # Concurrent discovery & DOI deduplication service
│       ├── exceptions.py           # Upstream API and PDF ingestion exceptions
│       ├── normalization.py        # DOI, abstract, and verified PDF URL helpers
│       ├── openalex_client.py      # Async OpenAlex REST API client
│       ├── pdf_ingestion.py        # Safe PyMuPDF validation and page-by-page text extraction
│       └── paper_extractor.py      # Structured scientific-paper extraction & ground-truth quote verifier
├── scripts/
│   ├── init_db.py                  # Non-destructive SQLite schema initialization & migration CLI
│   ├── smoke_test_discovery.py     # Optional manual smoke test for live OpenAlex/Crossref APIs
│   ├── verify_ollama.py            # Local integration test for live Ollama (qwen2.5:1.5b)
│   └── verify_real_paper_extraction.py # Live extraction & 7-point integrity audit on a real research paper
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Isolates all tests with a temporary SQLite DB and storage dir
│   ├── test_main.py                # pytest suite for health, version, CORS, and 404 handling
│   ├── test_papers.py              # Mocked HTTP pytest suite for scholarly paper discovery
│   ├── test_pdf_ingestion.py       # pytest suite for PDF upload validation and extraction
│   ├── test_projects_db.py         # pytest suite for SQLite persistence and cleanup rules
│   ├── test_ollama_provider.py     # Mocked unit tests for OllamaProvider & structured validation
│   └── test_paper_extractor.py     # Unit tests for scientific extraction, quote verification, and edge cases
├── requirements.txt                # Runtime dependencies
├── requirements-dev.txt            # Development and testing dependencies (pytest, httpx, pymupdf)
└── README.md                       # Setup, database migrations, startup, and testing guide
```

---

## Local LLM Configuration (Ollama)

Configured in `app/config.py` (overrideable via environment variables):

- `OLLAMA_BASE_URL`: Defaults to `http://127.0.0.1:11434`
- `OLLAMA_MODEL`: Defaults to `qwen2.5:1.5b`
- `OLLAMA_TIMEOUT_SECONDS`: Defaults to `120.0` seconds (`5.0` seconds connect timeout)
- `OLLAMA_MAX_STRUCTURED_RETRIES`: Defaults to `2` bounded retries (hard-capped at `3` retries / `4` total attempts so unbounded generation loops are impossible).

---

## 1. Setup & Database Initialization (PowerShell)

```powershell
cd C:\Users\priya\Desktop\papertrail\backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m scripts.init_db
```

---

## 2. Running Automated Unit Tests (Offline / Mocked)

```powershell
cd C:\Users\priya\Desktop\papertrail\backend
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 3. Verifying Local Ollama (`qwen2.5:1.5b`) Connection

Ensure Ollama is running (`ollama list` shows `qwen2.5:1.5b`), then run the live integration verification script:

```powershell
cd C:\Users\priya\Desktop\papertrail\backend
.\.venv\Scripts\python.exe -m scripts.verify_ollama
```

Or check the HTTP status endpoint while Uvicorn is running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/llm/status
```

---

## 4. Scientific Paper Structured Extraction & Local Real-Paper Audit

Run the automated 7-point scientific integrity audit against a real open-access paper (`Attention Is All You Need`, Vaswani et al., 2017, arXiv:1706.03762) or pass `--pdf <path>` / `--url <pdf_url>`:

```powershell
cd C:\Users\priya\Desktop\papertrail\backend
.\.venv\Scripts\python.exe -m scripts.verify_real_paper_extraction
```

