"""API routes for safe PDF upload, validation, page-by-page text extraction, and structured scientific extraction."""

from functools import lru_cache
from http import HTTPStatus

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from app.api.llm import get_extraction_llm_provider, get_llm_provider
from app.api.projects import get_repository
from app.db.repository import PaperTrailRepository
from app.llm.base import BaseLLMProvider
from app.schemas import ExtractedDocument, ScientificPaperExtraction
from app.services.exceptions import PDFIngestionError
from app.services.paper_extractor import ScientificPaperExtractor
from app.services.pdf_ingestion import PDFIngestionService

router = APIRouter(prefix="/api/documents", tags=["documents"])


@lru_cache(maxsize=1)
def get_pdf_ingestion_service() -> PDFIngestionService:
    """Return a singleton PDFIngestionService instance."""
    return PDFIngestionService()


def get_scientific_extractor(
    request: Request,
    provider: str = Query(
        default="auto",
        description="LLM provider for extraction: 'auto' (Gemini if GEMINI_API_KEY is set, else Ollama), 'gemini', or 'ollama'.",
    ),
    default_llm_provider: BaseLLMProvider = Depends(get_llm_provider),
) -> ScientificPaperExtractor:
    """Return a ScientificPaperExtractor configured with Gemini (if API key present) or local Ollama."""
    # Preserve FastAPI dependency_overrides[get_llm_provider] used by unit tests
    if get_llm_provider in request.app.dependency_overrides and provider == "auto":
        return ScientificPaperExtractor(llm_provider=default_llm_provider)

    active_provider = get_extraction_llm_provider(provider)
    return ScientificPaperExtractor(llm_provider=active_provider)


@router.post(
    "/upload",
    response_model=ExtractedDocument,
    status_code=HTTPStatus.OK,
    summary="Upload and Extract Research PDF",
    description=(
        "Validates a single uploaded research PDF (up to 20 MB), verifies its binary PDF "
        "structure using PyMuPDF, extracts text page by page, stores the file in the "
        "application-managed storage directory, persists document metadata in SQLite, "
        "and returns the structured document representation."
    ),
)
async def upload_pdf_document(
    file: UploadFile = File(..., description="Single research PDF file to upload and extract."),
    project_id: str | None = Query(
        default=None,
        description="Optional research project ID to associate this uploaded document with.",
    ),
    service: PDFIngestionService = Depends(get_pdf_ingestion_service),
    repo: PaperTrailRepository = Depends(get_repository),
) -> ExtractedDocument:
    """Validate, extract text page by page, and persist metadata for an uploaded PDF file."""
    try:
        if project_id is not None and not repo.project_exists(project_id):
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=f"Research project '{project_id}' was not found.",
            )

        file_bytes = service.read_bounded_stream(file.file)
        extracted = service.ingest_bytes(file_bytes, filename=file.filename)
        return repo.save_document_and_file(
            extracted=extracted,
            file_bytes=file_bytes,
            project_id=project_id,
        )
    except PDFIngestionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.message,
        ) from exc
    finally:
        await file.close()


@router.get(
    "/{document_id}",
    response_model=ExtractedDocument,
    summary="Get Extracted Document",
    description="Retrieve a structured document representation by its document_id.",
)
async def get_extracted_document(
    document_id: str,
    service: PDFIngestionService = Depends(get_pdf_ingestion_service),
    repo: PaperTrailRepository = Depends(get_repository),
) -> ExtractedDocument:
    """Retrieve a structured document from SQLite or the in-memory session store."""
    document = repo.get_document(document_id) or service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )
    return document


@router.post(
    "/{document_id}/extract",
    response_model=ScientificPaperExtraction,
    status_code=HTTPStatus.OK,
    summary="Run Structured Scientific Extraction",
    description=(
        "Extracts structured scientific methodology, datasets, sample size, metrics, "
        "quantitative results, claims, limitations, and verified verbatim supporting "
        "passages from a processed document. Retrying updates the existing record "
        "without creating duplicates."
    ),
)
async def extract_scientific_paper(
    document_id: str,
    service: PDFIngestionService = Depends(get_pdf_ingestion_service),
    repo: PaperTrailRepository = Depends(get_repository),
    extractor: ScientificPaperExtractor = Depends(get_scientific_extractor),
) -> ScientificPaperExtraction:
    """Run or retry structured scientific extraction on a processed document and persist the result."""
    document = repo.get_document(document_id) or service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )

    extraction = await extractor.extract_document(document)
    return repo.save_scientific_extraction(extraction)


@router.get(
    "/{document_id}/extraction",
    response_model=ScientificPaperExtraction,
    summary="Get Stored Scientific Extraction",
    description="Retrieve the persisted structured scientific extraction for a document_id.",
)
async def get_scientific_extraction(
    document_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> ScientificPaperExtraction:
    """Retrieve a persisted ScientificPaperExtraction from SQLite."""
    extraction = repo.get_scientific_extraction(document_id)
    if extraction is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"No scientific extraction found for document '{document_id}'.",
        )
    return extraction


@router.get(
    "/{document_id}/file",
    summary="Download or View Research PDF File",
    description="Streams the raw uploaded PDF file from managed storage.",
)
async def get_document_file(
    document_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> FileResponse:
    """Stream the physical PDF document binary for in-browser viewing or download."""
    doc = repo.get_document(document_id)
    if doc is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )
    file_path = repo.get_document_file_path(document_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Physical file for document '{document_id}' was not found in storage.",
        )
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=doc.filename,
    )

