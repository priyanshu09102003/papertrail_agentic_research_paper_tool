"""Custom exceptions for external scholarly API clients and PDF ingestion."""

from http import HTTPStatus


class UpstreamAPIError(Exception):
    """Base exception for errors originating from upstream discovery APIs."""

    def __init__(
        self,
        source: str,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.source = source
        self.message = message
        self.status_code = status_code


class UpstreamTimeoutError(UpstreamAPIError):
    """Raised when an upstream API request times out."""


class UpstreamRateLimitError(UpstreamAPIError):
    """Raised when an upstream API returns HTTP 429 Too Many Requests."""

    def __init__(
        self,
        source: str,
        message: str = "Upstream rate limit exceeded.",
        retry_after: str | None = None,
    ) -> None:
        super().__init__(source=source, message=message, status_code=429)
        self.retry_after = retry_after


class UpstreamResponseError(UpstreamAPIError):
    """Raised when an upstream API returns an HTTP error, network failure, or invalid JSON."""


class PDFIngestionError(Exception):
    """Base exception for PDF upload validation and extraction errors."""

    def __init__(
        self,
        message: str,
        status_code: int = HTTPStatus.BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PDFFileTooLargeError(PDFIngestionError):
    """Raised when an uploaded PDF exceeds the configured maximum byte size."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        )


class EmptyPDFError(PDFIngestionError):
    """Raised when an uploaded file is empty (0 bytes) or has 0 pages."""

    def __init__(self, message: str = "The uploaded PDF file is empty.") -> None:
        super().__init__(message=message, status_code=HTTPStatus.BAD_REQUEST)


class UnsupportedFileFormatError(PDFIngestionError):
    """Raised when an uploaded file is not a valid PDF document."""

    def __init__(
        self,
        message: str = "Unsupported file format. Only valid PDF files (%PDF-) are accepted.",
    ) -> None:
        super().__init__(message=message, status_code=HTTPStatus.BAD_REQUEST)


class CorruptedPDFError(PDFIngestionError):
    """Raised when a file has a PDF header but is corrupted or cannot be parsed."""

    def __init__(
        self,
        message: str = "The uploaded PDF file is corrupted or malformed and could not be parsed.",
    ) -> None:
        super().__init__(message=message, status_code=HTTPStatus.BAD_REQUEST)


class EncryptedPDFError(PDFIngestionError):
    """Raised when a PDF is encrypted or password-protected."""

    def __init__(
        self,
        message: str = "The uploaded PDF is encrypted or password-protected and cannot be processed.",
    ) -> None:
        super().__init__(message=message, status_code=HTTPStatus.BAD_REQUEST)


class InsufficientTextPDFError(PDFIngestionError):
    """Raised when a PDF contains too little extractable text for analysis."""

    def __init__(
        self,
        message: str = (
            "The uploaded PDF contains too little extractable text. "
            "If this is a scanned document, OCR may be required."
        ),
    ) -> None:
        super().__init__(
            message=message,
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )


class ScannedPDFError(InsufficientTextPDFError):
    """Raised when a PDF appears to be a scanned image document requiring OCR."""

    def __init__(
        self,
        message: str = (
            "The uploaded PDF appears to be a scanned document containing images "
            "with little or no selectable text. OCR may be required before processing."
        ),
    ) -> None:
        super().__init__(message=message)
