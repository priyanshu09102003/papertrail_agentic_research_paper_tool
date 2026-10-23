"""Tests for the structured scientific-paper extraction engine and scientific integrity rules."""

import asyncio
import json
from typing import Any

import pymupdf as fitz  # PyMuPDF
from fastapi.testclient import TestClient
import httpx

from app.api.llm import get_llm_provider
from app.db.repository import PaperTrailRepository
from app.llm.gemini_provider import GeminiProvider
from app.llm.ollama_provider import OllamaProvider
from app.main import app
from app.schemas import ExtractedDocument, ExtractedPage
from app.services.paper_extractor import ScientificPaperExtractor

client = TestClient(app)

SYNTHETIC_PAGE_1 = (
    "Title: Sparse Graph Attention for Clinical Time-Series Forecasting\n"
    "Research Question: Can sparse graph attention improve mortality prediction on irregular ICU time-series?\n"
    "Objective: We aim to reduce attention memory overhead while preserving clinical forecasting accuracy.\n"
    "Methodology: We propose SparseGAT-ICU, a pruned multi-head graph attention architecture evaluated "
    "using 5-fold patient-stratified cross-validation on de-identified electronic health records.\n"
    "Dataset and Sample Size: Experiments were conducted on the PhysioNet-2019 clinical cohort comprising "
    "N = 320 patients monitored across 48 hours."
)

SYNTHETIC_PAGE_2 = (
    "Baselines and Metrics: We compare SparseGAT-ICU against GRU-D and Standard Transformer using AUROC, "
    "AUPRC, and inference latency.\n"
    "Quantitative Results: SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split and reduced "
    "mean inference latency to 14.2 ms per patient record, compared to 31.8 ms for Standard Transformer.\n"
    "Limitations: Our study is limited to a single-center ICU cohort and does not evaluate external hospital "
    "generalization.\n"
    "Future Work: Future work will investigate federated multi-hospital training."
)


def _make_synthetic_doc(pages_text: list[str], doc_id: str = "doc_synthetic001") -> ExtractedDocument:
    pages = [
        ExtractedPage(
            page_number=i + 1,
            text=text,
            character_count=len("".join(text.split())),
            word_count=len(text.split()),
        )
        for i, text in enumerate(pages_text)
    ]
    return ExtractedDocument(
        document_id=doc_id,
        filename="synthetic_paper.pdf",
        file_size_bytes=4096,
        page_count=len(pages),
        total_characters=sum(p.character_count for p in pages),
        total_words=sum(p.word_count for p in pages),
        pages=pages,
    )


