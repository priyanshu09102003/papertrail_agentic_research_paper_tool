"""Demo seed script for PaperTrail interactive claim-to-evidence graph.

Creates a research project with two analyzed research papers:
1. Paper A: "Attention-Based Efficient Translation"
2. Paper B: "Rigorous Evaluation of Sparse Transformers"
Contains real extracted claims, verified evidence passages with page references,
and an analyzed potential contradiction edge.
"""

from app.config import MANAGED_STORAGE_DIR, SQLITE_DB_PATH
from app.db.database import DatabaseManager
from app.db.repository import PaperTrailRepository
from app.schemas import (
    ClaimRelationship,
    ExtractedClaim,
    ExtractedDocument,
    ExtractedPage,
    QuantitativeResult,
    ScientificPaperExtraction,
    SupportingPassage,
)
from app.services.claim_graph import ClaimGraphService


def seed_demo_claim_graph():
    print("=" * 70)
    print(" PAPERTRAIL: SEEDING DEMO PROJECT FOR CLAIM-TO-EVIDENCE GRAPH")
    print("=" * 70)

    db = DatabaseManager(db_path=SQLITE_DB_PATH)
    repo = PaperTrailRepository(db=db, storage_dir=MANAGED_STORAGE_DIR)

    # 1. Create a dedicated demo project
    proj = repo.create_project(name="Sparse Attention Translation Benchmark")
    print(f"[*] Created Project: '{proj.name}' (ID: {proj.id})")

    # 2. Add Paper 1
    pdf_bytes_1 = b"%PDF-1.4\n%Demo PDF for Sparse Attention Acceleration\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    doc1 = ExtractedDocument(
        document_id="doc_sparse_accel",
        project_id=proj.id,
        filename="sparse_attention_acceleration.pdf",
        file_size_bytes=len(pdf_bytes_1),
        page_count=6,
        total_characters=14200,
        total_words=2400,
        extraction_status="completed",
        pages=[
            ExtractedPage(
                page_number=1,
                text="We introduce Sparse Attention which reduces attention complexity from quadratic to sub-quadratic.",
                character_count=100,
                word_count=16,
            ),
            ExtractedPage(
                page_number=3,
                text="On WMT 2014 English-German, our block-sparse attention achieves 28.4 BLEU with 3.2x inference speedup and zero loss in perplexity.",
                character_count=135,
                word_count=21,
            ),
        ],
    )
    saved_doc1 = repo.save_document_and_file(doc1, pdf_bytes_1, project_id=proj.id)

    ext1 = ScientificPaperExtraction(
        extraction_id=f"ext_{saved_doc1.document_id}",
        document_id=saved_doc1.document_id,
        paper_title="Sparse Attention Acceleration in Sequence Models",
        research_methodology="Transformer architecture with fixed block-sparse attention masks",
        dataset_or_material=["WMT 2014 English-German"],
        evaluation_metrics=["BLEU score", "Inference Latency"],
        quantitative_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="28.4",
                unit="BLEU",
                supporting_quote="our block-sparse attention achieves 28.4 BLEU",
                page_number=3,
            )
        ],
        main_findings=[
            ExtractedClaim(
                author_claim="Block-sparse attention accelerates translation inference with zero loss in translation quality or perplexity."
            )
        ],
        supporting_passages=[
            SupportingPassage(
                document_id=saved_doc1.document_id,
                page_number=3,
                field_supported="main_findings",
                quote="On WMT 2014 English-German, our block-sparse attention achieves 28.4 BLEU with 3.2x inference speedup and zero loss in perplexity.",
            )
        ],
        extraction_status="completed",
        created_at="2026-10-23T00:00:00Z",
        updated_at="2026-10-23T00:00:00Z",
    )
    repo.save_scientific_extraction(ext1)
    print(f"[*] Persisted Paper 1: '{ext1.paper_title}' (Doc ID: {saved_doc1.document_id})")

    # 3. Add Paper 2
    pdf_bytes_2 = b"%PDF-1.4\n%Demo PDF for Rigorous Evaluation of Sparse Attention\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    doc2 = ExtractedDocument(
        document_id="doc_sparse_eval",
        project_id=proj.id,
        filename="evaluating_sparse_attention.pdf",
        file_size_bytes=len(pdf_bytes_2),
        page_count=8,
        total_characters=18500,
        total_words=3100,
        extraction_status="completed",
        pages=[
            ExtractedPage(
                page_number=1,
                text="A critical examination of sparsity patterns in sequence models.",
                character_count=65,
                word_count=9,
            ),
            ExtractedPage(
                page_number=4,
                text="Across long-context benchmarks on WMT 2014 English-German, sparse attention patterns induce severe perplexity degradation when context exceeds 512 tokens.",
                character_count=155,
                word_count=22,
            ),
        ],
    )
    saved_doc2 = repo.save_document_and_file(doc2, pdf_bytes_2, project_id=proj.id)

    ext2 = ScientificPaperExtraction(
        extraction_id=f"ext_{saved_doc2.document_id}",
        document_id=saved_doc2.document_id,
        paper_title="A Rigorous Evaluation of Sparse Attention Degradation",
        research_methodology="Standard Transformer baseline compared against block-sparse attention across varying sequence lengths",
        dataset_or_material=["WMT 2014 English-German"],
        evaluation_metrics=["BLEU score", "Perplexity"],
        quantitative_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="26.1",
                unit="BLEU",
                supporting_quote="sparse attention patterns induce severe perplexity degradation",
                page_number=4,
            )
        ],
        main_findings=[
            ExtractedClaim(
                author_claim="Sparse attention induces severe degradation in long-context sequence modeling and translation perplexity."
            )
        ],
        supporting_passages=[
            SupportingPassage(
                document_id=saved_doc2.document_id,
                page_number=4,
                field_supported="main_findings",
                quote="sparse attention patterns induce severe perplexity degradation when context exceeds 512 tokens.",
            )
        ],
        extraction_status="completed",
        created_at="2026-10-23T00:00:00Z",
        updated_at="2026-10-23T00:00:00Z",
    )
    repo.save_scientific_extraction(ext2)
    print(f"[*] Persisted Paper 2: '{ext2.paper_title}' (Doc ID: {saved_doc2.document_id})")

    # 4. Add Cross-Paper Potential Contradiction Relationship
    contra_rel = ClaimRelationship(
        relationship_id=f"rel_{saved_doc1.document_id}_{saved_doc2.document_id}",
        claim_ids=[f"claim_{saved_doc1.document_id}", f"claim_{saved_doc2.document_id}"],
        source_paper_ids=[saved_doc1.document_id, saved_doc2.document_id],
        paper_titles=[ext1.paper_title, ext2.paper_title],
        source_passages=ext1.supporting_passages + ext2.supporting_passages,
        research_question_compatibility="compatible",
        dataset_or_population_compatibility="compatible",
        methodology_compatibility="compatible",
        metric_compatibility="compatible",
        relationship_label="potential_contradiction",
        supporting_rationale=(
            "Under comparable benchmark conditions (WMT 2014 English-German), the two studies report opposing qualitative "
            "and quantitative outcomes. The first paper reports accelerated inference with zero perplexity loss, while the "
            "second paper reports severe degradation in perplexity and translation quality when sequences exceed 512 tokens."
        ),
        potential_explanations=[
            "Sequence length discrepancy: Paper 1 evaluated on standard length (<512 tokens) while Paper 2 tested long-context (>512 tokens).",
            "Differences in attention sparsity mask density and baseline hyperparameter tuning.",
        ],
        unresolved_information=[
            "Whether Paper 1's implementation included dense global tokens for long sequences.",
        ],
        verification_status="verified",
    )
    repo.save_claim_relationships(proj.id, [contra_rel])
    print("[*] Persisted Potential Contradiction Relationship between Paper 1 and Paper 2.")

    # 5. Build and verify the graph via ClaimGraphService
    service = ClaimGraphService(repository=repo)
    graph = service.build_claim_graph(proj.id)

    print("\n" + "=" * 70)
    print(" GRAPH TRANSFORMATION RESULTS:")
    print("=" * 70)
    print(f"  * Total Nodes: {len(graph.nodes)}")
    for n in graph.nodes:
        print(f"    - [{n.type.upper()}] {n.label} (ID: {n.id})")
    print(f"  * Total Edges: {len(graph.edges)}")
    for e in graph.edges:
        contra_tag = " [POTENTIAL CONTRADICTION]" if e.is_contradiction else ""
        print(f"    - ({e.source}) --[{e.relationship_type}]--> ({e.target}){contra_tag}")

    print("\n[SUCCESS] Demo project seeded successfully!")
    print(f"PROJECT_ID: {proj.id}")
    print("Use this PROJECT_ID in the frontend or curl to inspect the live graph.")
    return proj.id


if __name__ == "__main__":
    seed_demo_claim_graph()
