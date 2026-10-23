"""Mocked unit tests for the local Ollama LLM provider abstraction and structured output validation."""

import asyncio
import json
from typing import Any

from fastapi.testclient import TestClient
import httpx
from pydantic import BaseModel, Field

from app.api.llm import get_llm_provider
from app.llm.exceptions import (
    LLMInvalidResponseError,
    LLMModelNotFoundError,
    LLMServiceUnavailableError,
    LLMStructuredOutputError,
    LLMTimeoutError,
)
from app.llm.ollama_provider import OllamaProvider
from app.main import app


class SampleAnalysisOutput(BaseModel):
    """Sample Pydantic schema for testing structured LLM output validation."""

    topic: str = Field(..., min_length=2)
    key_points: list[str] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


def _mock_client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_generate_text_success() -> None:
    """Verify simple text generation validates output with LLMTextResponse."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "qwen2.5:1.5b"
        assert body["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5:1.5b",
                "response": "  Self-attention computes weighted token representations.  ",
                "done": True,
            },
        )

    async def run() -> None:
        async with _mock_client(handler) as http_client:
            provider = OllamaProvider(
                base_url="http://127.0.0.1:11434",
                model_name="qwen2.5:1.5b",
                http_client=http_client,
            )
            result = await provider.generate_text("Explain self-attention in one sentence.")

        assert result.provider == "ollama"
        assert result.model == "qwen2.5:1.5b"
        assert result.text == "Self-attention computes weighted token representations."

    asyncio.run(run())


def test_generate_structured_handles_markdown_fences_and_validates_pydantic() -> None:
    """Verify structured generation extracts JSON even when wrapped in markdown fences."""
    fenced_response = (
        "Here is the requested JSON object:\n"
        "```json\n"
        '{"topic": "Transformers", "key_points": ["Self-attention", "Parallel training"], "confidence": 0.95}\n'
        "```"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert "JSON" in body.get("system", "")
        return httpx.Response(200, json={"response": fenced_response, "done": True})

    async def run() -> None:
        async with _mock_client(handler) as http_client:
            provider = OllamaProvider(http_client=http_client)
            structured = await provider.generate_structured(
                "Summarize transformers.",
                SampleAnalysisOutput,
            )

        assert isinstance(structured, SampleAnalysisOutput)
        assert structured.topic == "Transformers"
        assert structured.key_points == ["Self-attention", "Parallel training"]
        assert structured.confidence == 0.95

    asyncio.run(run())


def test_generate_structured_recovers_with_bounded_retry() -> None:
    """Verify invalid first output triggers a bounded retry and succeeds when corrected."""
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            # First attempt returns malformed JSON / wrong types
            return httpx.Response(
                200,
                json={"response": '{"topic": "X", "key_points": [], "confidence": 2.5}', "done": True},
            )
        # Second attempt returns schema-valid JSON
        return httpx.Response(
            200,
            json={
                "response": '{"topic": "Graph Networks", "key_points": ["Message passing"], "confidence": 0.88}',
                "done": True,
            },
        )

    async def run() -> None:
        async with _mock_client(handler) as http_client:
            provider = OllamaProvider(http_client=http_client, max_structured_retries=2)
            result = await provider.generate_structured(
                "Extract graph network summary.",
                SampleAnalysisOutput,
            )

        assert attempts == 2
        assert result.topic == "Graph Networks"
        assert result.confidence == 0.88

    asyncio.run(run())


def test_generate_structured_enforces_hard_retry_cap_and_raises_controlled_error() -> None:
    """Verify persistent malformed JSON never loops unboundedly and raises LLMStructuredOutputError."""
    call_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"response": "not valid json at all", "done": True})

    async def run() -> None:
        async with _mock_client(handler) as http_client:
            provider = OllamaProvider(http_client=http_client)
            try:
                # Even if caller passes max_retries=50, hard cap clamps retries to 3 (4 total attempts)
                await provider.generate_structured(
                    "Test bounded retries.",
                    SampleAnalysisOutput,
                    max_retries=50,
                )
                raise AssertionError("Expected LLMStructuredOutputError")
            except LLMStructuredOutputError as exc:
                assert exc.attempts == 4
                assert call_count == 4
                assert "SampleAnalysisOutput" in exc.message

    asyncio.run(run())


def test_unavailable_ollama_service_handled_safely() -> None:
    """Verify connection failures raise LLMServiceUnavailableError without leaking internal details."""
    def connect_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused to 127.0.0.1:11434", request=request)

    async def run() -> None:
        async with _mock_client(connect_error_handler) as http_client:
            provider = OllamaProvider(http_client=http_client)
            try:
                await provider.generate_text("Hello")
                raise AssertionError("Expected LLMServiceUnavailableError")
            except LLMServiceUnavailableError as exc:
                assert exc.status_code == 503
                assert "127.0.0.1" not in exc.message

            status = await provider.check_health()
            assert status.service_reachable is False
            assert status.model_available is False
            assert status.status == "unavailable"

    asyncio.run(run())


def test_model_not_found_and_timeout_and_invalid_payload_responses() -> None:
    """Verify HTTP 404 model-not-found, timeouts, and malformed Ollama responses raise controlled errors."""
    def not_found_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404, json={"error": "model 'qwen2.5:1.5b' not found, try pulling it first"}
        )

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out", request=request)

    def malformed_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<<<corrupted upstream json>>>")

    async def run() -> None:
        # 1. Model not found (HTTP 404)
        async with _mock_client(not_found_handler) as http_client:
            provider = OllamaProvider(model_name="qwen2.5:1.5b", http_client=http_client)
            try:
                await provider.generate_text("Prompt")
                raise AssertionError("Expected LLMModelNotFoundError")
            except LLMModelNotFoundError as exc:
                assert exc.status_code == 404
                assert "qwen2.5:1.5b" in exc.message

        # 2. Request timeout
        async with _mock_client(timeout_handler) as http_client:
            provider = OllamaProvider(http_client=http_client)
            try:
                await provider.generate_text("Prompt")
                raise AssertionError("Expected LLMTimeoutError")
            except LLMTimeoutError as exc:
                assert exc.status_code == 504

        # 3. Malformed non-JSON response from Ollama
        async with _mock_client(malformed_handler) as http_client:
            provider = OllamaProvider(http_client=http_client)
            try:
                await provider.generate_text("Prompt")
                raise AssertionError("Expected LLMInvalidResponseError")
            except LLMInvalidResponseError as exc:
                assert exc.status_code == 502

    asyncio.run(run())


def test_llm_status_endpoint() -> None:
    """Verify GET /api/llm/status reports ready when qwen2.5:1.5b is present in /api/tags."""
    def tags_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen2.5:1.5b"}, {"name": "nomic-embed-text:latest"}]},
        )

    class ReadyOllamaProvider(OllamaProvider):
        async def check_health(self):  # type: ignore[override]
            async with _mock_client(tags_handler) as http_client:
                delegate = OllamaProvider(model_name="qwen2.5:1.5b", http_client=http_client)
                return await delegate.check_health()

    app.dependency_overrides[get_llm_provider] = lambda: ReadyOllamaProvider()
    try:
        client = TestClient(app)
        res = client.get("/api/llm/status")
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "ollama"
        assert data["model"] == "qwen2.5:1.5b"
        assert data["service_reachable"] is True
        assert data["model_available"] is True
        assert data["status"] == "ready"
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)
