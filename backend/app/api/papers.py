"""API routes for scholarly paper discovery."""

from functools import lru_cache
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT
from app.schemas import PaperSearchResponse
from app.services.discovery import PaperDiscoveryService
from app.services.exceptions import (
    UpstreamAPIError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
)

router = APIRouter(prefix="/api/papers", tags=["papers"])


@lru_cache(maxsize=1)
def get_discovery_service() -> PaperDiscoveryService:
    """Return a singleton PaperDiscoveryService instance."""
    return PaperDiscoveryService()


@router.get(
    "/search",
    response_model=PaperSearchResponse,
    summary="Search Scholarly Papers",
    description=(
        "Search OpenAlex and Crossref for scholarly papers, returning normalized "
        "and DOI-deduplicated results."
    ),
)
async def search_papers(
    q: Annotated[
        str | None,
        Query(
            description="Search query string (2 to 300 characters).",
        ),
    ] = None,
    query: Annotated[
        str | None,
        Query(
            description="Alternative/alias search query parameter.",
        ),
    ] = None,
    source: Annotated[
        str | None,
        Query(
            description="Optional source filter: 'openalex', 'crossref', or 'all'.",
        ),
    ] = None,
    from_year: Annotated[
        int | None,
        Query(
            description="Optional start publication year filter.",
        ),
    ] = None,
    to_year: Annotated[
        int | None,
        Query(
            description="Optional end publication year filter.",
        ),
    ] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_SEARCH_LIMIT,
            description=f"Maximum number of deduplicated papers to return (1 to {MAX_SEARCH_LIMIT}).",
        ),
    ] = DEFAULT_SEARCH_LIMIT,
    service: PaperDiscoveryService = Depends(get_discovery_service),
) -> PaperSearchResponse:
    """Validate search parameters and return normalized paper discovery results."""
    raw_query = q if q is not None else query
    if raw_query is None:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Search query parameter 'q' or 'query' is required.",
        )

    cleaned_query = raw_query.strip()
    if len(cleaned_query) < 2 or len(cleaned_query) > 300:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Search query must contain between 2 and 300 non-whitespace characters.",
        )

    try:
        response = await service.search_papers(query=cleaned_query, limit=limit)
        results = response.results
        if source and source.lower() != "all":
            results = [p for p in results if p.source and p.source.lower() == source.lower()]
        if from_year is not None:
            results = [p for p in results if p.publication_year is not None and p.publication_year >= from_year]
        if to_year is not None:
            results = [p for p in results if p.publication_year is not None and p.publication_year <= to_year]

        return PaperSearchResponse(
            query=cleaned_query,
            limit=limit,
            count=len(results),
            cached=response.cached,
            warnings=response.warnings,
            results=results,
        )
    except UpstreamRateLimitError as exc:
        raise HTTPException(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            detail=exc.message,
        ) from exc
    except UpstreamTimeoutError as exc:
        raise HTTPException(
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
            detail=exc.message,
        ) from exc
    except UpstreamAPIError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=exc.message,
        ) from exc
