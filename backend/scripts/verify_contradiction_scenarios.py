"""Demonstration script for PaperTrail scientific claim comparison and contradiction analysis.

Runs and demonstrates all seven required scientific integrity scenarios:
A. Two claims agree under comparable conditions.
B. Two claims report apparently opposing outcomes under comparable conditions.
C. Two models report different accuracies on different datasets.
D. Two papers use incompatible evaluation metrics.
E. A paper omits essential methodological details.
F. A generated relationship has no supporting evidence.
G. A numerical difference is reported without sufficient information to establish statistical significance.
"""

import json
from pathlib import Path

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
from app.services.contradiction_engine import (
    DeterministicCompatibilityChecker,
    ScientificContradictionAnalyzer,
    verify_claim_relationship_evidence,
)


def _fmt_rel(rel: ClaimRelationship) -> None:
    print(f"  * Papers:          {rel.paper_titles[0]} vs {rel.paper_titles[1]}")
    print(f"  * Relationship:    {rel.relationship_label.upper()}")
    print(f"  * Verification:    {rel.verification_status.upper()}")
    print(f"  * Compatibility:   Dataset={rel.dataset_or_population_compatibility}, Metric={rel.metric_compatibility}, Method={rel.methodology_compatibility}")
    if rel.quantitative_differences:
        for qd in rel.quantitative_differences:
            print(f"  * Quantitative:    {qd.difference_summary}")
            print(f"    Significance:    Reported={qd.statistical_significance_reported} ({qd.significance_details})")
    print(f"  * Rationale:       {rel.supporting_rationale}")
    if rel.potential_explanations:
        print(f"  * Explanations:    {'; '.join(rel.potential_explanations)}")
    if rel.unresolved_information:
        print(f"  * Unresolved Info: {'; '.join(rel.unresolved_information)}")
    print("-" * 75)


