"""Asynchronous OpenAlex REST API client for scholarly paper discovery."""

import asyncio
import logging
from typing import Any

import httpx

from app.config import (
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_TIMEOUT_SECONDS,
    MAX_CONCURRENT_UPSTREAM_REQUESTS,
    OPENALEX_BASE_URL,
    USER_AGENT,
)
from app.schemas import Paper
from app.services.exceptions import (
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
)
from app.services.normalization import (
    build_paper_id,
    clean_http_url,
    is_explicit_pdf_url,
    normalize_doi,
    reconstruct_openalex_abstract,
)

logger = logging.getLogger(__name__)


class OpenAlexClient:
    """Client for querying and normalizing works from the OpenAlex API."""

    SOURCE_NAME = "openalex"

    def __init__(
        self,
        *,
        base_url: str = OPENALEX_BASE_URL,
        timeout_seconds: float = HTTP_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = HTTP_CONNECT_TIMEOUT_SECONDS,
        semaphore: asyncio.Semaphore | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds)
        self._semaphore = semaphore or asyncio.Semaphore(MAX_CONCURRENT_UPSTREAM_REQUESTS)
        self._http_client = http_client

    async def search_works(self, query: str, limit: int) -> list[Paper]:
        """Search OpenAlex works by query string and return normalized Paper records."""
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        params: dict[str, str | int] = {
            "search": cleaned_query,
            "per-page": max(1, min(limit, 50)),
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        url = f"{self._base_url}/works"

        async with self._semaphore:
            payload = await self._execute_get(url=url, params=params, headers=headers)

        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            logger.warning("OpenAlex response missing valid 'results' list.")
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Invalid OpenAlex response format: missing 'results' list.",
            )

        papers: list[Paper] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            parsed = self._parse_work(item)
            if parsed is not None:
                papers.append(parsed)

        return papers

    async def _execute_get(
        self,
        *,
        url: str,
        params: dict[str, str | int],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Perform an async GET request with error, timeout, and rate-limit handling."""
        try:
            if self._http_client is not None:
                response = await self._http_client.get(
                    url, params=params, headers=headers, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, params=params, headers=headers)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                logger.warning("OpenAlex rate limit reached (HTTP 429).")
                raise UpstreamRateLimitError(
                    source=self.SOURCE_NAME,
                    message="OpenAlex rate limit exceeded (HTTP 429).",
                    retry_after=retry_after,
                )

            response.raise_for_status()
            data = response.json()
        except UpstreamRateLimitError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("OpenAlex request timed out: %s", type(exc).__name__)
            raise UpstreamTimeoutError(
                source=self.SOURCE_NAME,
                message="OpenAlex request timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning("OpenAlex returned HTTP %d.", status_code)
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message=f"OpenAlex returned HTTP {status_code}.",
                status_code=status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("OpenAlex network failure: %s", type(exc).__name__)
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Network error while communicating with OpenAlex.",
            ) from exc
        except ValueError as exc:
            logger.warning("OpenAlex returned invalid JSON.")
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="OpenAlex returned invalid JSON.",
            ) from exc

        if not isinstance(data, dict):
            logger.warning("OpenAlex JSON root is not an object.")
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Unexpected OpenAlex response structure.",
            )

        return data

    def _parse_work(self, item: dict[str, Any]) -> Paper | None:
        """Normalize a single OpenAlex work dictionary into a Paper model."""
        raw_title = item.get("title") or item.get("display_name")
        if not isinstance(raw_title, str) or not raw_title.strip():
            return None
        title = raw_title.strip()

        authors: list[str] = []
        raw_authorships = item.get("authorships")
        if isinstance(raw_authorships, list):
            for authorship in raw_authorships:
                if not isinstance(authorship, dict):
                    continue
                author_obj = authorship.get("author")
                if isinstance(author_obj, dict):
                    display_name = author_obj.get("display_name")
                    if isinstance(display_name, str) and display_name.strip():
                        authors.append(display_name.strip())

        raw_year = item.get("publication_year")
        publication_year: int | None = (
            raw_year
            if isinstance(raw_year, int) and not isinstance(raw_year, bool) and 1000 <= raw_year <= 2100
            else None
        )

        doi = normalize_doi(item.get("doi"))
        abstract = reconstruct_openalex_abstract(item.get("abstract_inverted_index"))

        primary_location = (
            item.get("primary_location")
            if isinstance(item.get("primary_location"), dict)
            else {}
        )
        best_oa_location = (
            item.get("best_oa_location")
            if isinstance(item.get("best_oa_location"), dict)
            else {}
        )

        landing_page_url = clean_http_url(
            primary_location.get("landing_page_url")
            or best_oa_location.get("landing_page_url")
        )

        # Only accept explicitly verified PDF URLs; never treat an HTML landing page as a PDF.
        candidate_pdf_url = best_oa_location.get("pdf_url") or primary_location.get("pdf_url")
        open_access_pdf_url = is_explicit_pdf_url(
            candidate_pdf_url,
            landing_page_url=landing_page_url,
            from_dedicated_pdf_field=True,
        )

        upstream_id = item.get("id") if isinstance(item.get("id"), str) else None
        paper_id = build_paper_id(
            source="openalex",
            doi=doi,
            upstream_id=upstream_id,
            title=title,
        )

        return Paper(
            id=paper_id,
            title=title,
            authors=authors,
            publication_year=publication_year,
            doi=doi,
            abstract=abstract,
            source="openalex",
            landing_page_url=landing_page_url,
            open_access_pdf_url=open_access_pdf_url,
        )
