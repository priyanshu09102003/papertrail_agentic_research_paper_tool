"""Comprehensive tests for scientific comparison, compatibility checking, and contradiction analysis.

Validates the 7 required scientific integrity scenarios:
A. Two claims agree under comparable conditions.
B. Two claims report apparently opposing outcomes under comparable conditions.
C. Two models report different accuracies on different datasets.
D. Two papers use incompatible evaluation metrics.
E. A paper omits essential methodological details.
F. A generated relationship has no supporting evidence.
G. A numerical difference is reported without sufficient information to establish statistical significance.
"""

from pathlib import Path
import pytest

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


@pytest.fixture
def temp_repo(tmp_path: Path) -> PaperTrailRepository:
    db = DatabaseManager(db_path=tmp_path / "test_contradictions.db")
    return PaperTrailRepository(db=db, storage_dir=tmp_path / "uploads")


def _make_extraction(
    doc_id: str,
    title: str,
    methodology: str | None = None,
    datasets: list[str] | None = None,
    metrics: list[str] | None = None,
    quant_results: list[QuantitativeResult] | None = None,
    findings: list[ExtractedClaim] | None = None,
    passages: list[SupportingPassage] | None = None,
    sample_size: str | None = None,
) -> ScientificPaperExtraction:
    return ScientificPaperExtraction(
        extraction_id=f"ext_{doc_id}",
        document_id=doc_id,
        paper_title=title,
        research_methodology=methodology,
        dataset_or_material=datasets or [],
        evaluation_metrics=metrics or [],
        quantitative_results=quant_results or [],
        main_findings=findings or [],
        supporting_passages=passages or [],
        sample_size=sample_size,
        page_numbers=[1],
        extraction_status="completed",
        chunk_count=1,
        failed_chunks=0,
        warnings=[],
        created_at="2026-10-23T00:00:00Z",
        updated_at="2026-10-23T00:00:00Z",
    )


# -----------------------------------------------------------------------------
# Scenario A: Two claims agree under comparable conditions
# -----------------------------------------------------------------------------
def test_scenario_a_agreement_under_comparable_conditions() -> None:
    analyzer = ScientificContradictionAnalyzer()

    p1 = _make_extraction(
        doc_id="p1",
        title="Transformer Translation",
        methodology="Stacked self-attention network",
        datasets=["WMT 2014 English-German"],
        metrics=["BLEU score"],
        quant_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="28.4",
                unit="BLEU",
                supporting_quote="establishes BLEU of 28.4",
                page_number=1,
            )
        ],
        findings=[
            ExtractedClaim(
                author_claim="Transformer self-attention significantly improves translation quality over baselines",
                verified_in_source=True,
            )
        ],
        passages=[
            SupportingPassage(document_id="p1", page_number=1, field_supported="main_findings", quote="Transformer self-attention significantly improves translation quality over baselines")
        ],
    )

    p2 = _make_extraction(
        doc_id="p2",
        title="Replicating Attention",
        methodology="Self-attention transformer architecture",
        datasets=["WMT 2014 English-German"],
        metrics=["BLEU score"],
        quant_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="28.2",
                unit="BLEU",
                supporting_quote="replicates BLEU score of 28.2",
                page_number=1,
            )
        ],
        findings=[
            ExtractedClaim(
                author_claim="Replication confirms self-attention achieves superior translation accuracy",
                verified_in_source=True,
            )
        ],
        passages=[
            SupportingPassage(document_id="p2", page_number=1, field_supported="main_findings", quote="Replication confirms self-attention achieves superior translation accuracy")
        ],
    )

    rel = analyzer.compare_extractions(p1, p2)
    assert rel.relationship_label == "agreement"
    assert rel.dataset_or_population_compatibility == "compatible"
    assert rel.metric_compatibility == "compatible"
    assert "compatible" in rel.supporting_rationale.lower()


