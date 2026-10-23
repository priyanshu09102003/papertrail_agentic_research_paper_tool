"""Structured scientific-paper extraction engine with ground-truth passage verification."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re

from pydantic import BaseModel, Field, model_validator

from app.config import (
    EXTRACTION_CHUNK_RETRIES,
    EXTRACTION_MAX_CHUNK_CHARS,
    EXTRACTION_MAX_CHUNKS_PER_DOC,
    EXTRACTION_MAX_TOKENS_PER_CHUNK,
    GEMINI_MAX_TOKENS_PER_CHUNK,
)
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMProviderError
from app.schemas import (
    ExtractedClaim,
    ExtractedDocument,
    ExtractedPage,
    QuantitativeResult,
    ScientificExtractionStatus,
    ScientificPaperExtraction,
    SupportingPassage,
)

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")
_PLACEHOLDER_NULL_STRINGS = {
    "",
    "none",
    "null",
    "n/a",
    "na",
    "unknown",
    "not reported",
    "not mentioned",
    "not specified",
    "not stated",
    "not applicable",
    "not provided",
    "not available",
    "unspecified",
    "string",
    "text value",
}


@dataclass(frozen=True)
class DocumentChunk:
    """Bounded text chunk preserving source 1-based page numbers."""

    chunk_index: int
    page_numbers: list[int]
    text: str


class RawClaimItem(BaseModel):
    """Intermediate LLM schema for a single finding/claim."""

    author_claim: str = ""
    model_interpretation: str | None = None
    supporting_quote: str | None = None
    page_number: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: object) -> object:
        if isinstance(data, str):
            return {"author_claim": data}
        if isinstance(data, dict):
            out = dict(data)
            if "claim" in out and not out.get("author_claim"):
                out["author_claim"] = out.pop("claim")
            if "interpretation" in out and not out.get("model_interpretation"):
                out["model_interpretation"] = out.pop("interpretation")
            if "quote" in out and not out.get("supporting_quote"):
                out["supporting_quote"] = out.pop("quote")
            if "page" in out and out.get("page_number") is None:
                out["page_number"] = out.pop("page")
            if out.get("author_claim") is None:
                out["author_claim"] = ""
            elif not isinstance(out.get("author_claim"), str):
                out["author_claim"] = str(out["author_claim"])
            return out
        return data


class RawQuantitativeItem(BaseModel):
    """Intermediate LLM schema for a quantitative result."""

    metric_name: str = ""
    value: str = ""
    unit: str | None = None
    context: str | None = None
    supporting_quote: str = ""
    page_number: int = 1

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: object) -> object:
        if isinstance(data, dict):
            out = dict(data)
            if "metric" in out and not out.get("metric_name"):
                out["metric_name"] = out.pop("metric")
            if "quote" in out and not out.get("supporting_quote"):
                out["supporting_quote"] = out.pop("quote")
            if "page" in out and "page_number" not in out:
                out["page_number"] = out.pop("page")
            for str_key in ("metric_name", "value", "supporting_quote"):
                v = out.get(str_key)
                if v is None:
                    out[str_key] = ""
                elif isinstance(v, (int, float)):
                    out[str_key] = str(v)
            for opt_key in ("unit", "context"):
                v = out.get(opt_key)
                if isinstance(v, (int, float)):
                    out[opt_key] = str(v)
            if out.get("page_number") is None or not isinstance(out.get("page_number"), int):
                out["page_number"] = 1
            return out
        return data


class RawSupportingPassageItem(BaseModel):
    """Intermediate LLM schema for an additional supporting evidence passage."""

    field_supported: str = "methodology"
    quote: str = ""
    page_number: int = 1

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: object) -> object:
        if isinstance(data, dict):
            out = dict(data)
            if out.get("field_supported") is None:
                out["field_supported"] = "general"
            if out.get("quote") is None:
                out["quote"] = ""
            if out.get("page_number") is None or not isinstance(out.get("page_number"), int):
                out["page_number"] = 1
            return out
        return data


_CHUNK_KEY_ALIASES: dict[str, str] = {
    "title": "paper_title",
    "question": "research_question",
    "objective": "study_objective",
    "methodology": "research_methodology",
    "datasets": "dataset_or_material",
    "sample_quote": "sample_size_quote",
    "sample_page": "sample_size_page",
    "architecture": "model_architecture_or_intervention",
    "metrics": "evaluation_metrics",
    "findings": "main_findings",
    "results": "quantitative_results",
    "limitations": "authors_stated_limitations",
}


class ChunkExtractionLLMOutput(BaseModel):
    """Schema validated against each chunk's LLM JSON output."""

    __compact_json_template__ = (
        '{"title":"","methodology":"","datasets":[""],"sample_size":"",'
        '"architecture":"","baselines":[""],"metrics":[""],'
        '"result_metric":"","result_value":"","result_unit":"",'
        '"finding_claim":"","finding_interpretation":"","finding_quote":"",'
        '"future_work":[""],"objective":null,"question":null,"limitations":[]}'
    )

    paper_title: str | None = None
    research_question: str | None = None
    study_objective: str | None = None
    research_methodology: str | None = None
    dataset_or_material: list[str] = Field(default_factory=list)
    sample_size: str | None = None
    sample_size_quote: str | None = None
    sample_size_page: int | None = None
    model_architecture_or_intervention: str | None = None
    baselines: list[str] = Field(default_factory=list)
    evaluation_metrics: list[str] = Field(default_factory=list)
    main_findings: list[RawClaimItem] = Field(default_factory=list)
    quantitative_results: list[RawQuantitativeItem] = Field(default_factory=list)
    authors_stated_limitations: list[str] = Field(default_factory=list)
    future_work: list[str] = Field(default_factory=list)
    supporting_passages: list[RawSupportingPassageItem] = Field(
        default_factory=list,
        json_schema_extra={"exclude_from_prompt": True},
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for short_key, full_key in _CHUNK_KEY_ALIASES.items():
            if short_key in out and out.get(full_key) is None:
                out[full_key] = out.pop(short_key)

        # Map flat finding_* keys into main_findings list if main_findings not already populated
        f_claim = out.pop("finding_claim", None)
        f_interp = out.pop("finding_interpretation", None)
        f_quote = out.pop("finding_quote", None)
        f_page = out.pop("finding_page", None)
        if f_claim and not out.get("main_findings"):
            out["main_findings"] = [
                {
                    "author_claim": f_claim,
                    "model_interpretation": f_interp,
                    "supporting_quote": f_quote,
                    "page_number": f_page,
                }
            ]

        # Map flat result_* keys into quantitative_results list if quantitative_results not already populated
        r_metric = out.pop("result_metric", None)
        r_value = out.pop("result_value", None)
        r_unit = out.pop("result_unit", None)
        r_quote = out.pop("result_quote", None)
        r_page = out.pop("result_page", None)
        if r_metric and r_value is not None and not out.get("quantitative_results"):
            out["quantitative_results"] = [
                {
                    "metric_name": r_metric,
                    "value": str(r_value),
                    "unit": r_unit,
                    "supporting_quote": r_quote or "",
                    "page_number": r_page or 1,
                }
            ]

        for str_field in (
            "paper_title",
            "research_question",
            "study_objective",
            "research_methodology",
            "sample_size",
            "sample_size_quote",
            "model_architecture_or_intervention",
        ):
            v = out.get(str_field)
            if isinstance(v, (int, float)):
                out[str_field] = str(v)
            elif isinstance(v, list):
                out[str_field] = "; ".join(str(x) for x in v if x) or None

        for list_str_field in (
            "dataset_or_material",
            "baselines",
            "evaluation_metrics",
            "authors_stated_limitations",
            "future_work",
        ):
            v = out.get(list_str_field)
            if v is None:
                out[list_str_field] = []
            elif isinstance(v, (str, int, float)):
                out[list_str_field] = [str(v)] if str(v).strip() else []

        for obj_list_field in ("main_findings", "quantitative_results", "supporting_passages"):
            v = out.get(obj_list_field)
            if v is None:
                out[obj_list_field] = []
            elif isinstance(v, dict):
                out[obj_list_field] = [v]
        return out


_EXTRACTION_SYSTEM_PROMPT = (
    "Extract ONLY facts explicitly stated in the text. "
    "Use \"\" or [] for any field not mentioned in the text. "
    "Copy sample_quote, finding_quote, and result_quote verbatim as exact substrings from the text."
)


def _clean_nullable_text(value: str | None) -> str | None:
    """Return None if a string is empty or a placeholder for missing data."""
    if value is None or not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped.lower().strip(".:;-_") in _PLACEHOLDER_NULL_STRINGS:
        return None
    return stripped


def _clean_string_list(items: list[str] | None) -> list[str]:
    """Filter out placeholders and deduplicate while preserving order."""
    if not items or not isinstance(items, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _clean_nullable_text(item)
        if cleaned is None:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def chunk_document_pages(
    pages: list[ExtractedPage],
    *,
    max_chunk_chars: int = EXTRACTION_MAX_CHUNK_CHARS,
    max_chunks: int = EXTRACTION_MAX_CHUNKS_PER_DOC,
) -> tuple[list[DocumentChunk], bool]:
    """Split document pages into bounded text chunks while preserving [Page N] markers.

    Returns (chunks, was_truncated).
    """
    raw_segments: list[tuple[int, str]] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        header = f"[Page {page.page_number}]\n"
        budget = max(200, max_chunk_chars - len(header) - 2)
        if len(text) <= budget:
            raw_segments.append((page.page_number, f"{header}{text}"))
        else:
            # Split oversized single page along paragraph/line boundaries
            start = 0
            while start < len(text):
                end = min(len(text), start + budget)
                if end < len(text):
                    newline_pos = text.rfind("\n", start, end)
                    space_pos = text.rfind(" ", start, end)
                    split_at = newline_pos if newline_pos > start + 100 else space_pos
                    if split_at > start + 100:
                        end = split_at
                slice_text = text[start:end].strip()
                if slice_text:
                    raw_segments.append((page.page_number, f"{header}{slice_text}"))
                start = end

    chunks: list[DocumentChunk] = []
    current_pages: list[int] = []
    current_blocks: list[str] = []
    current_len = 0

    for page_num, block in raw_segments:
        addition_len = len(block) + (2 if current_blocks else 0)
        if current_blocks and (current_len + addition_len > max_chunk_chars):
            chunks.append(
                DocumentChunk(
                    chunk_index=len(chunks) + 1,
                    page_numbers=sorted(set(current_pages)),
                    text="\n\n".join(current_blocks),
                )
            )
            current_pages = [page_num]
            current_blocks = [block]
            current_len = len(block)
        else:
            current_pages.append(page_num)
            current_blocks.append(block)
            current_len += addition_len

    if current_blocks:
        chunks.append(
            DocumentChunk(
                chunk_index=len(chunks) + 1,
                page_numbers=sorted(set(current_pages)),
                text="\n\n".join(current_blocks),
            )
        )

    was_truncated = len(chunks) > max_chunks
    return chunks[:max_chunks], was_truncated


def verify_quote_in_pages(
    candidate_quote: str | None,
    claimed_page: int | None,
    *,
    page_map: dict[int, str],
    chunk_pages: list[int] | None = None,
) -> tuple[int, str] | None:
    """Verify that candidate_quote exists in the source pages and return (verified_page_number, quote).

    Never fabricates page numbers or quotations. If the quote does not appear in
    any source page, returns None.
    """
    cleaned_quote = _clean_nullable_text(candidate_quote)
    if cleaned_quote is None or len(cleaned_quote) < 6:
        return None

    normalized_quote = _WHITESPACE_RE.sub(" ", cleaned_quote).strip()
    quote_lower = normalized_quote.lower()

    # Build ordered list of candidate pages to inspect: claimed_page -> chunk_pages -> all pages
    search_order: list[int] = []
    if claimed_page is not None and claimed_page in page_map:
        search_order.append(claimed_page)
    if chunk_pages:
        for p in chunk_pages:
            if p in page_map and p not in search_order:
                search_order.append(p)
    for p in sorted(page_map.keys()):
        if p not in search_order:
            search_order.append(p)

    for page_num in search_order:
        page_text = page_map[page_num]
        normalized_page = _WHITESPACE_RE.sub(" ", page_text).strip()
        pos = normalized_page.lower().find(quote_lower)
        if pos != -1:
            exact_slice = normalized_page[pos : pos + len(normalized_quote)]
            return page_num, exact_slice

    return None


def _find_verbatim_sentence_with_value(
    exact_val: str,
    metric_name: str | None,
    *,
    page_map: dict[int, str],
    chunk_pages: list[int] | None = None,
) -> tuple[int, str] | None:
    """Locate the exact verbatim sentence on a source page containing exact_val (and metric_name if present)."""
    search_order: list[int] = []
    if chunk_pages:
        for p in chunk_pages:
            if p in page_map and p not in search_order:
                search_order.append(p)
    for p in sorted(page_map.keys()):
        if p not in search_order:
            search_order.append(p)

    for page_num in search_order:
        normalized_page = _WHITESPACE_RE.sub(" ", page_map[page_num]).strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized_page) if s.strip()]
        # Prefer sentence containing both exact_val and metric_name
        if metric_name:
            for sent in sentences:
                if exact_val in sent and metric_name.lower() in sent.lower():
                    return page_num, sent
        for sent in sentences:
            if exact_val in sent:
                return page_num, sent
    return None


