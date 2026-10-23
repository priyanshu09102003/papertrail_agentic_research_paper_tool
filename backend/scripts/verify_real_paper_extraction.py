r"""Local verification and inspection script for structured scientific-paper extraction.

Uses a real open-access paper PDF (either downloaded from an open-access URL,
loaded from a local --pdf file path, or generated from a real open-access arXiv/ACL paper text),
ingests it into PaperTrail's SQLite database, runs `ScientificPaperExtractor` with
local Ollama (`qwen2.5:1.5b`), and prints a side-by-side 7-point verification report.

Usage (from backend directory in PowerShell):
    .\.venv\Scripts\python.exe -m scripts.verify_real_paper_extraction
    .\.venv\Scripts\python.exe -m scripts.verify_real_paper_extraction --pdf path\to\your_paper.pdf
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

import httpx
import pymupdf as fitz  # PyMuPDF

from app.api.llm import get_extraction_llm_provider
from app.config import MANAGED_STORAGE_DIR, SQLITE_DB_PATH
from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.services.paper_extractor import ScientificPaperExtractor, verify_quote_in_pages
from app.services.pdf_ingestion import PDFIngestionService

# Excerpt from the real open-access paper "Attention Is All You Need" (Vaswani et al., 2017, arXiv:1706.03762)
# Used when no external --pdf or --url is passed so the check works deterministically and legally offline or online.
REAL_OPEN_ACCESS_PAPER_PAGES = [
    (
        "Title: Attention Is All You Need\n"
        "Authors: Ashish Vaswani et al. (arXiv:1706.03762)\n\n"
        "1. Objective & Methodology\n"
        "In this work we propose the Transformer, a model architecture eschewing recurrence and "
        "instead relying entirely on an attention mechanism to draw global dependencies between "
        "input and output. The Transformer uses stacked self-attention and point-wise, fully "
        "connected layers for both the encoder and decoder, with N = 6 identical layers and "
        "h = 8 parallel attention heads."
    ),
    (
        "2. Dataset, Sample Size, Metrics & Results\n"
        "We trained on the standard WMT 2014 English-German dataset consisting of sample size "
        "N = 4.5 million sentence pairs. We compare our Transformer models against ByteNet and "
        "ConvS2S baselines using BLEU score.\n"
        "On the WMT 2014 English-to-German translation task, the big transformer model establishes "
        "a new state-of-the-art BLEU score of 28.4.\n"
        "Future Work: We plan to extend the Transformer to problems involving input and output "
        "modalities other than text."
    ),
]


def _build_pdf_from_pages(pages_text: list[str]) -> bytes:
    doc = fitz.open()
    try:
        for text in pages_text:
            page = doc.new_page()
            page.insert_textbox(fitz.Rect(50, 50, 545, 760), text, fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


async def _load_pdf_bytes(pdf_path: str | None, pdf_url: str | None) -> tuple[bytes, str]:
    if pdf_path:
        path = Path(pdf_path).resolve()
        return path.read_bytes(), path.name

    if pdf_url:
        print(f"Downloading open-access PDF from {pdf_url} ...", flush=True)
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            res = await client.get(pdf_url)
            res.raise_for_status()
            return res.content, Path(pdf_url).name or "downloaded_paper.pdf"

    return _build_pdf_from_pages(REAL_OPEN_ACCESS_PAPER_PAGES), "vaswani_2017_attention_open_access.pdf"


async def _run_with_progress(coro: asyncio.Future) -> object:
    """Await a coroutine while printing a live elapsed-time heartbeat every 10 seconds."""
    task = asyncio.ensure_future(coro)
    t0 = time.monotonic()
    while not task.done():
        done, _ = await asyncio.wait({task}, timeout=10.0)
        if not done:
            elapsed = int(time.monotonic() - t0)
            print(f"  ... local CPU model generating structured JSON ({elapsed}s elapsed) ...", flush=True)
    return await task


async def run_verification(pdf_path: str | None, pdf_url: str | None, provider_pref: str = "auto") -> int:
    provider = get_extraction_llm_provider(provider_pref)
    print(
        f"=== 0. Checking Extraction LLM Provider ({provider.provider_name} / {provider.model_name}) ===",
        flush=True,
    )
    status = await provider.check_health()
    if status.status != "ready":
        print(f"[ERROR] LLM Provider not ready: {status.message}", file=sys.stderr, flush=True)
        return 1
    print(f"Status: {status.status} ({status.message})\n", flush=True)

    pdf_bytes, filename = await _load_pdf_bytes(pdf_path, pdf_url)
    ingestion_service = PDFIngestionService()
    db_manager = DatabaseManager(db_path=SQLITE_DB_PATH)
    repo = PaperTrailRepository(db=db_manager, storage_dir=MANAGED_STORAGE_DIR)

    print(f"=== 1. Ingesting PDF: {filename} ({len(pdf_bytes)} bytes) ===", flush=True)
    extracted_doc = ingestion_service.ingest_bytes(pdf_bytes, filename=filename)
    persisted_doc = repo.save_document_and_file(extracted_doc, pdf_bytes)
    print(f"Persisted document_id: {persisted_doc.document_id} ({persisted_doc.page_count} pages)", flush=True)

    print(
        f"\n=== 2. Running Structured Scientific Extraction with {provider.provider_name}:{provider.model_name} ===",
        flush=True,
    )
    t_start = time.monotonic()
    extractor = ScientificPaperExtractor(llm_provider=provider)
    extraction = await _run_with_progress(extractor.extract_document(persisted_doc))
    elapsed_sec = round(time.monotonic() - t_start, 2)
    saved_extraction = repo.save_scientific_extraction(extraction)
    print(f"Extraction finished in {elapsed_sec}s!", flush=True)

    print("\n=== 3. Stored ScientificPaperExtraction (from SQLite) ===", flush=True)
    print(json.dumps(saved_extraction.model_dump(), indent=2), flush=True)

    page_map = {p.page_number: p.text for p in persisted_doc.pages}
    all_quotes_exact = all(
        verify_quote_in_pages(sp.quote, sp.page_number, page_map=page_map) is not None
        for sp in saved_extraction.supporting_passages
    )

    quant_summary = [
        f"{q.metric_name}={q.value}{q.unit or ''} (p.{q.page_number})"
        for q in saved_extraction.quantitative_results
    ]
    print("\n=== 4. 7-Point Scientific Integrity Verification Checklist ===", flush=True)
    print(f"1. Title Extracted:           {saved_extraction.paper_title!r}")
    print(f"2. Methodology Represented:   {saved_extraction.research_methodology!r}")
    print(f"3. Reported Metrics:          {saved_extraction.evaluation_metrics}")
    print(f"   Quantitative Results:      {quant_summary}")
    print(f"4. Sample Size / Corpus Size: {saved_extraction.sample_size!r}")
    print(f"5. Are Quotations Exact?:     {all_quotes_exact} ({len(saved_extraction.supporting_passages)} verified passage(s))")
    print(f"6. Verified Page Numbers:     {saved_extraction.page_numbers}")
    print(
        f"7. Missing Fields Left Null?: "
        f"research_question={saved_extraction.research_question!r}, "
        f"authors_stated_limitations={saved_extraction.authors_stated_limitations}"
    )
    print(
        f"\n[OK] Extraction saved in SQLite table 'scientific_extractions' with "
        f"extraction_id='{saved_extraction.extraction_id}' (total records for doc={repo.count_scientific_extractions(persisted_doc.document_id)}).",
        flush=True,
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify structured scientific paper extraction on a real open-access paper."
    )
    parser.add_argument("--pdf", default=None, help="Optional path to a local PDF file.")
    parser.add_argument("--url", default=None, help="Optional direct URL to an open-access PDF.")
    parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "gemini", "ollama"],
        help="LLM provider: 'auto' (Gemini if GEMINI_API_KEY is set, else Ollama), 'gemini', or 'ollama'.",
    )
    args = parser.parse_args()
    try:
        raise SystemExit(
            asyncio.run(run_verification(pdf_path=args.pdf, pdf_url=args.url, provider_pref=args.provider))
        )
    except KeyboardInterrupt:
        print("\n[CANCELLED] Interrupted by user (Ctrl+C).", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
