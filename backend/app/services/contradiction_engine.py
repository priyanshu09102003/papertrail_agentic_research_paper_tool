"""Structured scientific comparison and potential contradiction analysis engine.

Adheres strictly to the scientific integrity principles:
1. Do not infer contradiction merely because numeric results differ.
2. Do not compare different metrics as if they were equivalent.
3. Do not compare results from different datasets without acknowledging the difference.
4. Do not treat correlation as causation.
5. Do not assume that one paper is correct and another is incorrect.
6. Distinguish statistical significance from practical importance.
7. Preserve uncertainty and limitations.
8. Treat missing information as unknown.
9. Never fabricate supporting evidence.
10. Every proposed contradiction must link to claims and source passages.
11. Provisional relationship labels must be validated by evidence verification.
12. Do not substitute single numerical scores for evidence.
13. Explain methodological differences affecting comparability.
14. If evidence is insufficient, classify as 'unresolved' or 'incomparable'.
"""

import hashlib
import logging
import re
from typing import Any

from app.schemas import (
    ClaimRelationship,
    ClaimRelationshipLabel,
    CompatibilityLevel,
    ExtractedClaim,
    ExtractedDocument,
    QuantitativeDifference,
    QuantitativeResult,
    ScientificPaperExtraction,
    SupportingPassage,
    VerificationStatus,
)
from app.services.paper_extractor import verify_quote_in_pages

logger = logging.getLogger(__name__)

_SIGNIFICANCE_KEYWORDS = ("p<", "p <", "p=", "p =", "p-value", "p value", "ci", "confidence interval", "std", "variance", "standard deviation", "stderr", "±")
_OPPOSING_POSITIVE_RE = re.compile(r"\b(improve|improves|improved|outperform|outperforms|superior|gain|boost|effective|better)\b", re.IGNORECASE)
_OPPOSING_NEGATIVE_RE = re.compile(r"\b(degrade|degrades|degraded|inferior|worse|decline|drop|fails|ineffective|no improvement)\b", re.IGNORECASE)


