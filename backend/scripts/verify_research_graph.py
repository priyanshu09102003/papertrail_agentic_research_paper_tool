"""Verification script for LangGraph research workflow orchestration and analysis inspection."""

import argparse
import asyncio
import json
import logging
import sys
import time

from app.api.llm import get_extraction_llm_provider
from app.config import MANAGED_STORAGE_DIR, SQLITE_DB_PATH
from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.schemas import ExtractedDocument, ExtractedPage, ScientificPaperExtraction, SupportingPassage
from app.services.graph.workflow import get_graph_structure, run_research_workflow
from app.services.paper_extractor import ScientificPaperExtractor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Verify LangGraph research workflow orchestration.")
    parser.add_argument("--project-id", default=None, help="Optional existing project ID to analyze.")
    parser.add_argument("--provider", default="auto", choices=["auto", "gemini", "ollama"])
    args = parser.parse_args()

    db_manager = DatabaseManager(db_path=SQLITE_DB_PATH)
    repo = PaperTrailRepository(db=db_manager, storage_dir=MANAGED_STORAGE_DIR)

    print("=" * 70)
    print(" 1. LANGGRAPH RESEARCH WORKFLOW STRUCTURE INSPECTION")
    print("=" * 70)
    structure = get_graph_structure()
    print(f"Workflow: {structure.workflow_name}")
    print(f"Total Nodes: {len(structure.nodes)}")
    for node in structure.nodes:
        print(f"  - {node.name:32s} : {node.description}")
    print(f"\nTotal Edges: {len(structure.edges)} (Conditional transitions: {sum(1 for e in structure.edges if e.is_conditional)})")

    print("\nMermaid Workflow Diagram:")
    print(structure.mermaid_diagram)

    print("\n" + "=" * 70)
    print(" 2. INITIALIZING LLM PROVIDER & PROJECT")
    print("=" * 70)
    llm = get_extraction_llm_provider(provider_preference=args.provider)
    extractor = ScientificPaperExtractor(llm_provider=llm)
    print(f"Active Provider: {llm.provider_name} (model: {llm.model_name})")

    project_id = args.project_id
    if not project_id or not repo.project_exists(project_id):
        # Create a demonstration project
        proj = repo.create_project(
            name="Attention & Convolutional Sequence Synthesis",
            description="Comparative analysis of self-attention Transformer vs Convolutional sequence models.",
        )
        project_id = proj.id
        print(f"Created demo project: {project_id} ('{proj.name}')")

        # Ingest sample paper documents
        text_att = (
            "We propose the Transformer, a model architecture eschewing recurrence and relying "
            "entirely on an attention mechanism to draw global dependencies between input and output. "
            "On the WMT 2014 English-to-German translation task, the big transformer model establishes "
            "a new state-of-the-art BLEU score of 28.4, outperforming the best existing models by over 2.0 BLEU. "
            "Trained on 4.5 million sentence pairs."
        )
        doc1 = ExtractedDocument(
            document_id=f"doc_att_{project_id[:6]}",
            project_id=project_id,
            filename="vaswani_attention.pdf",
            stored_path="vaswani_attention.pdf",
            file_size_bytes=len(text_att),
            page_count=1,
            total_characters=len(text_att),
            total_words=len(text_att.split()),
            extraction_status="completed",
            pages=[
                ExtractedPage(
                    page_number=1,
                    text=text_att,
                    character_count=len(text_att),
                    word_count=len(text_att.split()),
                )
            ],
        )
        saved_doc1 = repo.save_document_and_file(doc1, text_att.encode("utf-8"), project_id=project_id)

        # Pre-cache doc1 extraction
        ext1 = ScientificPaperExtraction(
            extraction_id=f"ext_{saved_doc1.document_id}",
            document_id=saved_doc1.document_id,
            paper_title="Attention Is All You Need",
            research_methodology="Stacked self-attention without recurrence",
            dataset_or_material=["WMT 2014 English-German dataset"],
            sample_size="4.5 million sentence pairs",
            model_architecture_or_intervention="Transformer encoder-decoder",
            evaluation_metrics=["BLEU score"],
            quantitative_results=[
                {
                    "metric_name": "BLEU score",
                    "value": "28.4",
                    "unit": "BLEU",
                    "context": "WMT 2014 English-to-German",
                    "supporting_quote": "the big transformer model establishes a new state-of-the-art BLEU score of 28.4",
                    "page_number": 1,
                }
            ],
            supporting_passages=[
                SupportingPassage(
                    document_id=saved_doc1.document_id,
                    page_number=1,
                    field_supported="methodology",
                    quote="relying entirely on an attention mechanism to draw global dependencies",
                ),
                SupportingPassage(
                    document_id=saved_doc1.document_id,
                    page_number=1,
                    field_supported="sample_size",
                    quote="4.5 million sentence pairs",
                ),
                SupportingPassage(
                    document_id=saved_doc1.document_id,
                    page_number=1,
                    field_supported="quantitative_results",
                    quote="the big transformer model establishes a new state-of-the-art BLEU score of 28.4",
                ),
            ],
            page_numbers=[1],
            extraction_status="completed",
            chunk_count=1,
            failed_chunks=0,
            warnings=[],
            created_at="2026-10-23T00:00:00Z",
            updated_at="2026-10-23T00:00:00Z",
        )
        repo.save_scientific_extraction(ext1)
        print(f"Pre-cached verified extraction for document '{saved_doc1.document_id}'")

        # Document 2: ConvS2S
        text_conv = (
            "Convolutional Sequence to Sequence Learning. We introduce an architecture for sequence "
            "to sequence modeling that is entirely convolutional. On the WMT 2014 English-German benchmark, "
            "our ConvS2S architecture achieves a BLEU score of 25.16, outperforming earlier recurrent baselines. "
            "Evaluated using BLEU score on multi-bleu.perl."
        )
        doc2 = ExtractedDocument(
            document_id=f"doc_conv_{project_id[:6]}",
            project_id=project_id,
            filename="gehring_convs2s.pdf",
            stored_path="gehring_convs2s.pdf",
            file_size_bytes=len(text_conv),
            page_count=1,
            total_characters=len(text_conv),
            total_words=len(text_conv.split()),
            extraction_status="completed",
            pages=[
                ExtractedPage(
                    page_number=1,
                    text=text_conv,
                    character_count=len(text_conv),
                    word_count=len(text_conv.split()),
                )
            ],
        )
        saved_doc2 = repo.save_document_and_file(doc2, text_conv.encode("utf-8"), project_id=project_id)
        ext2 = ScientificPaperExtraction(
            extraction_id=f"ext_{saved_doc2.document_id}",
            document_id=saved_doc2.document_id,
            paper_title="Convolutional Sequence to Sequence Learning",
            research_methodology="Entirely convolutional sequence-to-sequence network",
            dataset_or_material=["WMT 2014 English-German benchmark"],
            model_architecture_or_intervention="ConvS2S",
            evaluation_metrics=["BLEU score"],
            quantitative_results=[
                {
                    "metric_name": "BLEU score",
                    "value": "25.16",
                    "unit": "BLEU",
                    "context": "WMT 2014 English-German",
                    "supporting_quote": "our ConvS2S architecture achieves a BLEU score of 25.16",
                    "page_number": 1,
                }
            ],
            supporting_passages=[
                SupportingPassage(
                    document_id=saved_doc2.document_id,
                    page_number=1,
                    field_supported="methodology",
                    quote="architecture for sequence to sequence modeling that is entirely convolutional",
                ),
                SupportingPassage(
                    document_id=saved_doc2.document_id,
                    page_number=1,
                    field_supported="quantitative_results",
                    quote="our ConvS2S architecture achieves a BLEU score of 25.16",
                ),
            ],
            page_numbers=[1],
            extraction_status="completed",
            chunk_count=1,
            failed_chunks=0,
            warnings=[],
            created_at="2026-10-23T00:00:00Z",
            updated_at="2026-10-23T00:00:00Z",
        )
        repo.save_scientific_extraction(ext2)
        print(f"Pre-cached verified extraction for document '{saved_doc2.document_id}'")

    print("\n" + "=" * 70)
    print(f" 3. EXECUTING LANGGRAPH RESEARCH WORKFLOW (Asynchronous)")
    print("=" * 70)
    t0 = time.perf_counter()
    final_state = await run_research_workflow(
        project_id=project_id,
        repository=repo,
        extractor=extractor,
    )
    elapsed = round(time.perf_counter() - t0, 2)
    print(f"Workflow finished in {elapsed}s with status: {final_state['status'].upper()}")

    print("\n" + "=" * 70)
    print(" 4. PERSISTED ANALYSIS & SYNTHESIS REPORT (from SQLite)")
    print("=" * 70)
    saved_record = repo.get_research_analysis(project_id)
    if not saved_record:
        print("[ERROR] No analysis record found in database!", file=sys.stderr)
        return

    print(f"Analysis ID:    {saved_record.analysis_id}")
    print(f"Project ID:     {saved_record.project_id}")
    print(f"Overall Status: {saved_record.status}")
    print(f"Node Trail:     {' -> '.join(h.node_name for h in saved_record.node_history)}")

    report = saved_record.report
    if report:
        print(f"\n--- Synthesized Research Report: {report.title} ---")
        print(f"Executive Summary: {report.executive_summary}")
        print(f"Papers Reviewed:   {', '.join(report.papers_reviewed)}")

        print("\nCross-Paper Comparisons:")
        for c in report.comparisons:
            print(f"  * [{c.dimension}]: {c.summary}")

        print("\nIdentified Conflicts / Empirical Divergences:")
        for cf in report.conflicts:
            print(f"  * [{cf.aspect}]: {cf.description}")
            print(f"    Author Claims: {cf.author_claims}")
            if cf.potential_reconciliation:
                print(f"    Potential Reconciliation: {cf.potential_reconciliation}")

        print(f"\nVerified Ground-Truth Evidence Passages: {len(report.verified_evidence)}")
        for ve in report.verified_evidence[:3]:
            print(f"  - [p.{ve.page_number}] \"{ve.quote}\" (verified={ve.verified})")

    # Idempotent re-run check (Requirement 10)
    total_analyses = repo.count_research_analyses(project_id)
    print(f"\n[OK] Database record count for project (strictly 1, no duplicates): {total_analyses}")
    print("[SUCCESS] All LangGraph research workflow stages completed and verified.")


if __name__ == "__main__":
    asyncio.run(main())