def _verify_sample_size_in_pages(
    raw_sample_size: str | None,
    raw_quote: str | None,
    raw_page: int | None,
    *,
    page_map: dict[int, str],
    chunk_pages: list[int],
) -> tuple[str | None, SupportingPassage | None, str | None]:
    """Verify that an extracted sample_size is genuinely present in the source text."""
    cleaned_size = _clean_nullable_text(raw_sample_size)
    if cleaned_size is None:
        return None, None, None

    all_normalized_text = " ".join(
        _WHITESPACE_RE.sub(" ", page_map[p]).lower() for p in sorted(page_map.keys())
    )

    # Check if the sample_size contains numeric tokens; every numeric token must exist in source text
    numbers = _NUMBER_TOKEN_RE.findall(cleaned_size)
    if numbers:
        for num in numbers:
            if num not in all_normalized_text:
                return (
                    None,
                    None,
                    f"Discarded unverified sample_size '{cleaned_size}' because number '{num}' was not found in source text.",
                )
    elif cleaned_size.lower() not in all_normalized_text:
        return (
            None,
            None,
            f"Discarded unverified sample_size '{cleaned_size}' not found in source text.",
        )

    verified_quote = verify_quote_in_pages(
        raw_quote,
        raw_page,
        page_map=page_map,
        chunk_pages=chunk_pages,
    ) or verify_quote_in_pages(
        cleaned_size,
        raw_page,
        page_map=page_map,
        chunk_pages=chunk_pages,
    )
    passage = None
    if verified_quote is not None:
        v_page, v_text = verified_quote
        passage = SupportingPassage(
            document_id="",  # Filled by caller
            page_number=v_page,
            field_supported="sample_size",
            quote=v_text,
        )
    return cleaned_size, passage, None