# -----------------------------------------------------------------------------
# Scenario B: Two claims report apparently opposing outcomes under comparable conditions
# -----------------------------------------------------------------------------
def test_scenario_b_opposing_outcomes_under_comparable_conditions() -> None:
    analyzer = ScientificContradictionAnalyzer()

    p1 = _make_extraction(
        doc_id="p1",
        title="Attention Acceleration Study",
        methodology="Sparse attention mechanism under standard 8-GPU cluster",
        datasets=["WMT 2014 English-German benchmark"],
        metrics=["BLEU score"],
        findings=[
            ExtractedClaim(
                author_claim="Sparse attention improves translation quality and outperforms full attention by 1.8 BLEU",
                verified_in_source=True,
            )
        ],
        passages=[
            SupportingPassage(document_id="p1", page_number=1, field_supported="main_findings", quote="Sparse attention improves translation quality and outperforms full attention by 1.8 BLEU")
        ],
    )

    p2 = _make_extraction(
        doc_id="p2",
        title="Rigorous Evaluation of Sparse Attention",
        methodology="Identical sparse attention mechanism on 8-GPU cluster",
        datasets=["WMT 2014 English-German benchmark"],
        metrics=["BLEU score"],
        findings=[
            ExtractedClaim(
                author_claim="Under matched training budgets, sparse attention degrades translation performance and fails to match full attention",
                verified_in_source=True,
            )
        ],
        passages=[
            SupportingPassage(document_id="p2", page_number=1, field_supported="main_findings", quote="sparse attention degrades translation performance and fails to match full attention")
        ],
    )

    rel = analyzer.compare_extractions(p1, p2)
    assert rel.relationship_label == "potential_contradiction"
    assert rel.dataset_or_population_compatibility in ("compatible", "partially_compatible")
    assert "opposing" in rel.supporting_rationale.lower()
    assert len(rel.potential_explanations) >= 1


# -----------------------------------------------------------------------------
# Scenario C: Two models report different accuracies on different datasets
# -----------------------------------------------------------------------------
def test_scenario_c_different_accuracies_on_different_datasets() -> None:
    analyzer = ScientificContradictionAnalyzer()

    p1 = _make_extraction(
        doc_id="p1",
        title="Vision Model on ImageNet",
        methodology="Deep convolutional neural network with residual connections",
        datasets=["ImageNet-1K balanced benchmark"],
        metrics=["Accuracy"],
        quant_results=[
            QuantitativeResult(
                metric_name="Accuracy",
                value="97.0",
                unit="%",
                supporting_quote="achieves 97.0% accuracy on ImageNet",
                page_number=1,
            )
        ],
        sample_size="1.28 million training images",
        passages=[
            SupportingPassage(document_id="p1", page_number=1, field_supported="quantitative_results", quote="achieves 97.0% accuracy on ImageNet")
        ],
    )

    p2 = _make_extraction(
        doc_id="p2",
        title="Vision Model on Medical Pathology",
        methodology="Identical deep convolutional neural network with residual connections",
        datasets=["Camelyon16 histopathology dataset"],
        metrics=["Accuracy"],
        quant_results=[
            QuantitativeResult(
                metric_name="Accuracy",
                value="91.0",
                unit="%",
                supporting_quote="achieves 91.0% accuracy on histopathology",
                page_number=1,
            )
        ],
        sample_size="400 high-resolution whole slide images",
        passages=[
            SupportingPassage(document_id="p2", page_number=1, field_supported="quantitative_results", quote="achieves 91.0% accuracy on histopathology")
        ],
    )

    rel = analyzer.compare_extractions(p1, p2)
    # Scientific Rule 1 & 3: Differing accuracies on different datasets MUST NOT be classified as contradiction!
    assert rel.relationship_label != "potential_contradiction"
    assert rel.relationship_label == "conditional_difference"
    assert rel.dataset_or_population_compatibility == "incompatible"
    assert "different datasets" in rel.supporting_rationale.lower()
    assert any("benchmark divergence" in exp.lower() or "sample size" in exp.lower() for exp in rel.potential_explanations)


