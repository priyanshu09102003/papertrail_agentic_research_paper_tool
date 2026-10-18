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
        str,
        Query(
            min_length=2,
            max_length=300,
            description="Search query string (2 to 300 characters).",
        ),
    ],
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
    cleaned_query = q.strip()
    if len(cleaned_query) < 2:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail="Search query must contain at least 2 non-whitespace characters.",
        )

    try:
        return await service.search_papers(query=cleaned_query, limit=limit)
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