def _detect_abstract_only(document: ExtractedDocument) -> bool:
    """Detect if the document is likely just an abstract or short summary rather than a full paper."""
    if document.page_count > 1:
        return False
    if document.total_words < 350:
        return True
    full_text_lower = " ".join(p.text.lower() for p in document.pages)
    has_methods_heading = any(
        marker in full_text_lower
        for marker in ("\nmethods", "\nmethodology", "\nexperimental setup", "\nmaterials and methods")
    )
    return not has_methods_heading and document.total_words < 600


class ScientificPaperExtractor:
    """Extracts structured scientific methodology, results, and verified evidence from an ExtractedDocument."""

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        *,
        max_chunk_chars: int = EXTRACTION_MAX_CHUNK_CHARS,
        max_chunks_per_doc: int = EXTRACTION_MAX_CHUNKS_PER_DOC,
        chunk_retries: int = EXTRACTION_CHUNK_RETRIES,
    ) -> None:
        self._llm = llm_provider
        self._max_chunk_chars = max_chunk_chars
        self._max_chunks_per_doc = max_chunks_per_doc
        self._chunk_retries = chunk_retries

    async def extract_document(
        self, document: ExtractedDocument
    ) -> ScientificPaperExtraction:
        """Process a document in bounded chunks and merge verified scientific findings."""
        now_iso = datetime.now(timezone.utc).isoformat()
        page_map: dict[int, str] = {p.page_number: p.text for p in document.pages}

        chunks, was_truncated = chunk_document_pages(
            document.pages,
            max_chunk_chars=self._max_chunk_chars,
            max_chunks=self._max_chunks_per_doc,
        )

        warnings: list[str] = []
        is_abstract_only = _detect_abstract_only(document)
        if is_abstract_only:
            warnings.append(
                "Source text appears to be an abstract or short summary; an abstract is not "
                "equivalent to a complete methodological review."
            )
        if was_truncated:
            warnings.append(
                f"Document exceeded maximum chunk limit and was truncated to the first "
                f"{self._max_chunks_per_doc} chunks."
            )

        if not chunks:
            return ScientificPaperExtraction(
                extraction_id=f"ext_{document.document_id}",
                document_id=document.document_id,
                is_abstract_only=is_abstract_only,
                extraction_status="failed",
                chunk_count=1,
                failed_chunks=1,
                warnings=["Document contained no extractable page chunks."],
                created_at=now_iso,
                updated_at=now_iso,
            )

        paper_title: str | None = None
        research_question: str | None = None
        study_objective: str | None = None
        research_methodology: str | None = None
        dataset_or_material: list[str] = []
        sample_size: str | None = None
        model_architecture_or_intervention: str | None = None
        baselines: list[str] = []
        evaluation_metrics: list[str] = []
        main_findings: list[ExtractedClaim] = []
        quantitative_results: list[QuantitativeResult] = []
        authors_stated_limitations: list[str] = []
        future_work: list[str] = []
        supporting_passages: list[SupportingPassage] = []
        seen_passages: set[tuple[int, str]] = set()

        failed_chunks = 0

        chunk_max_tokens = (
            GEMINI_MAX_TOKENS_PER_CHUNK
            if getattr(self._llm, "provider_name", "") == "gemini"
            else EXTRACTION_MAX_TOKENS_PER_CHUNK
        )

        for chunk in chunks:
            prompt = (
                "Extract facts from the text below into single-line JSON "
                "(keep each string under 8 words; use \"\" or [] if not stated; copy finding_quote verbatim):\n"
                f"{chunk.text}"
            )
            try:
                chunk_out = await self._llm.generate_structured(
                    prompt,
                    ChunkExtractionLLMOutput,
                    system_prompt=None,
                    max_tokens=chunk_max_tokens,
                    max_retries=self._chunk_retries,
                )
            except LLMProviderError as exc:
                failed_chunks += 1
                logger.warning(
                    "Chunk %d/%d extraction failed for doc=%s: %s",
                    chunk.chunk_index,
                    len(chunks),
                    document.document_id,
                    type(exc).__name__,
                )
                warnings.append(
                    f"Chunk {chunk.chunk_index} (pages {chunk.page_numbers}) failed extraction: {exc.message}"
                )
                continue

            if paper_title is None:
                paper_title = _clean_nullable_text(chunk_out.paper_title)
            if research_question is None:
                research_question = _clean_nullable_text(chunk_out.research_question)
            if study_objective is None:
                study_objective = _clean_nullable_text(chunk_out.study_objective)
            if research_methodology is None:
                research_methodology = _clean_nullable_text(chunk_out.research_methodology)
            if model_architecture_or_intervention is None:
                model_architecture_or_intervention = _clean_nullable_text(
                    chunk_out.model_architecture_or_intervention
                )

            dataset_or_material = _clean_string_list(
                dataset_or_material + chunk_out.dataset_or_material
            )
            baselines = _clean_string_list(baselines + chunk_out.baselines)
            evaluation_metrics = _clean_string_list(
                evaluation_metrics + chunk_out.evaluation_metrics
            )
            authors_stated_limitations = _clean_string_list(
                authors_stated_limitations + chunk_out.authors_stated_limitations
            )
            future_work = _clean_string_list(future_work + chunk_out.future_work)

            # Verify sample_size against ground-truth text
            if sample_size is None and chunk_out.sample_size is not None:
                verified_size, size_passage, size_warn = _verify_sample_size_in_pages(
                    chunk_out.sample_size,
                    chunk_out.sample_size_quote,
                    chunk_out.sample_size_page,
                    page_map=page_map,
                    chunk_pages=chunk.page_numbers,
                )
                if size_warn:
                    warnings.append(size_warn)
                if verified_size is not None:
                    sample_size = verified_size
                if size_passage is not None:
                    size_passage = size_passage.model_copy(
                        update={"document_id": document.document_id}
                    )
                    key = (size_passage.page_number, size_passage.quote.lower())
                    if key not in seen_passages:
                        seen_passages.add(key)
                        supporting_passages.append(size_passage)

            # Verify main_findings and enforce separation of author_claim vs model_interpretation
            for raw_claim in chunk_out.main_findings:
                cleaned_claim = _clean_nullable_text(raw_claim.author_claim)
                if cleaned_claim is None:
                    continue
                cleaned_interp = _clean_nullable_text(raw_claim.model_interpretation)
                verified_quote = verify_quote_in_pages(
                    raw_claim.supporting_quote,
                    raw_claim.page_number,
                    page_map=page_map,
                    chunk_pages=chunk.page_numbers,
                )
                if verified_quote is not None:
                    v_page, v_quote = verified_quote
                    main_findings.append(
                        ExtractedClaim(
                            author_claim=cleaned_claim,
                            model_interpretation=cleaned_interp,
                            supporting_quote=v_quote,
                            page_number=v_page,
                            verified_in_source=True,
                        )
                    )
                    p_key = (v_page, v_quote.lower())
                    if p_key not in seen_passages:
                        seen_passages.add(p_key)
                        supporting_passages.append(
                            SupportingPassage(
                                document_id=document.document_id,
                                page_number=v_page,
                                field_supported="main_findings",
                                quote=v_quote,
                            )
                        )
                else:
                    # Claim has no verified supporting passage: never store as verified evidence!
                    warnings.append(
                        f"Claim '{cleaned_claim[:60]}...' lacked a verifiable source quote and was marked unverified."
                    )
                    main_findings.append(
                        ExtractedClaim(
                            author_claim=cleaned_claim,
                            model_interpretation=cleaned_interp,
                            supporting_quote=None,
                            page_number=None,
                            verified_in_source=False,
                        )
                    )

            # Verify quantitative results (exact value and quote must appear on source page)
            for raw_q in chunk_out.quantitative_results:
                metric_name = _clean_nullable_text(raw_q.metric_name)
                exact_val = _clean_nullable_text(raw_q.value)
                unit_val = _clean_nullable_text(raw_q.unit)
                context_val = _clean_nullable_text(raw_q.context)
                if metric_name is None or exact_val is None:
                    continue

                if _clean_nullable_text(raw_q.supporting_quote) is not None:
                    verified_q = verify_quote_in_pages(
                        raw_q.supporting_quote,
                        raw_q.page_number,
                        page_map=page_map,
                        chunk_pages=chunk.page_numbers,
                    )
                else:
                    verified_q = _find_verbatim_sentence_with_value(
                        exact_val,
                        metric_name,
                        page_map=page_map,
                        chunk_pages=chunk.page_numbers,
                    )
                if verified_q is None:
                    warnings.append(
                        f"Discarded quantitative result '{metric_name}={exact_val}' because its supporting quote was not found in source text."
                    )
                    continue

                v_page, v_quote = verified_q
                page_text_norm = _WHITESPACE_RE.sub(" ", page_map[v_page])
                if exact_val not in v_quote and exact_val not in page_text_norm:
                    warnings.append(
                        f"Discarded quantitative result '{metric_name}={exact_val}' because numeric value '{exact_val}' was not present on page {v_page}."
                    )
                    continue

                if unit_val is not None and unit_val.lower() not in page_text_norm.lower():
                    unit_val = None

                quantitative_results.append(
                    QuantitativeResult(
                        metric_name=metric_name,
                        value=exact_val,
                        unit=unit_val,
                        context=context_val,
                        supporting_quote=v_quote,
                        page_number=v_page,
                    )
                )
                p_key = (v_page, v_quote.lower())
                if p_key not in seen_passages:
                    seen_passages.add(p_key)
                    supporting_passages.append(
                        SupportingPassage(
                            document_id=document.document_id,
                            page_number=v_page,
                            field_supported="quantitative_results",
                            quote=v_quote,
                        )
                    )

            # Verify additional supporting passages
            for raw_sp in chunk_out.supporting_passages:
                verified_sp = verify_quote_in_pages(
                    raw_sp.quote,
                    raw_sp.page_number,
                    page_map=page_map,
                    chunk_pages=chunk.page_numbers,
                )
                if verified_sp is not None:
                    v_page, v_quote = verified_sp
                    p_key = (v_page, v_quote.lower())
                    if p_key not in seen_passages:
                        seen_passages.add(p_key)
                        supporting_passages.append(
                            SupportingPassage(
                                document_id=document.document_id,
                                page_number=v_page,
                                field_supported=_clean_nullable_text(raw_sp.field_supported)
                                or "general",
                                quote=v_quote,
                            )
                        )

        # Determine overall extraction status
        if failed_chunks == len(chunks):
            status: ScientificExtractionStatus = "failed"
        elif failed_chunks > 0:
            status = "partial"
        else:
            status = "completed"

        verified_pages = sorted({sp.page_number for sp in supporting_passages})

        return ScientificPaperExtraction(
            extraction_id=f"ext_{document.document_id}",
            document_id=document.document_id,
            paper_title=paper_title,
            is_abstract_only=is_abstract_only,
            research_question=research_question,
            study_objective=study_objective,
            research_methodology=research_methodology,
            dataset_or_material=dataset_or_material,
            sample_size=sample_size,
            model_architecture_or_intervention=model_architecture_or_intervention,
            baselines=baselines,
            evaluation_metrics=evaluation_metrics,
            main_findings=main_findings,
            quantitative_results=quantitative_results,
            authors_stated_limitations=authors_stated_limitations,
            future_work=future_work,
            supporting_passages=supporting_passages,
            page_numbers=verified_pages,
            extraction_status=status,
            chunk_count=len(chunks),
            failed_chunks=failed_chunks,
            warnings=warnings,
            created_at=now_iso,
            updated_at=now_iso,
        )
