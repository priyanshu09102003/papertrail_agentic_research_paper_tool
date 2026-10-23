"""Safe PDF ingestion, validation, and page-by-page text extraction using PyMuPDF."""

from collections import OrderedDict
import hashlib
import logging
import re
from typing import BinaryIO

import pymupdf as fitz  # PyMuPDF

from app.config import (
    MAX_PDF_UPLOAD_SIZE_BYTES,
    MAX_STORED_DOCUMENTS,
    MIN_EXTRACTABLE_TEXT_CHARS,
    PDF_READ_CHUNK_SIZE_BYTES,
)
from app.schemas import ExtractedDocument, ExtractedPage
from app.services.exceptions import (
    CorruptedPDFError,
    EmptyPDFError,
    EncryptedPDFError,
    InsufficientTextPDFError,
    PDFFileTooLargeError,
    ScannedPDFError,
    UnsupportedFileFormatError,
)

logger = logging.getLogger(__name__)

_PDF_MAGIC_SIGNATURE = b"%PDF-"
_UNSAFE_FILENAME_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_pdf_filename(raw_filename: str | None) -> str:
    """Sanitize an uploaded filename to prevent path traversal and unsafe characters.

    Strips any directory components (both POSIX '/' and Windows '\\'), removes
    traversal segments ('..'), strips control characters, and guarantees a safe
    basename ending in '.pdf'.
    """
    if not raw_filename or not isinstance(raw_filename, str):
        return "document.pdf"

    # Remove null bytes and control characters immediately
    cleaned = _CONTROL_CHARS_RE.sub("", raw_filename).strip()
    if not cleaned:
        return "document.pdf"

    # Split on both forward and backward slashes to strip any directory traversal path
    parts = [
        segment
        for segment in re.split(r"[/\\]+", cleaned)
        if segment and segment not in {".", ".."}
    ]
    if not parts:
        return "document.pdf"

    basename = parts[-1]
    # Remove any remaining '..' sequences and replace unsafe characters with '_'
    basename = basename.replace("..", "_")
    basename = _UNSAFE_FILENAME_CHARS_RE.sub("_", basename).strip("._-")

    if not basename:
        return "document.pdf"

    if basename.lower().endswith(".pdf"):
        stem = basename[:-4].strip("._-")
        if not stem:
            stem = "document"
    else:
        stem = basename

    # Bound filename stem length to prevent filesystem/display issues
    stem = stem[:100]
    return f"{stem}.pdf"


