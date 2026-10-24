"""API routes for persistent research projects, project-paper associations, and project documents."""

from functools import lru_cache
from http import HTTPStatus

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import MANAGED_STORAGE_DIR, SQLITE_DB_PATH
from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.schemas import (
    ClaimRelationship,
    DocumentMetadata,
    ExtractedDocument,
    Paper,
    ProjectCreateRequest,
    ProjectDeleteResponse,
    ProjectDetailResponse,
    ProjectResponse,
    ScientificPaperExtraction,
)
from app.services.exceptions import PDFIngestionError
from app.services.pdf_ingestion import PDFIngestionService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@lru_cache(maxsize=1)
def get_repository() -> PaperTrailRepository:
    """Return the default singleton PaperTrailRepository backed by SQLite."""
    db_manager = DatabaseManager(db_path=SQLITE_DB_PATH)
    return PaperTrailRepository(db=db_manager, storage_dir=MANAGED_STORAGE_DIR)


@lru_cache(maxsize=1)
def _get_default_pdf_service() -> PDFIngestionService:
    return PDFIngestionService()


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=HTTPStatus.CREATED,
    summary="Create Research Project",
    description="Create a new persistent research project.",
)
async def create_project(
    payload: ProjectCreateRequest,
    repo: PaperTrailRepository = Depends(get_repository),
) -> ProjectResponse:
    """Create a research project after validating non-whitespace name."""
    cleaned_name = payload.name.strip()
    if not cleaned_name:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Project name must not be empty or whitespace.",
        )
    return repo.create_project(name=cleaned_name, description=payload.description)


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List Research Projects",
    description="List all persisted research projects.",
)
async def list_projects(
    repo: PaperTrailRepository = Depends(get_repository),
) -> list[ProjectResponse]:
    """Return all research projects ordered by creation timestamp descending."""
    return repo.list_projects()


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get Research Project Details",
    description="Retrieve a research project along with its associated papers and uploaded document metadata.",
)
async def get_project(
    project_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> ProjectDetailResponse:
    """Retrieve a project by ID or raise 404."""
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    return project


@router.delete(
    "/{project_id}",
    response_model=ProjectDeleteResponse,
    summary="Delete Research Project",
    description=(
        "Delete a research project, cascade-delete its paper associations and document metadata, "
        "and remove unreferenced PDF files from the managed storage directory."
    ),
)
async def delete_project(
    project_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> ProjectDeleteResponse:
    """Delete a project and perform file cleanup."""
    result = repo.delete_project(project_id)
    if result is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    return result


@router.post(
    "/{project_id}/papers",
    response_model=Paper,
    status_code=HTTPStatus.OK,
    summary="Associate Paper with Project",
    description=(
        "Persist a normalized scholarly paper (deduplicated by normalized DOI) "
        "and associate it with the specified research project."
    ),
)
async def add_paper_to_project(
    project_id: str,
    paper: Paper,
    repo: PaperTrailRepository = Depends(get_repository),
) -> Paper:
    """Upsert a discovered paper and link it to the project."""
    persisted = repo.associate_paper_with_project(project_id=project_id, paper=paper)
    if persisted is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    return persisted


@router.get(
    "/{project_id}/papers",
    response_model=list[Paper],
    summary="List Project Papers",
    description="List all scholarly papers associated with a research project.",
)
async def list_project_papers(
    project_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> list[Paper]:
    """List papers linked to a project."""
    papers = repo.list_project_papers(project_id)
    if papers is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    return papers


@router.delete(
    "/{project_id}/papers/{paper_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Remove Paper from Project",
    description="Disassociate a scholarly paper from a research project.",
)
async def remove_paper_from_project(
    project_id: str,
    paper_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> None:
    """Disassociate a paper from a project."""
    if not repo.project_exists(project_id):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    repo.remove_paper_from_project(project_id, paper_id)


@router.get(
    "/{project_id}/relationships",
    response_model=list[ClaimRelationship],
    summary="List Project Claim Relationships",
    description="Retrieve all verified cross-paper claim relationships and potential contradictions for a project.",
)
async def list_project_claim_relationships(
    project_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> list[ClaimRelationship]:
    """Retrieve verified claim relationships for a project."""
    if not repo.project_exists(project_id):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    return repo.get_claim_relationships(project_id)


@router.get(
    "/{project_id}/extractions",
    response_model=list[ScientificPaperExtraction],
    summary="List Project Scientific Extractions",
    description="Retrieve structured scientific methodology, metrics, and claims for all documents in a project.",
)
async def list_project_extractions(
    project_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> list[ScientificPaperExtraction]:
    """Retrieve extractions for all documents associated with a project."""
    if not repo.project_exists(project_id):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    doc_metas = repo.list_project_documents(project_id) or []
    extractions: list[ScientificPaperExtraction] = []
    for m in doc_metas:
        ext = repo.get_scientific_extraction(m.document_id)
        if ext:
            extractions.append(ext)
    return extractions



@router.post(
    "/{project_id}/documents",
    response_model=ExtractedDocument,
    status_code=HTTPStatus.OK,
    summary="Upload PDF Document to Project",
    description=(
        "Validate and extract text from a research PDF, store the file in the dedicated "
        "managed storage directory, and persist document metadata under the project."
    ),
)
async def upload_project_document(
    project_id: str,
    file: UploadFile = File(..., description="Single research PDF file to upload."),
    repo: PaperTrailRepository = Depends(get_repository),
    pdf_service: PDFIngestionService = Depends(_get_default_pdf_service),
) -> ExtractedDocument:
    """Upload, extract, and persist a PDF document linked to a specific project."""
    if not repo.project_exists(project_id):
        await file.close()
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )

    try:
        file_bytes = pdf_service.read_bounded_stream(file.file)
        extracted = pdf_service.ingest_bytes(file_bytes, filename=file.filename)
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
    "/{project_id}/documents",
    response_model=list[DocumentMetadata],
    summary="List Project Documents",
    description="List persisted PDF document metadata records associated with a research project.",
)
async def list_project_documents(
    project_id: str,
    repo: PaperTrailRepository = Depends(get_repository),
) -> list[DocumentMetadata]:
    """List document metadata for a project."""
    docs = repo.list_project_documents(project_id)
    if docs is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Research project '{project_id}' was not found.",
        )
    return docs
