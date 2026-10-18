"""API routes for safe PDF upload, validation, and page-by-page text extraction."""

from functools import lru_cache
from http import HTTPStatus

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.schemas import ExtractedDocument
from app.services.exceptions import PDFIngestionError
from app.services.pdf_ingestion import PDFIngestionService

router = APIRouter(prefix="/api/documents", tags=["documents"])


@lru_cache(maxsize=1)
def get_pdf_ingestion_service() -> PDFIngestionService:
    """Return a singleton PDFIngestionService instance."""
    return PDFIngestionService()


@router.post(
    "/upload",
    response_model=ExtractedDocument,
    status_code=HTTPStatus.OK,
    summary="Upload and Extract Research PDF",
    description=(
        "Validates a single uploaded research PDF (up to 20 MB), verifies its binary PDF "
        "structure using PyMuPDF, extracts text page by page, detects scanned or low-text "
        "documents, and returns the structured document representation."
    ),
)
async def upload_pdf_document(
    file: UploadFile = File(..., description="Single research PDF file to upload and extract."),
    service: PDFIngestionService = Depends(get_pdf_ingestion_service),
) -> ExtractedDocument:
    """Validate and extract text page by page from an uploaded PDF file."""
    try:
        file_bytes = service.read_bounded_stream(file.file)
        return service.ingest_bytes(file_bytes, filename=file.filename)
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
) -> ExtractedDocument:
    """Retrieve a structured document from the in-memory session store."""
    document = service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )
    return document
