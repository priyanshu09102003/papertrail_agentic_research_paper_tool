"""Pydantic schemas for API responses, error handling, scholarly paper discovery, and PDF extraction."""

from typing import Any, Literal

from pydantic import BaseModel, Field

PaperSource = Literal["openalex", "crossref"]


class HealthResponse(BaseModel):
    """Schema for the health check endpoint response."""

    status: Literal["ok"] = Field(default="ok", description="Service health status.")
    application: str = Field(default="PaperTrail", description="Application name.")


class VersionResponse(BaseModel):
    """Schema for the application version endpoint response."""

    application: str = Field(default="PaperTrail", description="Application name.")
    version: str = Field(..., description="Semantic version of the backend application.")


class ErrorResponse(BaseModel):
    """Standardized schema for API error responses."""

    error: str = Field(..., description="Short error type or status phrase.")
    message: str = Field(..., description="Human-readable explanation of the error.")
    status_code: int = Field(..., description="HTTP status code.")
    details: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional validation error details when applicable.",
    )


class Paper(BaseModel):
    """Normalized scholarly paper representation across discovery providers."""

    id: str = Field(..., description="Internal deterministic identifier for the paper.")
    title: str = Field(..., min_length=1, description="Title of the scholarly work.")
    authors: list[str] = Field(
        default_factory=list,
        description="Ordered list of author display names.",
    )
    publication_year: int | None = Field(
        default=None,
        description="Year the work was published, if known.",
    )
    doi: str | None = Field(
        default=None,
        description="Normalized lowercase DOI (e.g., '10.1038/nature12373'), if available.",
    )
    abstract: str | None = Field(
        default=None,
        description="Plain-text abstract of the paper, if available.",
    )
    source: PaperSource = Field(
        ...,
        description="Upstream provider that supplied the primary record ('openalex' or 'crossref').",
    )
    landing_page_url: str | None = Field(
        default=None,
        description="URL of the paper's publisher or repository landing page.",
    )
    open_access_pdf_url: str | None = Field(
        default=None,
        description="Direct open-access PDF URL, only when explicitly provided and verified as a PDF link.",
    )


class PaperSearchResponse(BaseModel):
    """Structured response for GET /api/papers/search."""

    query: str = Field(..., description="Search query string.")
    limit: int = Field(..., description="Maximum number of deduplicated results requested.")
    count: int = Field(..., description="Number of papers returned in results.")
    cached: bool = Field(
        default=False,
        description="Whether this response was served from the local search cache.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings (e.g., if one upstream source was unavailable).",
    )
    results: list[Paper] = Field(
        default_factory=list,
        description="Normalized and deduplicated list of discovered scholarly papers.",
    )


class ExtractedPage(BaseModel):
    """Structured representation of text extracted from a single PDF page."""

    page_number: int = Field(..., ge=1, description="1-based page number in the PDF document.")
    text: str = Field(..., description="Extracted plain text content for this page.")
    character_count: int = Field(
        ..., ge=0, description="Number of non-whitespace characters extracted from this page."
    )
    word_count: int = Field(
        ..., ge=0, description="Number of words extracted from this page."
    )


class ExtractedDocument(BaseModel):
    """Structured document representation returned after safe PDF ingestion and text extraction."""

    document_id: str = Field(
        ..., description="Unique deterministic identifier for the extracted document."
    )
    filename: str = Field(
        ..., description="Sanitized safe filename of the uploaded PDF."
    )
    file_size_bytes: int = Field(
        ..., ge=1, description="Size of the uploaded PDF file in bytes."
    )
    page_count: int = Field(
        ..., ge=1, description="Total number of pages in the PDF document."
    )
    total_characters: int = Field(
        ..., ge=0, description="Total non-whitespace characters extracted across all pages."
    )
    total_words: int = Field(
        ..., ge=0, description="Total words extracted across all pages."
    )
    pages: list[ExtractedPage] = Field(
        default_factory=list,
        description="Ordered page-by-page extracted text.",
    )