# -----------------------------------------------------------------------------
# Scenario D: Two papers use incompatible evaluation metrics
# -----------------------------------------------------------------------------
def test_scenario_d_incompatible_evaluation_metrics() -> None:
    analyzer = ScientificContradictionAnalyzer()

    p1 = _make_extraction(
        doc_id="p1",
        title="Machine Translation Quality",
        methodology="Transformer model",
        datasets=["TED Talk Corpus"],
        metrics=["BLEU score"],
        quant_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="34.5",
                unit="BLEU",
                supporting_quote="reports 34.5 BLEU",
                page_number=1,
            )
        ],
        passages=[
            SupportingPassage(document_id="p1", page_number=1, field_supported="quantitative_results", quote="reports 34.5 BLEU")
        ],
    )

    p2 = _make_extraction(
        doc_id="p2",
        title="Speech Transcription System",
        methodology="Conformer acoustic model",
        datasets=["TED Talk Corpus"],
        metrics=["Word Error Rate"],
        quant_results=[
            QuantitativeResult(
                metric_name="Word Error Rate",
                value="7.8",
                unit="%",
                supporting_quote="achieves 7.8% word error rate",
                page_number=1,
            )
        ],
        passages=[
            SupportingPassage(document_id="p2", page_number=1, field_supported="quantitative_results", quote="achieves 7.8% word error rate")
        ],
    )

    rel = analyzer.compare_extractions(p1, p2)
    # Scientific Rule 2: Do not compare different metrics as if they were equivalent
    assert rel.relationship_label == "incomparable"
    assert rel.metric_compatibility == "incompatible"
    assert "incompatible metrics" in rel.supporting_rationale.lower()


# -----------------------------------------------------------------------------
# Scenario E: A paper omits essential methodological details
# -----------------------------------------------------------------------------
def test_scenario_e_paper_omits_essential_methodology() -> None:
    analyzer = ScientificContradictionAnalyzer()

    p1 = _make_extraction(
        doc_id="p1",
        title="Vague Performance Claim Paper",
        methodology=None,  # OMITTED METHODOLOGY
        datasets=[],        # OMITTED DATASETS
        metrics=["Accuracy"],
        quant_results=[
            QuantitativeResult(
                metric_name="Accuracy",
                value="99.2",
                unit="%",
                supporting_quote="reaches 99.2% accuracy",
                page_number=1,
            )
        ],
    )

    p2 = _make_extraction(
        doc_id="p2",
        title="Standard Rigorous Study",
        methodology="Supervised ResNet-50 trained with Adam optimizer for 100 epochs",
        datasets=["CIFAR-100 benchmark"],
        metrics=["Accuracy"],
        quant_results=[
            QuantitativeResult(
                metric_name="Accuracy",
                value="81.4",
                unit="%",
                supporting_quote="reaches 81.4% accuracy",
                page_number=1,
            )
        ],
    )

    rel = analyzer.compare_extractions(p1, p2)
    # Scientific Rule 8: Missing information must be treated as unknown; classify as unresolved
    assert rel.relationship_label == "unresolved"
    assert len(rel.unresolved_information) >= 1
    assert "omitted" in rel.supporting_rationale.lower()


# -----------------------------------------------------------------------------
# Scenario F: A generated relationship has no supporting evidence
# -----------------------------------------------------------------------------
def test_scenario_f_unsupported_evidence_fails_verification() -> None:
    # A relationship asserts potential_contradiction, but its passage is fabricated/missing
    raw_rel = ClaimRelationship(
        relationship_id="rel_fake",
        claim_ids=["c1", "c2"],
        source_paper_ids=["doc_1", "doc_2"],
        paper_titles=["Paper 1", "Paper 2"],
        source_passages=[
            SupportingPassage(
                document_id="doc_1",
                page_number=1,
                field_supported="main_findings",
                quote="This quote does not exist anywhere in doc 1 text",
            )
        ],
        relationship_label="potential_contradiction",
        supporting_rationale="Claims appear to contradict",
    )

    real_doc1 = ExtractedDocument(
        document_id="doc_1",
        filename="real.pdf",
        file_size_bytes=100,
        page_count=1,
        total_characters=80,
        total_words=10,
        extraction_status="completed",
        pages=[
            ExtractedPage(
                page_number=1,
                text="The actual paper discusses completely different concepts without the claimed quote.",
                character_count=80,
                word_count=10,
            )
        ],
    )

    verified_rel = verify_claim_relationship_evidence(raw_rel, {"doc_1": real_doc1})

    # Scientific Rule 10 & 11: A claim relationship with no verifiable evidence cannot be verified
    assert verified_rel.verification_status == "unverified"
    assert verified_rel.relationship_label == "unresolved"
    assert "evidence audit failed" in verified_rel.supporting_rationale.lower()


