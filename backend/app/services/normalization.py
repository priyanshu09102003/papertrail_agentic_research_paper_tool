"""Normalization helpers for DOIs, abstracts, URLs, and paper identifiers."""

import hashlib
import html
import re
from urllib.parse import urlparse

from app.schemas import PaperSource

_DOI_PREFIX_RE = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)",
    re.IGNORECASE,
)
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_XML_TAG_RE = re.compile(r"<[^>]+>")
_LEADING_ABSTRACT_LABEL_RE = re.compile(r"^abstract[\s:.\-—]*", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_doi(raw_doi: str | None) -> str | None:
    """Normalize a DOI string to lowercase '10.xxxx/...' format, or return None."""
    if not raw_doi or not isinstance(raw_doi, str):
        return None

    cleaned = _DOI_PREFIX_RE.sub("", raw_doi.strip()).strip().lower()
    if not cleaned or not _DOI_PATTERN.match(cleaned):
        return None
    return cleaned


def clean_http_url(raw_url: str | None) -> str | None:
    """Validate and return a clean http/https URL, or None if invalid."""
    if not raw_url or not isinstance(raw_url, str):
        return None

    candidate = raw_url.strip()
    if not candidate:
        return None

    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def is_explicit_pdf_url(
    raw_url: str | None,
    *,
    landing_page_url: str | None = None,
    content_type: str | None = None,
    from_dedicated_pdf_field: bool = False,
) -> str | None:
    """Verify whether a candidate URL is an explicitly established open-access PDF URL.

    Never assumes that an open-access landing page is a directly downloadable PDF.
    """
    valid_url = clean_http_url(raw_url)
    if not valid_url:
        return None

    normalized_content_type = (content_type or "").strip().lower()
    if normalized_content_type and "html" in normalized_content_type:
        return None

    parsed_path = urlparse(valid_url).path.lower()
    ends_with_pdf = parsed_path.endswith(".pdf") or "/pdf/" in parsed_path
    is_pdf_mime = normalized_content_type == "application/pdf"

    # Do not treat a landing page URL as a direct PDF unless it explicitly ends with .pdf
    if landing_page_url and valid_url.rstrip("/") == landing_page_url.strip().rstrip("/"):
        if not ends_with_pdf and not is_pdf_mime:
            return None

    if from_dedicated_pdf_field or is_pdf_mime or ends_with_pdf:
        return valid_url

    return None


def reconstruct_openalex_abstract(
    inverted_index: dict[str, list[int]] | None,
) -> str | None:
    """Reconstruct a plain-text abstract from an OpenAlex abstract_inverted_index."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return None

    position_to_word: dict[int, str] = {}
    for word, positions in inverted_index.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int) and pos >= 0:
                position_to_word[pos] = word

    if not position_to_word:
        return None

    ordered_words = [
        position_to_word[idx] for idx in sorted(position_to_word.keys())
    ]
    reconstructed = _WHITESPACE_RE.sub(" ", " ".join(ordered_words)).strip()
    return reconstructed if reconstructed else None


def clean_crossref_abstract(raw_abstract: str | None) -> str | None:
    """Strip JATS/XML tags and normalize whitespace from a Crossref abstract."""
    if not raw_abstract or not isinstance(raw_abstract, str):
        return None

    without_tags = _XML_TAG_RE.sub(" ", raw_abstract)
    unescaped = html.unescape(without_tags)
    collapsed = _WHITESPACE_RE.sub(" ", unescaped).strip()
    cleaned = _LEADING_ABSTRACT_LABEL_RE.sub("", collapsed).strip()
    return cleaned if cleaned else None


def build_paper_id(
    *,
    source: PaperSource,
    doi: str | None,
    upstream_id: str | None,
    title: str,
) -> str:
    """Create a deterministic internal identifier for a normalized Paper."""
    if doi:
        return f"doi:{doi}"

    if upstream_id and isinstance(upstream_id, str) and upstream_id.strip():
        cleaned_id = upstream_id.strip()
        if cleaned_id.startswith("https://openalex.org/"):
            cleaned_id = cleaned_id.removeprefix("https://openalex.org/")
        return f"{source}:{cleaned_id}"

    digest = hashlib.sha256(f"{source}:{title.strip().lower()}".encode("utf-8")).hexdigest()[:12]
    return f"{source}:{digest}"