def _normalize_name(name: str) -> str:
    """Normalize text token for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _are_metrics_compatible(m1: str, m2: str) -> bool:
    """Determine whether two evaluation metric strings refer to the same comparable measurement."""
    norm1 = _normalize_name(m1)
    norm2 = _normalize_name(m2)
    if norm1 == norm2:
        return True
    # Group standard aliases
    bleu_group = {"bleu", "bleuscore", "multibleu"}
    acc_group = {"accuracy", "top1accuracy", "top1acc", "exactmatch", "em"}
    f1_group = {"f1", "f1score", "macrof1", "microf1"}
    wer_group = {"wer", "worderrorrate"}
    loss_group = {"loss", "crossentropyloss", "perplexity", "ppl"}

    for group in (bleu_group, acc_group, f1_group, wer_group, loss_group):
        if norm1 in group and norm2 in group:
            return True
    return False


def _are_datasets_compatible(d1_list: list[str], d2_list: list[str]) -> tuple[CompatibilityLevel, str]:
    """Check dataset compatibility between two papers."""
    if not d1_list or not d2_list:
        return "unknown", "Dataset or experimental material was omitted in one or more papers."

    norm_d1 = {_normalize_name(d) for d in d1_list if d.strip()}
    norm_d2 = {_normalize_name(d) for d in d2_list if d.strip()}

    if not norm_d1 or not norm_d2:
        return "unknown", "Dataset details were omitted or empty."

    # Direct overlap
    overlap = norm_d1.intersection(norm_d2)
    if overlap:
        return "compatible", f"Both papers evaluate on common dataset/benchmark: {', '.join(d1_list)}."

    # Partial / subset matching
    for item1 in norm_d1:
        for item2 in norm_d2:
            if item1 in item2 or item2 in item1:
                return "partially_compatible", f"Datasets share common benchmark family: '{', '.join(d1_list)}' and '{', '.join(d2_list)}'."

    return "incompatible", f"Different datasets/populations used: '{', '.join(d1_list)}' vs '{', '.join(d2_list)}'."


class DeterministicCompatibilityChecker:
    """Examines research questions, datasets, settings, and metrics before analyzing conflicts."""

    @staticmethod
    def evaluate(
        p1: ScientificPaperExtraction,
        p2: ScientificPaperExtraction,
    ) -> dict[str, Any]:
        """Perform deterministic compatibility checks across two extracted papers."""
        unresolved: list[str] = []

        # 1. Research Question Compatibility
        if not p1.research_question or not p2.research_question:
            rq_comp: CompatibilityLevel = "unknown"
            if not p1.research_question:
                unresolved.append(f"Research question was not explicitly stated in {p1.paper_title or p1.document_id}.")
            if not p2.research_question:
                unresolved.append(f"Research question was not explicitly stated in {p2.paper_title or p2.document_id}.")
        else:
            q1_norm = _normalize_name(p1.research_question)
            q2_norm = _normalize_name(p2.research_question)
            rq_comp = "compatible" if (q1_norm in q2_norm or q2_norm in q1_norm or len(set(q1_norm) & set(q2_norm)) > 15) else "partially_compatible"

        # 2. Dataset / Population Compatibility
        ds_comp, ds_note = _are_datasets_compatible(p1.dataset_or_material, p2.dataset_or_material)
        if ds_comp == "unknown":
            unresolved.append("Dataset or experimental material omitted in one or both papers.")

        # 3. Methodology Compatibility & Essential Details Check
        p1_has_method = bool(p1.research_methodology and len(p1.research_methodology.strip()) > 5)
        p2_has_method = bool(p2.research_methodology and len(p2.research_methodology.strip()) > 5)

        if not p1_has_method or not p2_has_method:
            method_comp: CompatibilityLevel = "unknown"
            if not p1_has_method:
                unresolved.append(f"Essential methodological details omitted in {p1.paper_title or p1.document_id}.")
            if not p2_has_method:
                unresolved.append(f"Essential methodological details omitted in {p2.paper_title or p2.document_id}.")
        else:
            method_comp = "compatible"

        # 4. Metric Compatibility
        p1_metrics = [m for m in p1.evaluation_metrics if m.strip()]
        p2_metrics = [m for m in p2.evaluation_metrics if m.strip()]

        if not p1_metrics or not p2_metrics:
            # Check quantitative results for metrics if evaluation_metrics list was omitted
            p1_q_metrics = [q.metric_name for q in p1.quantitative_results if q.metric_name.strip()]
            p2_q_metrics = [q.metric_name for q in p2.quantitative_results if q.metric_name.strip()]
            p1_metrics = p1_metrics or p1_q_metrics
            p2_metrics = p2_metrics or p2_q_metrics

        if not p1_metrics or not p2_metrics:
            metric_comp: CompatibilityLevel = "unknown"
            unresolved.append("Evaluation metrics were not explicitly reported in one or both papers.")
            shared_metrics: list[str] = []
        else:
            shared_metrics = [
                m1 for m1 in p1_metrics for m2 in p2_metrics if _are_metrics_compatible(m1, m2)
            ]
            if shared_metrics:
                metric_comp = "compatible"
            else:
                metric_comp = "incompatible"

        # 5. Check Statistical Significance & Uncertainty reporting
        significance_found = False
        all_text = " ".join(
            (p1.research_methodology or "") + " " + (p2.research_methodology or "") + " " +
            " ".join(sp.quote for sp in p1.supporting_passages + p2.supporting_passages)
        ).lower()

        for kw in _SIGNIFICANCE_KEYWORDS:
            if kw in all_text:
                significance_found = True
                break

        return {
            "research_question_compatibility": rq_comp,
            "dataset_or_population_compatibility": ds_comp,
            "dataset_note": ds_note,
            "methodology_compatibility": method_comp,
            "metric_compatibility": metric_comp,
            "shared_metrics": shared_metrics,
            "statistical_significance_reported": significance_found,
            "unresolved_information": unresolved,
        }


class ScientificContradictionAnalyzer:
    """Core analysis engine comparing pairs of scientific findings under scientific integrity rules."""

    def __init__(self, checker: DeterministicCompatibilityChecker | None = None) -> None:
        self.checker = checker or DeterministicCompatibilityChecker()

    def compare_extractions(
        self,
        ext1: ScientificPaperExtraction,
        ext2: ScientificPaperExtraction,
    ) -> ClaimRelationship:
        """Analyze relationship between two extracted research papers."""
        compat = self.checker.evaluate(ext1, ext2)
        title1 = ext1.paper_title or f"Document {ext1.document_id}"
        title2 = ext2.paper_title or f"Document {ext2.document_id}"
        paper_titles = [title1, title2]
        source_paper_ids = [ext1.document_id, ext2.document_id]

        # Gather relevant evidence passages from both papers
        combined_passages: list[SupportingPassage] = []
        for sp in ext1.supporting_passages + ext2.supporting_passages:
            if sp.field_supported in ("main_findings", "quantitative_results", "methodology", "sample_size"):
                combined_passages.append(sp)

        # Detect quantitative differences for shared metrics
        quant_diffs: list[QuantitativeDifference] = []
        shared_metrics = compat["shared_metrics"]
        for m_name in shared_metrics:
            q1_match = next((q for q in ext1.quantitative_results if _are_metrics_compatible(q.metric_name, m_name)), None)
            q2_match = next((q for q in ext2.quantitative_results if _are_metrics_compatible(q.metric_name, m_name)), None)
            if q1_match and q2_match:
                diff_desc = f"{title1} reported {q1_match.value}{q1_match.unit or ''} vs {title2} reported {q2_match.value}{q2_match.unit or ''} on {m_name}."
                sig_reported = compat["statistical_significance_reported"]
                sig_detail = (
                    "Statistical significance and variance metrics were reported in source text."
                    if sig_reported
                    else "Numerical difference is reported, but neither variance, standard error, nor p-values were provided to establish statistical significance."
                )
                quant_diffs.append(
                    QuantitativeDifference(
                        metric_name=m_name,
                        paper_1_value=q1_match.value,
                        paper_1_unit=q1_match.unit,
                        paper_2_value=q2_match.value,
                        paper_2_unit=q2_match.unit,
                        difference_summary=diff_desc,
                        statistical_significance_reported=sig_reported,
                        significance_details=sig_detail,
                    )
                )

        unresolved = list(compat["unresolved_information"])
        potential_explanations: list[str] = []

        # --- SCIENTIFIC RULE EVALUATION & CLASSIFICATION ---

        # RULE E: Missing essential methodological or dataset details
        p1_omits = not ext1.research_methodology or not ext1.dataset_or_material
        p2_omits = not ext2.research_methodology or not ext2.dataset_or_material
        if p1_omits or p2_omits or (compat["methodology_compatibility"] == "unknown" and compat["dataset_or_population_compatibility"] == "unknown"):
            label: ClaimRelationshipLabel = "unresolved"
            rationale = (
                f"Essential experimental methodology or dataset details were omitted in "
                f"{title1 if p1_omits else ''}{' and ' if p1_omits and p2_omits else ''}{title2 if p2_omits else ''}. "
                "The scientific integrity rules dictate that missing information must be treated as unknown; "
                "the available evidence is insufficient to determine whether the findings agree, diverge, or conflict."
            )
            return self._build_relationship(
                source_paper_ids, paper_titles, combined_passages, compat,
                quant_diffs, potential_explanations, label, rationale, unresolved
            )

        # RULE D: Incompatible evaluation metrics
        if compat["metric_compatibility"] == "incompatible":
            label = "incomparable"
            p1_m_str = ", ".join(ext1.evaluation_metrics) or "unspecified metrics"
            p2_m_str = ", ".join(ext2.evaluation_metrics) or "unspecified metrics"
            rationale = (
                f"Papers evaluate fundamentally incompatible metrics ({title1}: [{p1_m_str}] vs {title2}: [{p2_m_str}]). "
                "Scientific Rule 2 prohibits comparing different metrics as if they were equivalent. "
                "Differences in measurement dimensions prevent a direct empirical comparison."
            )
            potential_explanations.append("Different evaluation objectives and task criteria prevent numeric calibration.")
            return self._build_relationship(
                source_paper_ids, paper_titles, combined_passages, compat,
                quant_diffs, potential_explanations, label, rationale, unresolved
            )

        # RULE C: Different datasets or populations
        if compat["dataset_or_population_compatibility"] == "incompatible":
            label = "conditional_difference"
            p1_d_str = ", ".join(ext1.dataset_or_material)
            p2_d_str = ", ".join(ext2.dataset_or_material)
            rationale = (
                f"Models/interventions were evaluated on different datasets or study populations "
                f"({title1}: [{p1_d_str}] vs {title2}: [{p2_d_str}]). "
                "Scientific Rule 1 & Rule 3 dictate that differing numerical results on different datasets "
                "do not constitute a contradiction. The findings represent conditional differences under distinct data distributions."
            )
            potential_explanations.append(f"Benchmark divergence: differences in data domain, label distribution, or difficulty between {p1_d_str} and {p2_d_str}.")
            if ext1.sample_size or ext2.sample_size:
                potential_explanations.append(f"Sample size divergence: {title1} ({ext1.sample_size or 'unreported'}) vs {title2} ({ext2.sample_size or 'unreported'}).")
            return self._build_relationship(
                source_paper_ids, paper_titles, combined_passages, compat,
                quant_diffs, potential_explanations, label, rationale, unresolved
            )

        # RULE G & RULE B: Comparable conditions (metrics compatible, datasets compatible/comparable)
        # Check text claim directional polarity
        claims1_text = " ".join(c.author_claim for c in ext1.main_findings)
        claims2_text = " ".join(c.author_claim for c in ext2.main_findings)

        p1_pos = bool(_OPPOSING_POSITIVE_RE.search(claims1_text))
        p1_neg = bool(_OPPOSING_NEGATIVE_RE.search(claims1_text))
        p2_pos = bool(_OPPOSING_POSITIVE_RE.search(claims2_text))
        p2_neg = bool(_OPPOSING_NEGATIVE_RE.search(claims2_text))

        # Check for opposing outcomes under comparable conditions (Scenario B)
        has_opposing_claims = (p1_pos and p2_neg) or (p1_neg and p2_pos)

        if has_opposing_claims and compat["dataset_or_population_compatibility"] in ("compatible", "partially_compatible"):
            label = "potential_contradiction"
            rationale = (
                f"Under comparable experimental conditions on {compat['dataset_note']}, the papers report "
                f"apparently opposing qualitative outcomes. {title1} claims positive/beneficial effects, while "
                f"{title2} reports negative effects or performance degradation. This finding appears inconsistent "
                "and warrants closer methodological and empirical examination."
            )
            potential_explanations.append("Differences in implementation details, hyperparameters, or baseline tuning rigor.")
            return self._build_relationship(
                source_paper_ids, paper_titles, combined_passages, compat,
                quant_diffs, potential_explanations, label, rationale, unresolved
            )

        # Check for agreement under comparable conditions (Scenario A)
        if (p1_pos and p2_pos) or (not has_opposing_claims and compat["dataset_or_population_compatibility"] == "compatible" and compat["metric_compatibility"] == "compatible"):
            # Check Scenario G: Numerical difference without statistical significance
            if quant_diffs and not compat["statistical_significance_reported"]:
                label = "agreement"
                rationale = (
                    f"Both papers report compatible directional findings under comparable benchmark conditions ({compat['dataset_note']}). "
                    f"A numerical difference is observed in reported metrics ({quant_diffs[0].difference_summary}), "
                    "but neither paper reported variance, standard error, or p-values. "
                    "In accordance with Scientific Rule 6 & 7, statistical significance cannot be inferred, "
                    "and the findings are classified as consistent in directionality while preserving uncertainty."
                )
                unresolved.append("Statistical significance tests (p-values, standard errors, confidence intervals) were not reported.")
            else:
                label = "agreement"
                rationale = (
                    f"Papers report compatible findings and concordant conclusions under comparable conditions ({compat['dataset_note']}). "
                    f"Both studies observe consistent behavior on shared metric(s) [{', '.join(shared_metrics)}]."
                )
            return self._build_relationship(
                source_paper_ids, paper_titles, combined_passages, compat,
                quant_diffs, potential_explanations, label, rationale, unresolved
            )

        # Default fallback: Extension or Unresolved
        if ext1.model_architecture_or_intervention and ext2.model_architecture_or_intervention and ext1.model_architecture_or_intervention != ext2.model_architecture_or_intervention:
            label = "extension"
            rationale = (
                f"{title2} evaluates an extension or alternative intervention ({ext2.model_architecture_or_intervention}) "
                f"relative to {title1} ({ext1.model_architecture_or_intervention}) without establishing direct contradiction."
            )
        else:
            label = "unresolved"
            rationale = "Available extracted evidence is insufficient to definitively classify the relationship."

        return self._build_relationship(
            source_paper_ids, paper_titles, combined_passages, compat,
            quant_diffs, potential_explanations, label, rationale, unresolved
        )

    def _build_relationship(
        self,
        source_paper_ids: list[str],
        paper_titles: list[str],
        passages: list[SupportingPassage],
        compat: dict[str, Any],
        quant_diffs: list[QuantitativeDifference],
        potential_explanations: list[str],
        label: ClaimRelationshipLabel,
        rationale: str,
        unresolved: list[str],
    ) -> ClaimRelationship:
        digest_input = f"{':'.join(source_paper_ids)}:{label}:{rationale[:60]}"
        rel_id = f"rel_{hashlib.sha256(digest_input.encode('utf-8')).hexdigest()[:16]}"
        return ClaimRelationship(
            relationship_id=rel_id,
            claim_ids=[f"claim_{pid}" for pid in source_paper_ids],
            source_paper_ids=source_paper_ids,
            paper_titles=paper_titles,
            source_passages=passages,
            research_question_compatibility=compat["research_question_compatibility"],
            dataset_or_population_compatibility=compat["dataset_or_population_compatibility"],
            methodology_compatibility=compat["methodology_compatibility"],
            metric_compatibility=compat["metric_compatibility"],
            quantitative_differences=quant_diffs,
            potential_explanations=potential_explanations,
            relationship_label=label,
            supporting_rationale=rationale,
            unresolved_information=unresolved,
            verification_status="unverified",
        )


def verify_claim_relationship_evidence(
    relationship: ClaimRelationship,
    documents_map: dict[str, ExtractedDocument],
) -> ClaimRelationship:
    """Verify that every cited quote in the relationship exists verbatim in the source documents.

    Scientific Rule 10 & 11:
    - Every proposed contradiction must link to genuine claims and source passages.
    - If a relationship (particularly a potential_contradiction) lacks verified evidence,
      it CANNOT be maintained as a verified contradiction and is marked unverified / downgraded to unresolved.
    """
    if not relationship.source_passages:
        # Scenario F: A generated relationship has no supporting evidence
        logger.warning("Relationship %s has no supporting passages.", relationship.relationship_id)
        return relationship.model_copy(
            update={
                "verification_status": "unverified",
                "relationship_label": "unresolved" if relationship.relationship_label == "potential_contradiction" else relationship.relationship_label,
                "supporting_rationale": relationship.supporting_rationale + " [EVIDENCE AUDIT FAILED: No source evidence passages were provided. Unsupported claims cannot be treated as verified evidence.]",
                "unresolved_information": relationship.unresolved_information + ["Missing verifiable supporting passages from original document."],
            }
        )

    all_verified = True
    unverified_quotes: list[str] = []

    for sp in relationship.source_passages:
        doc = documents_map.get(sp.document_id)
        if not doc:
            all_verified = False
            unverified_quotes.append(f"Document '{sp.document_id}' not found in storage.")
            continue

        page_map = {p.page_number: p.text for p in doc.pages}
        verified_match = verify_quote_in_pages(sp.quote, sp.page_number, page_map=page_map)
        if not verified_match:
            all_verified = False
            unverified_quotes.append(f"Quote \"{sp.quote[:50]}...\" was not found on page {sp.page_number} of doc '{sp.document_id}'.")

    if not all_verified:
        # Scientific Rule 10: Never store unsupported claims as verified evidence
        is_contradiction = relationship.relationship_label == "potential_contradiction"
        new_label = "unresolved" if is_contradiction else relationship.relationship_label
        note = (
            f" [EVIDENCE AUDIT FAILED: {len(unverified_quotes)} passage(s) failed verification. "
            f"Rule 10 prohibits asserting unverified contradictions; status marked unverified.]"
        )
        return relationship.model_copy(
            update={
                "verification_status": "unverified",
                "relationship_label": new_label,
                "supporting_rationale": relationship.supporting_rationale + note,
                "unresolved_information": relationship.unresolved_information + unverified_quotes,
            }
        )

    return relationship.model_copy(update={"verification_status": "verified"})
