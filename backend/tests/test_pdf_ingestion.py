"""Tests for safe PDF upload, validation, path-traversal protection, and PyMuPDF text extraction."""

import fitz  # PyMuPDF
from fastapi.testclient import TestClient

from app.api.documents import get_pdf_ingestion_service
from app.main import app
from app.services.pdf_ingestion import PDFIngestionService, sanitize_pdf_filename

client = TestClient(app)


def _build_valid_pdf_bytes(pages_text: list[str]) -> bytes:
    """Create an in-memory PDF with the given text wrapped inside each page."""
    doc = fitz.open()
    try:
        for text in pages_text:
            page = doc.new_page()
            page.insert_textbox(fitz.Rect(72, 72, 520, 720), text, fontsize=12)
        return doc.tobytes()
    finally:
        doc.close()


def _build_encrypted_pdf_bytes(text: str, password: str = "secret123") -> bytes:
    """Create an in-memory password-encrypted PDF."""
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
        return doc.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw=password,
            user_pw=password,
        )
    finally:
        doc.close()


def _build_scanned_image_only_pdf_bytes() -> bytes:
    """Create an in-memory PDF containing a raster image and no selectable text."""
    doc = fitz.open()
    try:
        page = doc.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
        pixmap.clear_with(200)
        png_bytes = pixmap.tobytes("png")
        page.insert_image(fitz.Rect(72, 72, 272, 272), stream=png_bytes)
        return doc.tobytes()
    finally:
        doc.close()


def test_valid_multipage_pdf_upload_and_extraction() -> None:
    """Verify a valid multi-page PDF is extracted page-by-page with preserved page numbers."""
    page_1_text = (
        "Transformer architectures have revolutionized natural language processing "
        "by replacing recurrence with self-attention mechanisms."
    )
    page_2_text = (
        "Experimental evaluation on machine translation benchmarks demonstrates "
        "superior quality and substantially lower training cost."
    )
    pdf_bytes = _build_valid_pdf_bytes([page_1_text, page_2_text])

    response = client.post(
        "/api/documents/upload",
        files={"file": ("attention_paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"].startswith("doc_")
    assert data["filename"] == "attention_paper.pdf"
    assert data["file_size_bytes"] == len(pdf_bytes)
    assert data["page_count"] == 2
    assert data["total_characters"] >= 150
    assert data["total_words"] >= 25
    assert len(data["pages"]) == 2

    assert data["pages"][0]["page_number"] == 1
    assert "Transformer architectures" in data["pages"][0]["text"]
    assert data["pages"][0]["character_count"] > 0
    assert data["pages"][0]["word_count"] > 0

    assert data["pages"][1]["page_number"] == 2
    assert "Experimental evaluation" in data["pages"][1]["text"]

    # Verify structured document can also be retrieved by document_id
    get_res = client.get(f"/api/documents/{data['document_id']}")
    assert get_res.status_code == 200
    assert get_res.json()["document_id"] == data["document_id"]


def test_unsafe_filenames_and_path_traversal_prevented() -> None:
    """Verify path traversal sequences and unsafe characters are stripped from filenames."""
    assert sanitize_pdf_filename("../../etc/passwd") == "passwd.pdf"
    assert sanitize_pdf_filename("..\\..\\Windows\\System32\\malicious.pdf") == "malicious.pdf"
    assert sanitize_pdf_filename(".../..//") == "document.pdf"
    assert sanitize_pdf_filename("my\x00unsafe<>:\"file|?*.pdf") == "myunsafe_file.pdf"

    pdf_bytes = _build_valid_pdf_bytes(
        [
            "This valid research paper tests path traversal protection on uploaded filenames "
            "with plenty of extractable scholarly text content."
        ]
    )
    response = client.post(
        "/api/documents/upload",
        files={"file": ("../../../etc/shadow/../../traversal_attempt.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "traversal_attempt.pdf"


def test_non_pdf_with_spoofed_filename_and_content_type_rejected() -> None:
    """Verify filename and Content-Type header alone are not trusted without %PDF- signature."""
    fake_bytes = b"<html><body>This is an HTML landing page, not a PDF binary.</body></html>"
    response = client.post(
        "/api/documents/upload",
        files={"file": ("spoofed_paper.pdf", fake_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["status_code"] == 400
    assert "%pdf-" in body["message"].lower() or "format" in body["message"].lower()


def test_malformed_corrupted_pdf_rejected() -> None:
    """Verify a file with a %PDF- header but corrupted body returns a clear 400 error."""
    corrupted_bytes = b"%PDF-1.7\n1 0 obj\n<<<corrupted binary content not parseable>>>\n%%EOF"
    response = client.post(
        "/api/documents/upload",
        files={"file": ("corrupted.pdf", corrupted_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["status_code"] == 400
    assert "corrupted" in body["message"].lower() or "malformed" in body["message"].lower()


def test_encrypted_pdf_rejected() -> None:
    """Verify password-protected/encrypted PDFs return a clear 400 error."""
    encrypted_bytes = _build_encrypted_pdf_bytes(
        "Confidential research content that is encrypted with AES-256."
    )
    response = client.post(
        "/api/documents/upload",
        files={"file": ("encrypted.pdf", encrypted_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["status_code"] == 400
    assert "encrypted" in body["message"].lower() or "password" in body["message"].lower()


def test_empty_file_rejected() -> None:
    """Verify uploading a 0-byte file returns a clear 400 error."""
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["status_code"] == 400
    assert "empty" in body["message"].lower()


def test_oversized_upload_rejected() -> None:
    """Verify uploads exceeding the maximum file size limit return HTTP 413."""
    small_limit_service = PDFIngestionService(max_file_size_bytes=512)
    app.dependency_overrides[get_pdf_ingestion_service] = lambda: small_limit_service
    try:
        pdf_bytes = _build_valid_pdf_bytes(
            [
                "This valid PDF document is larger than 512 bytes so that we can deterministically "
                "verify the streaming file size limit check without allocating 20 MB in tests."
            ]
        )
        assert len(pdf_bytes) > 512
        response = client.post(
            "/api/documents/upload",
            files={"file": ("large.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 413
        body = response.json()
        assert body["status_code"] == 413
        assert "exceeds the maximum allowed size" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_missing_text_and_scanned_pdf_detection() -> None:
    """Verify PDFs with too little text or scanned image-only pages return 422 and mention OCR."""
    # 1. Blank / near-empty text PDF (no images, fewer than 50 characters)
    low_text_pdf = _build_valid_pdf_bytes(["Short"])
    res_low = client.post(
        "/api/documents/upload",
        files={"file": ("blank_page.pdf", low_text_pdf, "application/pdf")},
    )
    assert res_low.status_code == 422
    body_low = res_low.json()
    assert body_low["status_code"] == 422
    assert "too little extractable text" in body_low["message"].lower()
    assert "ocr" in body_low["message"].lower()

    # 2. Scanned image-only PDF (contains embedded image, 0 selectable text)
    scanned_pdf = _build_scanned_image_only_pdf_bytes()
    res_scanned = client.post(
        "/api/documents/upload",
        files={"file": ("scanned_paper.pdf", scanned_pdf, "application/pdf")},
    )
    assert res_scanned.status_code == 422
    body_scanned = res_scanned.json()
    assert body_scanned["status_code"] == 422
    assert "scanned" in body_scanned["message"].lower()
    assert "ocr may be required" in body_scanned["message"].lower()
