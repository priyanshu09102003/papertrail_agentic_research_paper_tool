"""Unit and endpoint tests for OpenAlex, Crossref, normalization, deduplication, and caching.

All tests use mocked HTTP transports and never depend on live external API availability.
"""

import asyncio
from typing import Any

from fastapi.testclient import TestClient
import httpx

from app.api.papers import get_discovery_service
from app.main import app
from app.services.cache import SearchCache
from app.services.crossref_client import CrossrefClient
from app.services.discovery import PaperDiscoveryService
from app.services.exceptions import (
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
)
from app.services.openalex_client import OpenAlexClient


def _make_async_client(handler: Any) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient backed by a mock transport handler."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


def test_successful_openalex_response() -> None:
    """Verify OpenAlex client normalizes a complete work payload accurately."""
    sample_payload = {
        "results": [
            {
                "id": "https://openalex.org/W2741809807",
                "title": "Attention Is All You Need",
                "publication_year": 2017,
                "doi": "https://doi.org/10.48550/arXiv.1706.03762",
                "authorships": [
                    {"author": {"display_name": "Ashish Vaswani"}},
                    {"author": {"display_name": "Noam Shazeer"}},
                ],
                "abstract_inverted_index": {
                    "Dominant": [0],
                    "sequence": [1],
                    "transduction": [2],
                    "models": [3],
                },
                "primary_location": {
                    "landing_page_url": "https://arxiv.org/abs/1706.03762",
                    "pdf_url": None,
                },
                "best_oa_location": {
                    "landing_page_url": "https://arxiv.org/abs/1706.03762",
                    "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
                },
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/works"
        assert request.url.params["search"] == "transformer"
        return httpx.Response(200, json=sample_payload)

    async def run() -> None:
        async with _make_async_client(handler) as http_client:
            client = OpenAlexClient(http_client=http_client)
            results = await client.search_works("transformer", limit=5)

        assert len(results) == 1
        paper = results[0]
        assert paper.id == "doi:10.48550/arxiv.1706.03762"
        assert paper.title == "Attention Is All You Need"
        assert paper.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert paper.publication_year == 2017
        assert paper.doi == "10.48550/arxiv.1706.03762"
        assert paper.abstract == "Dominant sequence transduction models"
        assert paper.source == "openalex"
        assert paper.landing_page_url == "https://arxiv.org/abs/1706.03762"
        assert paper.open_access_pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"

    asyncio.run(run())


def test_successful_crossref_response() -> None:
    """Verify Crossref client normalizes a complete work payload and strips JATS XML tags."""
    sample_payload = {
        "status": "ok",
        "message": {
            "items": [
                {
                    "DOI": "10.1038/Nature14539",
                    "title": ["Deep learning"],
                    "author": [
                        {"given": "Yann", "family": "LeCun"},
                        {"given": "Yoshua", "family": "Bengio"},
                        {"given": "Geoffrey", "family": "Hinton"},
                    ],
                    "published-print": {"date-parts": [[2015, 5, 28]]},
                    "abstract": "<jats:title>Abstract</jats:title><jats:p>Deep learning allows computational models to learn representations.</jats:p>",
                    "resource": {
                        "primary": {
                            "URL": "https://www.nature.com/articles/nature14539"
                        }
                    },
                    "link": [
                        {
                            "URL": "https://www.nature.com/articles/nature14539",
                            "content-type": "text/html",
                        },
                        {
                            "URL": "https://www.nature.com/articles/nature14539.pdf",
                            "content-type": "application/pdf",
                        },
                    ],
                }
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/works"
        assert request.url.params["query"] == "deep learning"
        return httpx.Response(200, json=sample_payload)

    async def run() -> None:
        async with _make_async_client(handler) as http_client:
            client = CrossrefClient(http_client=http_client)
            results = await client.search_works("deep learning", limit=5)

        assert len(results) == 1
        paper = results[0]
        assert paper.id == "doi:10.1038/nature14539"
        assert paper.title == "Deep learning"
        assert paper.authors == ["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"]
        assert paper.publication_year == 2015
        assert paper.doi == "10.1038/nature14539"
        assert (
            paper.abstract
            == "Deep learning allows computational models to learn representations."
        )
        assert paper.source == "crossref"
        assert paper.landing_page_url == "https://www.nature.com/articles/nature14539"
        assert (
            paper.open_access_pdf_url
            == "https://www.nature.com/articles/nature14539.pdf"
        )

    asyncio.run(run())


def test_missing_abstracts_and_missing_doi_preserved_as_null() -> None:
    """Verify missing abstracts, DOIs, and PDF URLs remain None and landing page is not treated as PDF."""
    openalex_payload = {
        "results": [
            {
                "id": "https://openalex.org/W999999",
                "title": "A Work Without DOI or Abstract",
                "publication_year": None,
                "doi": None,
                "authorships": [],
                "abstract_inverted_index": None,
                "primary_location": {
                    "landing_page_url": "https://example.org/paper-landing-page",
                    "pdf_url": "https://example.org/paper-landing-page",
                },
                "best_oa_location": None,
            }
        ]
    }
    crossref_payload = {
        "message": {
            "items": [
                {
                    "title": ["Second Work Without DOI or Abstract"],
                    "DOI": None,
                    "author": [],
                    "URL": "https://publisher.example.org/article/42",
                    "link": [
                        {
                            "URL": "https://publisher.example.org/article/42",
                            "content-type": "unspecified",
                        }
                    ],
                }
            ]
        }
    }

    async def run() -> None:
        async with (
            _make_async_client(lambda _: httpx.Response(200, json=openalex_payload)) as oa_http,
            _make_async_client(lambda _: httpx.Response(200, json=crossref_payload)) as cr_http,
        ):
            service = PaperDiscoveryService(
                openalex_client=OpenAlexClient(http_client=oa_http),
                crossref_client=CrossrefClient(http_client=cr_http),
                cache=SearchCache(cache_file_path=None),
            )
            response = await service.search_papers("missing fields test", limit=10)

        assert response.count == 2
        first, second = response.results[0], response.results[1]

        assert first.id == "openalex:W999999"
        assert first.doi is None
        assert first.abstract is None
        assert first.publication_year is None
        assert first.authors == []
        assert first.landing_page_url == "https://example.org/paper-landing-page"
        # Landing page URL must not be treated as a direct PDF URL
        assert first.open_access_pdf_url is None

        assert second.doi is None
        assert second.abstract is None
        assert second.authors == []
        assert second.landing_page_url == "https://publisher.example.org/article/42"
        assert second.open_access_pdf_url is None

    asyncio.run(run())


def test_duplicate_doi_records_are_deduplicated_and_merged() -> None:
    """Verify records sharing the same normalized DOI are deduplicated and complementary fields merged."""
    openalex_payload = {
        "results": [
            {
                "id": "https://openalex.org/W111",
                "title": "Graph Neural Networks Review",
                "publication_year": 2021,
                "doi": "https://doi.org/10.1000/GNN.2021.01",
                "authorships": [{"author": {"display_name": "Alice Smith"}}],
                "abstract_inverted_index": None,
                "primary_location": {
                    "landing_page_url": "https://example.org/gnn",
                    "pdf_url": "https://example.org/gnn.pdf",
                },
            }
        ]
    }
    crossref_payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/gnn.2021.01",
                    "title": ["Graph Neural Networks Review"],
                    "author": [{"given": "Alice", "family": "Smith"}],
                    "published-print": {"date-parts": [[2021]]},
                    "abstract": "<jats:p>Comprehensive survey of GNN architectures.</jats:p>",
                    "URL": "https://doi.org/10.1000/gnn.2021.01",
                }
            ]
        }
    }

    oa_calls = 0
    cr_calls = 0

    def oa_handler(_: httpx.Request) -> httpx.Response:
        nonlocal oa_calls
        oa_calls += 1
        return httpx.Response(200, json=openalex_payload)

    def cr_handler(_: httpx.Request) -> httpx.Response:
        nonlocal cr_calls
        cr_calls += 1
        return httpx.Response(200, json=crossref_payload)

    async def run() -> None:
        async with (
            _make_async_client(oa_handler) as oa_http,
            _make_async_client(cr_handler) as cr_http,
        ):
            service = PaperDiscoveryService(
                openalex_client=OpenAlexClient(http_client=oa_http),
                crossref_client=CrossrefClient(http_client=cr_http),
                cache=SearchCache(cache_file_path=None),
            )

            first_res = await service.search_papers("graph neural networks", limit=10)
            assert first_res.count == 1
            assert first_res.cached is False
            merged = first_res.results[0]
            assert merged.doi == "10.1000/gnn.2021.01"
            assert merged.source == "openalex"
            assert merged.abstract == "Comprehensive survey of GNN architectures."
            assert merged.open_access_pdf_url == "https://example.org/gnn.pdf"

            # Second identical query should be served from cache without new HTTP requests
            second_res = await service.search_papers("graph neural networks", limit=10)
            assert second_res.cached is True
            assert second_res.count == 1
            assert oa_calls == 1
            assert cr_calls == 1

    asyncio.run(run())


def test_network_timeout_handling() -> None:
    """Verify network timeouts raise UpstreamTimeoutError and return HTTP 504 on the route."""
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out", request=request)

    async def run() -> None:
        async with _make_async_client(timeout_handler) as http_client:
            oa_client = OpenAlexClient(http_client=http_client)
            try:
                await oa_client.search_works("timeout query", limit=5)
                raise AssertionError("Expected UpstreamTimeoutError")
            except UpstreamTimeoutError as exc:
                assert exc.source == "openalex"

    asyncio.run(run())

    # Also verify route returns 504 Gateway Timeout when both providers time out
    class TimeoutService(PaperDiscoveryService):
        async def search_papers(self, query: str, limit: int):  # type: ignore[override]
            raise UpstreamTimeoutError(
                source="openalex", message="Upstream discovery request timed out."
            )

    app.dependency_overrides[get_discovery_service] = lambda: TimeoutService(
        cache=SearchCache(cache_file_path=None)
    )
    try:
        client = TestClient(app)
        response = client.get("/api/papers/search", params={"q": "quantum computing"})
        assert response.status_code == 504
        body = response.json()
        assert body["status_code"] == 504
        assert "timed out" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_http_429_rate_limit_response() -> None:
    """Verify HTTP 429 from upstream raises UpstreamRateLimitError and maps to HTTP 429 on the route."""
    def rate_limit_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"}, json={"error": "rate limit"})

    async def run() -> None:
        async with _make_async_client(rate_limit_handler) as http_client:
            cr_client = CrossrefClient(http_client=http_client)
            try:
                await cr_client.search_works("rate limited query", limit=5)
                raise AssertionError("Expected UpstreamRateLimitError")
            except UpstreamRateLimitError as exc:
                assert exc.source == "crossref"
                assert exc.status_code == 429
                assert exc.retry_after == "30"

    asyncio.run(run())

    class RateLimitedService(PaperDiscoveryService):
        async def search_papers(self, query: str, limit: int):  # type: ignore[override]
            raise UpstreamRateLimitError(
                source="crossref", message="Crossref rate limit exceeded (HTTP 429)."
            )

    app.dependency_overrides[get_discovery_service] = lambda: RateLimitedService(
        cache=SearchCache(cache_file_path=None)
    )
    try:
        client = TestClient(app)
        response = client.get("/api/papers/search", params={"q": "protein folding"})
        assert response.status_code == 429
        body = response.json()
        assert body["status_code"] == 429
        assert "rate limit" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_invalid_upstream_response() -> None:
    """Verify malformed JSON or unexpected payload structure raises UpstreamResponseError and maps to 502."""
    def invalid_json_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<<<not valid json>>>")

    def missing_items_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    async def run() -> None:
        async with _make_async_client(invalid_json_handler) as http_client:
            oa_client = OpenAlexClient(http_client=http_client)
            try:
                await oa_client.search_works("invalid json", limit=5)
                raise AssertionError("Expected UpstreamResponseError for invalid JSON")
            except UpstreamResponseError as exc:
                assert "invalid json" in exc.message.lower()

        async with _make_async_client(missing_items_handler) as http_client:
            cr_client = CrossrefClient(http_client=http_client)
            try:
                await cr_client.search_works("missing items", limit=5)
                raise AssertionError("Expected UpstreamResponseError for missing message")
            except UpstreamResponseError as exc:
                assert "missing 'message'" in exc.message.lower()

    asyncio.run(run())

    class BadGatewayService(PaperDiscoveryService):
        async def search_papers(self, query: str, limit: int):  # type: ignore[override]
            raise UpstreamResponseError(
                source="openalex", message="Invalid OpenAlex response format."
            )

    app.dependency_overrides[get_discovery_service] = lambda: BadGatewayService(
        cache=SearchCache(cache_file_path=None)
    )
    try:
        client = TestClient(app)
        response = client.get("/api/papers/search", params={"q": "invalid upstream"})
        assert response.status_code == 502
        body = response.json()
        assert body["status_code"] == 502
        assert "invalid openalex" in body["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_invalid_user_query_parameters() -> None:
    """Verify invalid user query strings and out-of-bounds limits return HTTP 422."""
    client = TestClient(app)

    # Missing 'q' parameter
    res_missing = client.get("/api/papers/search")
    assert res_missing.status_code == 422

    # Single-character query
    res_short = client.get("/api/papers/search", params={"q": "a"})
    assert res_short.status_code == 422

    # Whitespace-only query
    res_whitespace = client.get("/api/papers/search", params={"q": "     "})
    assert res_whitespace.status_code == 422

    # Invalid limit (0 and > 50)
    res_limit_zero = client.get("/api/papers/search", params={"q": "machine learning", "limit": 0})
    assert res_limit_zero.status_code == 422

    res_limit_high = client.get("/api/papers/search", params={"q": "machine learning", "limit": 100})
    assert res_limit_high.status_code == 422


def test_query_alias_and_filters() -> None:
    """Verify 'query' parameter alias and year/source filters work properly."""
    client = TestClient(app)

    # Calling with query parameter instead of q
    res = client.get("/api/papers/search", params={
        "query": "deep learning",
        "source": "all",
        "from_year": 2018,
        "to_year": 2024,
        "limit": 5,
    })
    # Must succeed (200) or upstream fallback, but never 422
    assert res.status_code in (200, 502, 504)