# -----------------------------------------------------------------------------
# Scenario G: Numerical difference without establishing statistical significance
# -----------------------------------------------------------------------------
def test_scenario_g_numerical_difference_without_statistical_significance() -> None:
    analyzer = ScientificContradictionAnalyzer()

    # Two papers compare models on same dataset & metric, but report single numeric scores without variance/p-value
    p1 = _make_extraction(
        doc_id="p1",
        title="Model Baseline Evaluation",
        methodology="Feedforward neural network with ReLU",
        datasets=["WMT 2014 English-German"],
        metrics=["BLEU score"],
        quant_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="26.3",
                unit="BLEU",
                supporting_quote="Model achieves 26.3 BLEU on WMT 2014.",
                page_number=1,
            )
        ],
        passages=[
            SupportingPassage(document_id="p1", page_number=1, field_supported="quantitative_results", quote="Model achieves 26.3 BLEU on WMT 2014.")
        ],
    )

    p2 = _make_extraction(
        doc_id="p2",
        title="Model Minor Variant Evaluation",
        methodology="Feedforward neural network with GELU",
        datasets=["WMT 2014 English-German"],
        metrics=["BLEU score"],
        quant_results=[
            QuantitativeResult(
                metric_name="BLEU score",
                value="26.7",
                unit="BLEU",
                supporting_quote="Variant achieves 26.7 BLEU on WMT 2014.",
                page_number=1,
            )
        ],
        passages=[
            SupportingPassage(document_id="p2", page_number=1, field_supported="quantitative_results", quote="Variant achieves 26.7 BLEU on WMT 2014.")
        ],
    )

    rel = analyzer.compare_extractions(p1, p2)
    # Scientific Rule 6 & 1: Difference of 0.4 without p-values/variance MUST NOT be inferred as contradiction
    assert rel.relationship_label != "potential_contradiction"
    assert len(rel.quantitative_differences) == 1
    qd = rel.quantitative_differences[0]
    assert qd.statistical_significance_reported is False
    assert "statistical significance" in qd.significance_details.lower()
    assert any("statistical significance" in info.lower() for info in rel.unresolved_information)


# -----------------------------------------------------------------------------
# Database Persistence Test for Claim Relationships
# -----------------------------------------------------------------------------
def test_claim_relationship_persistence(temp_repo: PaperTrailRepository) -> None:
    project = temp_repo.create_project("Contradiction DB Project")
    p_id = project.id

    rel = ClaimRelationship(
        relationship_id=f"rel_{p_id[:8]}",
        claim_ids=["c1", "c2"],
        source_paper_ids=["doc_1", "doc_2"],
        paper_titles=["Paper 1", "Paper 2"],
        relationship_label="agreement",
        supporting_rationale="Deterministic check confirms agreement on common benchmark.",
        verification_status="verified",
    )

    # Persist
    saved = temp_repo.save_claim_relationships(p_id, [rel], analysis_id=f"analysis_{p_id}")
    assert len(saved) == 1

    # Retrieve
    retrieved = temp_repo.get_claim_relationships(p_id)
    assert len(retrieved) == 1
    assert retrieved[0].relationship_id == rel.relationship_id
    assert retrieved[0].relationship_label == "agreement"
    assert retrieved[0].verification_status == "verified"
