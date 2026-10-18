"""Asynchronous Crossref REST API client for scholarly paper discovery."""

import asyncio
import logging
from typing import Any

import httpx

from app.config import (
    CROSSREF_BASE_URL,
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_TIMEOUT_SECONDS,
    MAX_CONCURRENT_UPSTREAM_REQUESTS,
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
    clean_crossref_abstract,
    clean_http_url,
    is_explicit_pdf_url,
    normalize_doi,
)

logger = logging.getLogger(__name__)


class CrossrefClient:
    """Client for querying and normalizing works from the Crossref REST API."""

    SOURCE_NAME = "crossref"

    def __init__(
        self,
        *,
        base_url: str = CROSSREF_BASE_URL,
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
        """Search Crossref works by query string and return normalized Paper records."""
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        params: dict[str, str | int] = {
            "query": cleaned_query,
            "rows": max(1, min(limit, 50)),
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        url = f"{self._base_url}/works"

        async with self._semaphore:
            payload = await self._execute_get(url=url, params=params, headers=headers)

        message_block = payload.get("message")
        if not isinstance(message_block, dict):
            logger.warning("Crossref response missing valid 'message' object.")
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Invalid Crossref response format: missing 'message' object.",
            )

        raw_items = message_block.get("items")
        if not isinstance(raw_items, list):
            logger.warning("Crossref response missing valid 'items' list.")
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Invalid Crossref response format: missing 'items' list.",
            )

        papers: list[Paper] = []
        for item in raw_items:
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
                logger.warning("Crossref rate limit reached (HTTP 429).")
                raise UpstreamRateLimitError(
                    source=self.SOURCE_NAME,
                    message="Crossref rate limit exceeded (HTTP 429).",
                    retry_after=retry_after,
                )

            response.raise_for_status()
            data = response.json()
        except UpstreamRateLimitError:
            raise
        except httpx.TimeoutException as exc:
            logger.warning("Crossref request timed out: %s", type(exc).__name__)
            raise UpstreamTimeoutError(
                source=self.SOURCE_NAME,
                message="Crossref request timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning("Crossref returned HTTP %d.", status_code)
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message=f"Crossref returned HTTP {status_code}.",
                status_code=status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Crossref network failure: %s", type(exc).__name__)
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Network error while communicating with Crossref.",
            ) from exc
        except ValueError as exc:
            logger.warning("Crossref returned invalid JSON.")
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Crossref returned invalid JSON.",
            ) from exc

        if not isinstance(data, dict):
            logger.warning("Crossref JSON root is not an object.")
            raise UpstreamResponseError(
                source=self.SOURCE_NAME,
                message="Unexpected Crossref response structure.",
            )

        return data

    def _parse_work(self, item: dict[str, Any]) -> Paper | None:
        """Normalize a single Crossref work item into a Paper model."""
        raw_titles = item.get("title")
        title: str | None = None
        if isinstance(raw_titles, list):
            for candidate in raw_titles:
                if isinstance(candidate, str) and candidate.strip():
                    title = candidate.strip()
                    break
        elif isinstance(raw_titles, str) and raw_titles.strip():
            title = raw_titles.strip()

        if not title:
            return None

        authors = self._extract_authors(item.get("author"))
        publication_year = self._extract_publication_year(item)
        doi = normalize_doi(item.get("DOI"))
        abstract = clean_crossref_abstract(item.get("abstract"))

        landing_page_url = self._extract_landing_page_url(item)
        open_access_pdf_url = self._extract_pdf_url(
            item.get("link"), landing_page_url=landing_page_url
        )

        paper_id = build_paper_id(
            source="crossref",
            doi=doi,
            upstream_id=doi or clean_http_url(item.get("URL")),
            title=title,
        )

        return Paper(
            id=paper_id,
            title=title,
            authors=authors,
            publication_year=publication_year,
            doi=doi,
            abstract=abstract,
            source="crossref",
            landing_page_url=landing_page_url,
            open_access_pdf_url=open_access_pdf_url,
        )

    @staticmethod
    def _extract_authors(raw_authors: Any) -> list[str]:
        """Extract ordered author display names from a Crossref author list."""
        if not isinstance(raw_authors, list):
            return []

        authors: list[str] = []
        for entry in raw_authors:
            if not isinstance(entry, dict):
                continue
            given = entry.get("given")
            family = entry.get("family")
            name = entry.get("name")

            parts: list[str] = []
            if isinstance(given, str) and given.strip():
                parts.append(given.strip())
            if isinstance(family, str) and family.strip():
                parts.append(family.strip())

            if parts:
                authors.append(" ".join(parts))
            elif isinstance(name, str) and name.strip():
                authors.append(name.strip())

        return authors

    @staticmethod
    def _extract_publication_year(item: dict[str, Any]) -> int | None:
        """Extract publication year from Crossref date-parts fields."""
        for field_name in ("published-print", "published-online", "published", "issued"):
            date_obj = item.get(field_name)
            if not isinstance(date_obj, dict):
                continue
            date_parts = date_obj.get("date-parts")
            if (
                isinstance(date_parts, list)
                and date_parts
                and isinstance(date_parts[0], list)
                and date_parts[0]
            ):
                year = date_parts[0][0]
                if isinstance(year, int) and not isinstance(year, bool) and 1000 <= year <= 2100:
                    return year
        return None

    @staticmethod
    def _extract_landing_page_url(item: dict[str, Any]) -> str | None:
        """Extract primary landing page URL from Crossref resource or URL fields."""
        resource = item.get("resource")
        if isinstance(resource, dict):
            primary = resource.get("primary")
            if isinstance(primary, dict):
                primary_url = clean_http_url(primary.get("URL"))
                if primary_url:
                    return primary_url

        return clean_http_url(item.get("URL"))

    @staticmethod
    def _extract_pdf_url(raw_links: Any, *, landing_page_url: str | None) -> str | None:
        """Extract a verified direct PDF URL from Crossref link entries, if explicitly present."""
        if not isinstance(raw_links, list):
            return None

        for link in raw_links:
            if not isinstance(link, dict):
                continue
            content_type = link.get("content-type")
            if not isinstance(content_type, str):
                continue
            if content_type.strip().lower() != "application/pdf":
                continue

            verified = is_explicit_pdf_url(
                link.get("URL"),
                landing_page_url=landing_page_url,
                content_type=content_type,
                from_dedicated_pdf_field=True,
            )
            if verified:
                return verified

        return None