def _clean_page_text(raw_text: str) -> str:
    """Remove non-printable control characters while preserving line breaks."""
    if not raw_text:
        return ""
    cleaned = _CONTROL_CHARS_RE.sub("", raw_text)
    lines = [line.strip() for line in cleaned.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def _count_non_whitespace_chars(text: str) -> int:
    """Count characters excluding all whitespace."""
    return len(_WHITESPACE_RE.sub("", text))


def _count_words(text: str) -> int:
    """Count whitespace-delimited words in extracted text."""
    stripped = text.strip()
    if not stripped:
        return 0
    return len(stripped.split())


class DocumentStore:
    """Bounded in-memory store for structured ExtractedDocument representations.

    Does not store raw PDF binaries.
    """

    def __init__(self, max_documents: int = MAX_STORED_DOCUMENTS) -> None:
        self._max_documents = max_documents
        self._documents: OrderedDict[str, ExtractedDocument] = OrderedDict()

    def save(self, document: ExtractedDocument) -> None:
        """Store or update an ExtractedDocument in memory."""
        self._documents[document.document_id] = document.model_copy(deep=True)
        self._documents.move_to_end(document.document_id)
        while len(self._documents) > self._max_documents:
            self._documents.popitem(last=False)

    def get(self, document_id: str) -> ExtractedDocument | None:
        """Retrieve a stored ExtractedDocument by ID, if present."""
        doc = self._documents.get(document_id)
        if doc is None:
            return None
        self._documents.move_to_end(document_id)
        return doc.model_copy(deep=True)


class PDFIngestionService:
    """Service for validating uploaded PDFs and extracting structured page-by-page text."""

    def __init__(
        self,
        *,
        max_file_size_bytes: int = MAX_PDF_UPLOAD_SIZE_BYTES,
        min_extractable_chars: int = MIN_EXTRACTABLE_TEXT_CHARS,
        document_store: DocumentStore | None = None,
    ) -> None:
        self._max_file_size_bytes = max_file_size_bytes
        self._min_extractable_chars = min_extractable_chars
        self._store = document_store if document_store is not None else DocumentStore()

    @property
    def max_file_size_bytes(self) -> int:
        """Return the configured maximum upload size in bytes."""
        return self._max_file_size_bytes

    def get_document(self, document_id: str) -> ExtractedDocument | None:
        """Retrieve a previously extracted structured document by ID."""
        return self._store.get(document_id)

    def read_bounded_stream(self, file_obj: BinaryIO) -> bytes:
        """Read a binary file stream in chunks while enforcing the maximum file size limit."""
        chunks: list[bytes] = []
        total_bytes = 0

        while True:
            chunk = file_obj.read(PDF_READ_CHUNK_SIZE_BYTES)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > self._max_file_size_bytes:
                max_mb = self._max_file_size_bytes / (1024 * 1024)
                raise PDFFileTooLargeError(
                    f"Uploaded file exceeds the maximum allowed size of {max_mb:.1f} MB "
                    f"({self._max_file_size_bytes} bytes)."
                )
            chunks.append(chunk)

        return b"".join(chunks)

    def ingest_bytes(
        self,
        file_bytes: bytes,
        *,
        filename: str | None = None,
    ) -> ExtractedDocument:
        """Validate raw PDF bytes, extract page-by-page text in memory, and store structure."""
        safe_filename = sanitize_pdf_filename(filename)

        if not file_bytes:
            raise EmptyPDFError("The uploaded file is empty (0 bytes).")

        if len(file_bytes) > self._max_file_size_bytes:
            max_mb = self._max_file_size_bytes / (1024 * 1024)
            raise PDFFileTooLargeError(
                f"Uploaded file exceeds the maximum allowed size of {max_mb:.1f} MB "
                f"({self._max_file_size_bytes} bytes)."
            )

        # Verify PDF magic header inside the first 1024 bytes; never trust filename/Content-Type alone
        if _PDF_MAGIC_SIGNATURE not in file_bytes[:1024]:
            raise UnsupportedFileFormatError(
                "Invalid file format: uploaded file does not contain a valid '%PDF-' header."
            )

        fitz.TOOLS.mupdf_warnings(reset=True)
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            logger.warning("PyMuPDF failed to open uploaded PDF (%s): %s", safe_filename, type(exc).__name__)
            raise CorruptedPDFError(
                "The uploaded PDF file is corrupted or malformed and could not be opened."
            ) from exc

        try:
            if not getattr(doc, "is_pdf", True):
                raise UnsupportedFileFormatError(
                    "Uploaded file is not recognized as a valid PDF document."
                )

            if doc.needs_pass or doc.is_encrypted:
                raise EncryptedPDFError(
                    "The uploaded PDF is encrypted or password-protected and cannot be processed."
                )

            mupdf_warnings = fitz.TOOLS.mupdf_warnings()
            page_count = doc.page_count
            if page_count <= 0:
                if mupdf_warnings:
                    raise CorruptedPDFError(
                        "The uploaded PDF file is corrupted or malformed and contains no valid pages."
                    )
                raise EmptyPDFError(
                    "The uploaded PDF file contains no pages or is malformed."
                )

            extracted_pages: list[ExtractedPage] = []
            total_characters = 0
            total_words = 0
            pages_with_images = 0

            for page_index in range(page_count):
                try:
                    page = doc.load_page(page_index)
                    raw_page_text = page.get_text("text")
                    page_images = page.get_images(full=True)
                except Exception as exc:
                    logger.warning(
                        "PyMuPDF failed reading page %d of %s: %s",
                        page_index + 1,
                        safe_filename,
                        type(exc).__name__,
                    )
                    raise CorruptedPDFError(
                        f"Failed to read page {page_index + 1}; the PDF file appears to be corrupted."
                    ) from exc

                if page_images:
                    pages_with_images += 1

                cleaned_text = _clean_page_text(raw_page_text)
                char_count = _count_non_whitespace_chars(cleaned_text)
                word_count = _count_words(cleaned_text)

                total_characters += char_count
                total_words += word_count

                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_index + 1,
                        text=cleaned_text,
                        character_count=char_count,
                        word_count=word_count,
                    )
                )
        finally:
            doc.close()

        # Detect scanned PDFs and PDFs with insufficient extractable text
        if total_characters < self._min_extractable_chars:
            if pages_with_images > 0:
                raise ScannedPDFError(
                    "The uploaded PDF appears to be a scanned document (image-based pages detected "
                    f"with only {total_characters} extractable characters). "
                    "OCR may be required before this document can be analyzed."
                )
            raise InsufficientTextPDFError(
                f"The uploaded PDF contains too little extractable text ({total_characters} "
                f"non-whitespace characters found; minimum required is {self._min_extractable_chars}). "
                "If this is a scanned document, OCR may be required."
            )

        digest = hashlib.sha256(file_bytes).hexdigest()[:16]
        document_id = f"doc_{digest}"

        structured_document = ExtractedDocument(
            document_id=document_id,
            filename=safe_filename,
            file_size_bytes=len(file_bytes),
            page_count=page_count,
            total_characters=total_characters,
            total_words=total_words,
            pages=extracted_pages,
        )

        self._store.save(structured_document)
        return structured_document
