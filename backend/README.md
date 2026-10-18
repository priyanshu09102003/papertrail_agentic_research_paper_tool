# PaperTrail Backend

FastAPI backend service for **PaperTrail**, an AI research analysis platform.

## Project Structure

```text
backend/
├── app/
│   ├── __init__.py                 # Package version definition
│   ├── config.py                   # App, API timeout, concurrency, cache, and PDF upload settings
│   ├── main.py                     # FastAPI application entry point and error handlers
│   ├── schemas.py                  # Pydantic response, error, Paper, and ExtractedDocument models
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py               # GET /api/health and GET /api/version endpoints
│   │   ├── papers.py               # GET /api/papers/search endpoint
│   │   └── documents.py            # POST /api/documents/upload and GET /api/documents/{id}
│   └── services/
│       ├── __init__.py
│       ├── cache.py                # Local TTL search response cache
│       ├── crossref_client.py      # Async Crossref REST API client
│       ├── discovery.py            # Concurrent discovery & DOI deduplication service
│       ├── exceptions.py           # Upstream API and PDF ingestion exceptions
│       ├── normalization.py        # DOI, abstract, and verified PDF URL helpers
│       ├── openalex_client.py      # Async OpenAlex REST API client
│       └── pdf_ingestion.py        # Safe PyMuPDF validation and page-by-page text extraction
├── scripts/
│   └── smoke_test_discovery.py     # Optional manual smoke test for live OpenAlex/Crossref APIs
├── tests/
│   ├── __init__.py
│   ├── test_main.py                # pytest suite for health, version, CORS, and 404 handling
│   ├── test_papers.py              # Mocked HTTP pytest suite for scholarly paper discovery
│   └── test_pdf_ingestion.py       # pytest suite for PDF upload validation and extraction
├── requirements.txt                # Runtime dependencies
├── requirements-dev.txt            # Development and testing dependencies (pytest, httpx)
└── README.md                       # Setup, startup, limits, and testing documentation
```

## PDF Ingestion & File-Size Limits

- **Maximum PDF Upload Size:** `20 MB` (`20,971,520` bytes, configured via `MAX_PDF_UPLOAD_SIZE_BYTES` in `app/config.py`). Uploads exceeding 20 MB are rejected while streaming with `HTTP 413 Payload Too Large`.
- **Binary Format Verification:** Uploaded files must contain a valid `%PDF-` binary signature and parse cleanly in PyMuPDF (`fitz`). Spoofed filenames or `Content-Type` headers are rejected with `HTTP 400 Bad Request`.
- **Encrypted & Corrupted PDFs:** Password-protected/encrypted or malformed PDFs are rejected with `HTTP 400 Bad Request`.
- **Minimum Extractable Text & Scanned PDF Detection:** A valid PDF must yield at least `50` non-whitespace characters across all pages (`MIN_EXTRACTABLE_TEXT_CHARS`). PDFs with insufficient text or image-only scanned pages are rejected with `HTTP 422 Unprocessable Entity` and a message indicating that **OCR may be required** (no OCR binaries are installed or executed automatically).
- **Zero Temporary Disk Retention:** PDFs are parsed directly from bounded in-memory streams (`fitz.open(stream=..., filetype="pdf")`) and closed immediately. Raw PDF binaries are not stored permanently on disk or in a database.

---

## 1. Setup (PowerShell)

Open PowerShell and navigate to the `backend` directory:

```powershell
cd C:\Users\priya\Desktop\papertrail\backend
```

Activate the virtual environment and ensure dependencies are installed:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

---

## 2. Startup (PowerShell)

With the virtual environment activated inside `C:\Users\priya\Desktop\papertrail\backend`, start the development server using Uvicorn:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, you can verify the endpoints in a second PowerShell window or browser:

- **Health Check:** `Invoke-RestMethod http://127.0.0.1:8000/api/health`
- **Version Info:** `Invoke-RestMethod http://127.0.0.1:8000/api/version`
- **Paper Search:** `Invoke-RestMethod "http://127.0.0.1:8000/api/papers/search?q=machine+learning&limit=5"`
- **Interactive API Docs (Swagger UI):** `http://127.0.0.1:8000/docs`

---

## 3. Running Unit Tests (PowerShell)

From the `C:\Users\priya\Desktop\papertrail\backend` directory, run the complete `pytest` suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 4. Optional Live API Smoke Test

To manually test live queries against the OpenAlex and Crossref REST APIs:

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke_test_discovery --query "retrieval augmented generation" --limit 5
```
