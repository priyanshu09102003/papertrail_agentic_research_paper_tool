"""Discovery service combining OpenAlex and Crossref results with DOI deduplication and caching."""

import asyncio
import logging

from app.config import MAX_CONCURRENT_UPSTREAM_REQUESTS
from app.schemas import Paper, PaperSearchResponse
from app.services.cache import SearchCache
from app.services.crossref_client import CrossrefClient
from app.services.exceptions import (
    UpstreamAPIError,
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
)
from app.services.normalization import normalize_doi
from app.services.openalex_client import OpenAlexClient

logger = logging.getLogger(__name__)


def deduplicate_papers(papers: list[Paper]) -> list[Paper]:
    """Deduplicate papers primarily by normalized DOI, merging non-null complementary metadata.

    Records without a DOI are preserved unless they have an identical normalized
    (source, id) or identical normalized title + publication year.
    """
    deduplicated: list[Paper] = []
    doi_index: dict[str, int] = {}
    fallback_keys: set[tuple[str, int | None]] = set()

    for paper in papers:
        normalized_doi = normalize_doi(paper.doi)
        if normalized_doi is not None:
            if paper.doi != normalized_doi:
                paper = paper.model_copy(update={"doi": normalized_doi})

            existing_idx = doi_index.get(normalized_doi)
            if existing_idx is not None:
                deduplicated[existing_idx] = _merge_duplicate_records(
                    primary=deduplicated[existing_idx],
                    secondary=paper,
                )
                continue

            doi_index[normalized_doi] = len(deduplicated)
            deduplicated.append(paper)
        else:
            title_key = (" ".join(paper.title.lower().split()), paper.publication_year)
            if title_key in fallback_keys:
                continue
            fallback_keys.add(title_key)
            deduplicated.append(paper)

    return deduplicated


def _merge_duplicate_records(primary: Paper, secondary: Paper) -> Paper:
    """Fill missing fields on the primary record from a secondary duplicate record without fabricating."""
    return Paper(
        id=primary.id,
        title=primary.title,
        authors=primary.authors if primary.authors else secondary.authors,
        publication_year=(
            primary.publication_year
            if primary.publication_year is not None
            else secondary.publication_year
        ),
        doi=primary.doi or secondary.doi,
        abstract=primary.abstract if primary.abstract is not None else secondary.abstract,
        source=primary.source,
        landing_page_url=(
            primary.landing_page_url
            if primary.landing_page_url is not None
            else secondary.landing_page_url
        ),
        open_access_pdf_url=(
            primary.open_access_pdf_url
            if primary.open_access_pdf_url is not None
            else secondary.open_access_pdf_url
        ),
    )


class PaperDiscoveryService:
    """Coordinates OpenAlex and Crossref queries, caching, and normalization."""

    def __init__(
        self,
        *,
        openalex_client: OpenAlexClient | None = None,
        crossref_client: CrossrefClient | None = None,
        cache: SearchCache | None = None,
    ) -> None:
        shared_semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPSTREAM_REQUESTS)
        self._openalex = openalex_client or OpenAlexClient(semaphore=shared_semaphore)
        self._crossref = crossref_client or CrossrefClient(semaphore=shared_semaphore)
        self._cache = cache if cache is not None else SearchCache()

    async def search_papers(self, query: str, limit: int) -> PaperSearchResponse:
        """Search OpenAlex and Crossref concurrently, normalize, deduplicate, and cache."""
        cleaned_query = " ".join(query.strip().split())

        cached_results = self._cache.get(cleaned_query, limit)
        if cached_results is not None:
            return PaperSearchResponse(
                query=cleaned_query,
                limit=limit,
                count=len(cached_results),
                cached=True,
                warnings=[],
                results=cached_results,
            )

        openalex_res, crossref_res = await asyncio.gather(
            self._openalex.search_works(cleaned_query, limit=limit),
            self._crossref.search_works(cleaned_query, limit=limit),
            return_exceptions=True,
        )

        combined_papers: list[Paper] = []
        errors: list[UpstreamAPIError] = []
        warnings: list[str] = []

        for source_label, outcome in (
            ("openalex", openalex_res),
            ("crossref", crossref_res),
        ):
            if isinstance(outcome, list):
                combined_papers.extend(outcome)
            elif isinstance(outcome, UpstreamAPIError):
                errors.append(outcome)
                warnings.append(f"{source_label}: {outcome.message}")
            elif isinstance(outcome, Exception):
                logger.warning(
                    "Unexpected error from %s: %s",
                    source_label,
                    type(outcome).__name__,
                )
                err = UpstreamResponseError(
                    source=source_label,
                    message=f"Unexpected error from {source_label}.",
                )
                errors.append(err)
                warnings.append(f"{source_label}: {err.message}")

        # If both providers failed, raise the most specific upstream error
        if len(errors) == 2:
            for err in errors:
                if isinstance(err, UpstreamRateLimitError):
                    raise err
            for err in errors:
                if isinstance(err, UpstreamTimeoutError):
                    raise err
            raise errors[0]

        deduped = deduplicate_papers(combined_papers)[:limit]

        # Only cache clean, complete responses (when no upstream provider failed)
        if not errors:
            self._cache.set(cleaned_query, limit, deduped)

        return PaperSearchResponse(
            query=cleaned_query,
            limit=limit,
            count=len(deduped),
            cached=False,
            warnings=warnings,
            results=deduped,
        )