def _build_pdf_bytes(pages_text: list[str]) -> bytes:
    doc = fitz.open()
    try:
        for text in pages_text:
            page = doc.new_page()
            page.insert_textbox(fitz.Rect(50, 50, 540, 750), text, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


def _mock_ollama_provider(handler: Any, *, max_retries: int = 1) -> OllamaProvider:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return OllamaProvider(http_client=http_client, max_structured_retries=max_retries)


def test_complete_extraction_and_idempotent_retry_persistence(
    isolated_test_repository: PaperTrailRepository,
) -> None:
    """Verify full scientific extraction, persistence in SQLite, and retry without duplicate rows."""
    llm_payload = {
        "paper_title": "Sparse Graph Attention for Clinical Time-Series Forecasting",
        "research_question": "Can sparse graph attention improve mortality prediction on irregular ICU time-series?",
        "study_objective": "Reduce attention memory overhead while preserving clinical forecasting accuracy.",
        "research_methodology": "5-fold patient-stratified cross-validation using SparseGAT-ICU on de-identified EHRs.",
        "dataset_or_material": ["PhysioNet-2019 clinical cohort"],
        "sample_size": "N = 320 patients",
        "sample_size_quote": "comprising N = 320 patients monitored across 48 hours.",
        "sample_size_page": 1,
        "model_architecture_or_intervention": "SparseGAT-ICU pruned multi-head graph attention",
        "baselines": ["GRU-D", "Standard Transformer"],
        "evaluation_metrics": ["AUROC", "AUPRC", "inference latency"],
        "main_findings": [
            {
                "author_claim": "SparseGAT-ICU achieved an AUROC of 0.891 and reduced latency to 14.2 ms.",
                "model_interpretation": "Demonstrates higher efficiency than the Standard Transformer baseline.",
                "supporting_quote": "SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split",
                "page_number": 2,
            }
        ],
        "quantitative_results": [
            {
                "metric_name": "AUROC",
                "value": "0.891",
                "unit": None,
                "context": "Held-out test split",
                "supporting_quote": "SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split",
                "page_number": 2,
            },
            {
                "metric_name": "Inference Latency",
                "value": "14.2",
                "unit": "ms",
                "context": "Per patient record",
                "supporting_quote": "reduced mean inference latency to 14.2 ms per patient record",
                "page_number": 2,
            },
        ],
        "authors_stated_limitations": [
            "Single-center ICU cohort; does not evaluate external hospital generalization."
        ],
        "future_work": ["Federated multi-hospital training."],
        "supporting_passages": [
            {
                "field_supported": "limitations",
                "quote": "Our study is limited to a single-center ICU cohort",
                "page_number": 2,
            }
        ],
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": json.dumps(llm_payload), "done": True})

    pdf_bytes = _build_pdf_bytes([SYNTHETIC_PAGE_1, SYNTHETIC_PAGE_2])
    upload_res = client.post(
        "/api/documents/upload",
        files={"file": ("clinical_gat.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]

    app.dependency_overrides[get_llm_provider] = lambda: _mock_ollama_provider(handler)
    try:
        # 1. Run initial extraction
        ext_res_1 = client.post(f"/api/documents/{doc_id}/extract")
        assert ext_res_1.status_code == 200
        data_1 = ext_res_1.json()

        assert data_1["extraction_id"] == f"ext_{doc_id}"
        assert data_1["document_id"] == doc_id
        assert data_1["paper_title"] == "Sparse Graph Attention for Clinical Time-Series Forecasting"
        assert data_1["sample_size"] == "N = 320 patients"
        assert data_1["extraction_status"] == "completed"
        assert data_1["page_numbers"] == [1, 2]
        assert len(data_1["main_findings"]) == 1
        assert data_1["main_findings"][0]["verified_in_source"] is True
        assert data_1["main_findings"][0]["author_claim"] != data_1["main_findings"][0]["model_interpretation"]

        # 2. Retry extraction for the same document and verify no duplicate records are created
        ext_res_2 = client.post(f"/api/documents/{doc_id}/extract")
        assert ext_res_2.status_code == 200
        assert isolated_test_repository.count_scientific_extractions(doc_id) == 1

        # 3. Inspect persisted extraction via GET endpoint
        get_res = client.get(f"/api/documents/{doc_id}/extraction")
        assert get_res.status_code == 200
        assert get_res.json()["extraction_id"] == f"ext_{doc_id}"
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_source_omits_sample_size_and_hallucinated_sample_size_rejected() -> None:
    """Verify omitted sample_size remains None and any fabricated sample_size is discarded."""
    text_without_sample_size = (
        "Title: Theoretical Bounds of Linear Attention\n"
        "Methodology: We derive closed-form spectral bounds for linear kernel attention mechanisms "
        "under orthogonal random features without empirical human cohorts."
    )
    doc = _make_synthetic_doc([text_without_sample_size], doc_id="doc_no_sample")

    # Case A: Model attempts to invent "N = 500 participants" which does not exist in source text
    hallucinated_payload = {
        "paper_title": "Theoretical Bounds of Linear Attention",
        "research_methodology": "Closed-form spectral bounds derivation.",
        "sample_size": "N = 500 participants",
        "sample_size_quote": "evaluated on N = 500 participants",
        "sample_size_page": 1,
    }

    async def run() -> None:
        provider = _mock_ollama_provider(
            lambda _: httpx.Response(200, json={"response": json.dumps(hallucinated_payload), "done": True})
        )
        extractor = ScientificPaperExtractor(llm_provider=provider)
        result = await extractor.extract_document(doc)

        # Hallucinated sample size must be rejected and left as None
        assert result.sample_size is None
        assert any("sample_size" in w for w in result.warnings)
        # Missing fields must be explicitly None or []
        assert result.research_question is None
        assert result.dataset_or_material == []
        assert result.future_work == []

    asyncio.run(run())


def test_model_returns_invalid_json() -> None:
    """Verify invalid JSON from the model is handled cleanly and results in 'failed' status after retries."""
    doc = _make_synthetic_doc([SYNTHETIC_PAGE_1], doc_id="doc_invalid_json")

    async def run() -> None:
        provider = _mock_ollama_provider(
            lambda _: httpx.Response(200, json={"response": "<<<broken non-json output>>>", "done": True}),
            max_retries=1,
        )
        extractor = ScientificPaperExtractor(llm_provider=provider, chunk_retries=1)
        result = await extractor.extract_document(doc)

        assert result.extraction_status == "failed"
        assert result.failed_chunks == 1
        assert len(result.warnings) >= 1

    asyncio.run(run())


def test_claim_with_no_supporting_passage_not_stored_as_verified_evidence() -> None:
    """Verify claims lacking a verifiable source quote are marked unverified and excluded from supporting_passages."""
    doc = _make_synthetic_doc([SYNTHETIC_PAGE_1, SYNTHETIC_PAGE_2], doc_id="doc_unverified_claim")

    payload = {
        "paper_title": "Sparse Graph Attention for Clinical Time-Series Forecasting",
        "main_findings": [
            {
                "author_claim": "The model cured all patients in the hospital.",
                "model_interpretation": "Overstated unsupported claim.",
                "supporting_quote": "This sentence does not exist anywhere in the paper.",
                "page_number": 1,
            },
            {
                "author_claim": "SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split.",
                "model_interpretation": "Supported empirical finding.",
                "supporting_quote": "SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split",
                "page_number": 2,
            },
        ],
    }

    async def run() -> None:
        provider = _mock_ollama_provider(
            lambda _: httpx.Response(200, json={"response": json.dumps(payload), "done": True})
        )
        extractor = ScientificPaperExtractor(llm_provider=provider)
        result = await extractor.extract_document(doc)

        assert len(result.main_findings) == 2
        unsupported, supported = result.main_findings[0], result.main_findings[1]

        # Unsupported claim is flagged unverified and stripped of fabricated quote/page
        assert unsupported.verified_in_source is False
        assert unsupported.supporting_quote is None
        assert unsupported.page_number is None

        # Supported claim is verified and retained in supporting_passages
        assert supported.verified_in_source is True
        assert supported.page_number == 2
        assert len(result.supporting_passages) == 1
        assert result.supporting_passages[0].page_number == 2
        assert (
            result.supporting_passages[0].quote
            == "SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split"
        )

    asyncio.run(run())


def test_numeric_results_and_units_preserved_exactly() -> None:
    """Verify exact numeric values and units are preserved and fabricated numbers are discarded."""
    doc = _make_synthetic_doc([SYNTHETIC_PAGE_1, SYNTHETIC_PAGE_2], doc_id="doc_numeric")

    payload = {
        "quantitative_results": [
            {
                "metric_name": "Mean Inference Latency",
                "value": "14.2",
                "unit": "ms",
                "context": "SparseGAT-ICU per patient record",
                "supporting_quote": "reduced mean inference latency to 14.2 ms per patient record",
                "page_number": 2,
            },
            {
                "metric_name": "Baseline Latency",
                "value": "31.8",
                "unit": "ms",
                "context": "Standard Transformer",
                "supporting_quote": "compared to 31.8 ms for Standard Transformer.",
                "page_number": 2,
            },
            {
                "metric_name": "Fabricated Accuracy",
                "value": "99.99",
                "unit": "%",
                "context": "Hallucinated metric",
                "supporting_quote": "reduced mean inference latency to 14.2 ms per patient record",
                "page_number": 2,
            },
        ]
    }

    async def run() -> None:
        provider = _mock_ollama_provider(
            lambda _: httpx.Response(200, json={"response": json.dumps(payload), "done": True})
        )
        extractor = ScientificPaperExtractor(llm_provider=provider)
        result = await extractor.extract_document(doc)

        # Only the 2 genuine numeric results appear; the fabricated 99.99% is discarded
        assert len(result.quantitative_results) == 2
        assert result.quantitative_results[0].value == "14.2"
        assert result.quantitative_results[0].unit == "ms"
        assert result.quantitative_results[0].page_number == 2

        assert result.quantitative_results[1].value == "31.8"
        assert result.quantitative_results[1].unit == "ms"
        assert result.quantitative_results[1].page_number == 2

    asyncio.run(run())


def test_partially_failed_extraction_across_chunks() -> None:
    """Verify that when one chunk succeeds and another chunk fails, status is 'partial' and findings are kept."""
    doc = _make_synthetic_doc([SYNTHETIC_PAGE_1, SYNTHETIC_PAGE_2], doc_id="doc_partial")

    call_idx = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            # Chunk 1 (Page 1) succeeds
            chunk_1_data = {
                "paper_title": "Sparse Graph Attention for Clinical Time-Series Forecasting",
                "sample_size": "N = 320 patients",
                "sample_size_quote": "comprising N = 320 patients monitored across 48 hours.",
                "sample_size_page": 1,
                "dataset_or_material": ["PhysioNet-2019 clinical cohort"],
            }
            return httpx.Response(200, json={"response": json.dumps(chunk_1_data), "done": True})
        # Chunk 2 (Page 2) fails on all attempts
        return httpx.Response(200, json={"response": "<<<invalid json on chunk 2>>>", "done": True})

    async def run() -> None:
        provider = _mock_ollama_provider(handler, max_retries=0)
        # Force each ~550-char page into its own chunk by setting max_chunk_chars=700
        extractor = ScientificPaperExtractor(
            llm_provider=provider,
            max_chunk_chars=700,
            chunk_retries=0,
        )
        result = await extractor.extract_document(doc)

        assert result.chunk_count == 2
        assert result.failed_chunks == 1
        assert result.extraction_status == "partial"
        assert result.paper_title == "Sparse Graph Attention for Clinical Time-Series Forecasting"
        assert result.sample_size == "N = 320 patients"
        assert result.page_numbers == [1]
        assert any("Chunk 2" in w for w in result.warnings)

    asyncio.run(run())


def test_gemini_provider_extraction_and_header_security() -> None:
    """Verify GeminiProvider works with ScientificPaperExtractor and sends x-goog-api-key in headers only."""
    doc = _make_synthetic_doc([SYNTHETIC_PAGE_1, SYNTHETIC_PAGE_2], doc_id="doc_gemini001")

    gemini_json_output = {
        "title": "Sparse Graph Attention for Clinical Time-Series Forecasting",
        "methodology": "5-fold patient-stratified cross-validation using SparseGAT-ICU",
        "datasets": ["PhysioNet-2019 clinical cohort"],
        "sample_size": "N = 320 patients",
        "architecture": "SparseGAT-ICU",
        "baselines": ["GRU-D", "Standard Transformer"],
        "metrics": ["AUROC", "AUPRC"],
        "result_metric": "AUROC",
        "result_value": "0.891",
        "finding_claim": "SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split.",
        "finding_interpretation": "Improves accuracy while reducing attention overhead.",
        "finding_quote": "SparseGAT-ICU achieved an AUROC of 0.891 on the held-out test split",
        "future_work": ["Federated multi-hospital training."],
    }

    def gemini_handler(request: httpx.Request) -> httpx.Response:
        # API key must be in x-goog-api-key header, NEVER in URL query parameters
        assert request.headers.get("x-goog-api-key") == "test-secret-gemini-key"
        assert "test-secret-gemini-key" not in str(request.url)
        body = json.loads(request.content.decode("utf-8"))
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps(gemini_json_output)}],
                        }
                    }
                ]
            },
        )

    async def run() -> None:
        transport = httpx.MockTransport(gemini_handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            provider = GeminiProvider(
                api_key="test-secret-gemini-key",
                model_name="gemini-2.5-flash",
                http_client=http_client,
            )
            extractor = ScientificPaperExtractor(llm_provider=provider)
            result = await extractor.extract_document(doc)

        assert result.extraction_status == "completed"
        assert result.paper_title == "Sparse Graph Attention for Clinical Time-Series Forecasting"
        assert result.sample_size == "N = 320 patients"
        assert result.quantitative_results[0].value == "0.891"
        assert result.page_numbers == [1, 2]

    asyncio.run(run())