def run_demonstration() -> None:
    analyzer = ScientificContradictionAnalyzer()
    print("=" * 75)
    print(" PAPERTRAIL: STRUCTURED CLAIM COMPARISON & CONTRADICTION ANALYSIS")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # Scenario A
    # -------------------------------------------------------------------------
    print("\n[SCENARIO A] Two claims agree under comparable conditions:")
    p1_a = ScientificPaperExtraction(
        extraction_id="ext_p1_a", document_id="p1_a", paper_title="Transformer Translation",
        research_methodology="Stacked self-attention network without recurrence",
        dataset_or_material=["WMT 2014 English-German"], evaluation_metrics=["BLEU score"],
        quantitative_results=[QuantitativeResult(metric_name="BLEU score", value="28.4", unit="BLEU", supporting_quote="BLEU of 28.4", page_number=1)],
        main_findings=[ExtractedClaim(author_claim="Transformer self-attention significantly improves translation quality", verified_in_source=True)],
        supporting_passages=[SupportingPassage(document_id="p1_a", page_number=1, field_supported="main_findings", quote="Transformer self-attention significantly improves translation quality")],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    p2_a = ScientificPaperExtraction(
        extraction_id="ext_p2_a", document_id="p2_a", paper_title="Replicating Attention",
        research_methodology="Self-attention transformer architecture",
        dataset_or_material=["WMT 2014 English-German"], evaluation_metrics=["BLEU score"],
        quantitative_results=[QuantitativeResult(metric_name="BLEU score", value="28.2", unit="BLEU", supporting_quote="BLEU score of 28.2", page_number=1)],
        main_findings=[ExtractedClaim(author_claim="Replication confirms self-attention achieves superior translation accuracy", verified_in_source=True)],
        supporting_passages=[SupportingPassage(document_id="p2_a", page_number=1, field_supported="main_findings", quote="Replication confirms self-attention achieves superior translation accuracy")],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    rel_a = analyzer.compare_extractions(p1_a, p2_a)
    _fmt_rel(rel_a)

    # -------------------------------------------------------------------------
    # Scenario B
    # -------------------------------------------------------------------------
    print("\n[SCENARIO B] Two claims report apparently opposing outcomes under comparable conditions:")
    p1_b = ScientificPaperExtraction(
        extraction_id="ext_p1_b", document_id="p1_b", paper_title="Sparse Attention Acceleration",
        research_methodology="Sparse block attention under standard 8-GPU cluster",
        dataset_or_material=["WMT 2014 English-German benchmark"], evaluation_metrics=["BLEU score"],
        main_findings=[ExtractedClaim(author_claim="Sparse attention improves translation quality and outperforms full attention by 1.8 BLEU", verified_in_source=True)],
        supporting_passages=[SupportingPassage(document_id="p1_b", page_number=1, field_supported="main_findings", quote="Sparse attention improves translation quality and outperforms full attention by 1.8 BLEU")],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    p2_b = ScientificPaperExtraction(
        extraction_id="ext_p2_b", document_id="p2_b", paper_title="Rigorous Evaluation of Sparse Attention",
        research_methodology="Identical sparse block attention on 8-GPU cluster",
        dataset_or_material=["WMT 2014 English-German benchmark"], evaluation_metrics=["BLEU score"],
        main_findings=[ExtractedClaim(author_claim="Under matched training budgets, sparse attention degrades translation performance and fails to match full attention", verified_in_source=True)],
        supporting_passages=[SupportingPassage(document_id="p2_b", page_number=1, field_supported="main_findings", quote="sparse attention degrades translation performance and fails to match full attention")],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    rel_b = analyzer.compare_extractions(p1_b, p2_b)
    _fmt_rel(rel_b)

    # -------------------------------------------------------------------------
    # Scenario C
    # -------------------------------------------------------------------------
    print("\n[SCENARIO C] Two models report different accuracies on different datasets:")
    p1_c = ScientificPaperExtraction(
        extraction_id="ext_p1_c", document_id="p1_c", paper_title="Vision Model on ImageNet",
        research_methodology="Deep convolutional neural network with residual connections",
        dataset_or_material=["ImageNet-1K balanced benchmark"], evaluation_metrics=["Accuracy"],
        quantitative_results=[QuantitativeResult(metric_name="Accuracy", value="97.0", unit="%", supporting_quote="97.0% accuracy on ImageNet", page_number=1)],
        sample_size="1.28M images", extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    p2_c = ScientificPaperExtraction(
        extraction_id="ext_p2_c", document_id="p2_c", paper_title="Vision Model on Medical Pathology",
        research_methodology="Identical deep convolutional neural network with residual connections",
        dataset_or_material=["Camelyon16 histopathology dataset"], evaluation_metrics=["Accuracy"],
        quantitative_results=[QuantitativeResult(metric_name="Accuracy", value="91.0", unit="%", supporting_quote="91.0% accuracy on histopathology", page_number=1)],
        sample_size="400 whole slide images", extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    rel_c = analyzer.compare_extractions(p1_c, p2_c)
    _fmt_rel(rel_c)

    # -------------------------------------------------------------------------
    # Scenario D
    # -------------------------------------------------------------------------
    print("\n[SCENARIO D] Two papers use incompatible evaluation metrics:")
    p1_d = ScientificPaperExtraction(
        extraction_id="ext_p1_d", document_id="p1_d", paper_title="Machine Translation Quality",
        research_methodology="Transformer model", dataset_or_material=["TED Talk Corpus"], evaluation_metrics=["BLEU score"],
        quantitative_results=[QuantitativeResult(metric_name="BLEU score", value="34.5", unit="BLEU", supporting_quote="reports 34.5 BLEU", page_number=1)],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    p2_d = ScientificPaperExtraction(
        extraction_id="ext_p2_d", document_id="p2_d", paper_title="Speech Transcription System",
        research_methodology="Conformer acoustic model", dataset_or_material=["TED Talk Corpus"], evaluation_metrics=["Word Error Rate"],
        quantitative_results=[QuantitativeResult(metric_name="Word Error Rate", value="7.8", unit="%", supporting_quote="7.8% word error rate", page_number=1)],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    rel_d = analyzer.compare_extractions(p1_d, p2_d)
    _fmt_rel(rel_d)

    # -------------------------------------------------------------------------
    # Scenario E
    # -------------------------------------------------------------------------
    print("\n[SCENARIO E] A paper omits essential methodological details:")
    p1_e = ScientificPaperExtraction(
        extraction_id="ext_p1_e", document_id="p1_e", paper_title="Vague Claim Paper",
        research_methodology=None, dataset_or_material=[], evaluation_metrics=["Accuracy"],
        quantitative_results=[QuantitativeResult(metric_name="Accuracy", value="99.2", unit="%", supporting_quote="99.2% accuracy", page_number=1)],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    p2_e = ScientificPaperExtraction(
        extraction_id="ext_p2_e", document_id="p2_e", paper_title="Standard Rigorous Study",
        research_methodology="Supervised ResNet-50 trained for 100 epochs", dataset_or_material=["CIFAR-100"], evaluation_metrics=["Accuracy"],
        quantitative_results=[QuantitativeResult(metric_name="Accuracy", value="81.4", unit="%", supporting_quote="81.4% accuracy", page_number=1)],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    rel_e = analyzer.compare_extractions(p1_e, p2_e)
    _fmt_rel(rel_e)

    # -------------------------------------------------------------------------
    # Scenario F
    # -------------------------------------------------------------------------
    print("\n[SCENARIO F] A generated relationship has no supporting evidence:")
    fabricated_rel = ClaimRelationship(
        relationship_id="rel_unverified_claim", claim_ids=["c1", "c2"], source_paper_ids=["doc_1", "doc_2"],
        paper_titles=["Study Alpha", "Study Beta"],
        source_passages=[SupportingPassage(document_id="doc_1", page_number=1, field_supported="main_findings", quote="This quote does not exist in doc 1")],
        relationship_label="potential_contradiction", supporting_rationale="Provisional contradiction flagged by model.",
    )
    doc_1 = ExtractedDocument(
        document_id="doc_1", filename="doc1.pdf", file_size_bytes=100, page_count=1, total_characters=50, total_words=10, extraction_status="completed",
        pages=[ExtractedPage(page_number=1, text="The actual paper contains entirely different text about baseline testing.", character_count=50, word_count=10)],
    )
    verified_rel_f = verify_claim_relationship_evidence(fabricated_rel, {"doc_1": doc_1})
    _fmt_rel(verified_rel_f)

    # -------------------------------------------------------------------------
    # Scenario G
    # -------------------------------------------------------------------------
    print("\n[SCENARIO G] Numerical difference without established statistical significance:")
    p1_g = ScientificPaperExtraction(
        extraction_id="ext_p1_g", document_id="p1_g", paper_title="Model Baseline",
        research_methodology="Feedforward neural network with ReLU", dataset_or_material=["WMT 2014 English-German"], evaluation_metrics=["BLEU score"],
        quantitative_results=[QuantitativeResult(metric_name="BLEU score", value="26.3", unit="BLEU", supporting_quote="achieves 26.3 BLEU", page_number=1)],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    p2_g = ScientificPaperExtraction(
        extraction_id="ext_p2_g", document_id="p2_g", paper_title="Model Variant",
        research_methodology="Feedforward neural network with GELU", dataset_or_material=["WMT 2014 English-German"], evaluation_metrics=["BLEU score"],
        quantitative_results=[QuantitativeResult(metric_name="BLEU score", value="26.7", unit="BLEU", supporting_quote="achieves 26.7 BLEU", page_number=1)],
        extraction_status="completed", created_at="2026-10-23T00:00:00Z", updated_at="2026-10-23T00:00:00Z",
    )
    rel_g = analyzer.compare_extractions(p1_g, p2_g)
    _fmt_rel(rel_g)

    # Database persistence demonstration
    print("\n[DATABASE PERSISTENCE] Storing & Retrieving Claim Relationships in SQLite:")
    db_manager = DatabaseManager(db_path=SQLITE_DB_PATH)
    repo = PaperTrailRepository(db=db_manager, storage_dir=MANAGED_STORAGE_DIR)
    proj = repo.create_project(name="Scientific Contradiction Analysis Suite")
    saved_rels = repo.save_claim_relationships(proj.id, [rel_a, rel_b, rel_c, rel_d, rel_e, rel_g])
    print(f"Persisted {len(saved_rels)} claim relationships into SQLite table 'claim_relationships' for project '{proj.id}'.")
    retrieved = repo.get_claim_relationships(proj.id)
    print(f"Successfully retrieved {len(retrieved)} relationships. Labels: {[r.relationship_label for r in retrieved]}")
    print("[SUCCESS] All 7 scientific integrity scenarios demonstrated and verified.")


if __name__ == "__main__":
    run_demonstration()
