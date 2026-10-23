"""Discrete LangGraph node implementations for the PaperTrail research analysis workflow."""

from datetime import datetime, timezone
import logging
from typing import Any

from app.db.repository import PaperTrailRepository
from app.schemas import (
    ClaimRelationship,
    ComparisonItem,
    ConflictItem,
    EvidenceVerificationItem,
    NodeExecutionRecord,
    QuantitativeResult,
    ResearchAnalysisRecord,
    ResearchReport,
    ScientificPaperExtraction,
    SupportingPassage,
)
from app.services.contradiction_engine import (
    ScientificContradictionAnalyzer,
    verify_claim_relationship_evidence,
)
from app.services.graph.state import NodeExecutionState, ResearchAnalysisState, utc_now_iso
from app.services.paper_extractor import ScientificPaperExtractor, verify_quote_in_pages

logger = logging.getLogger(__name__)


def _make_node_record(
    node_name: str,
    status: str,
    started_at: str,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> NodeExecutionState:
    """Helper to construct a typed node execution audit record."""
    return NodeExecutionState(
        node_name=node_name,
        status=status,  # type: ignore[typeddict-item]
        started_at=started_at,
        completed_at=utc_now_iso(),
        error=error,
        details=details or {},
    )


class ResearchWorkflowNodes:
    """Dependency-injected node execution suite for the PaperTrail research workflow."""

    def __init__(
        self,
        repository: PaperTrailRepository,
        extractor: ScientificPaperExtractor,
    ) -> None:
        self.repository = repository
        self.extractor = extractor

    # -------------------------------------------------------------------------
    # Node 1: Validate Research Project
    # -------------------------------------------------------------------------
    async def validate_project(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Validate that the requested project exists in the database."""
        started_at = utc_now_iso()
        project_id = state.get("project_id", "")
        if not project_id or not self.repository.project_exists(project_id):
            err_msg = f"Research project '{project_id}' was not found in the database."
            return {
                "status": "failed",
                "current_node": "validate_project",
                "error_message": err_msg,
                "node_history": [
                    _make_node_record("validate_project", "failed", started_at, error=err_msg)
                ],
            }

        project = self.repository.get_project(project_id)
        proj_name = project.name if project else None
        proj_desc = project.description if project else None

        return {
            "status": "in_progress",
            "current_node": "validate_project",
            "project_name": proj_name,
            "project_description": proj_desc,
            "node_history": [
                _make_node_record(
                    "validate_project",
                    "completed",
                    started_at,
                    details={"project_name": proj_name},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 2: Load Selected Papers
    # -------------------------------------------------------------------------
    async def load_selected_papers(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Load scholarly papers and document metadata associated with the project."""
        started_at = utc_now_iso()
        project_id = state["project_id"]
        project = self.repository.get_project(project_id)

        if not project or (not project.papers and not project.documents):
            err_msg = f"Project '{project_id}' has no associated scholarly papers or uploaded PDF documents."
            return {
                "status": "failed",
                "current_node": "load_selected_papers",
                "error_message": err_msg,
                "node_history": [
                    _make_node_record("load_selected_papers", "failed", started_at, error=err_msg)
                ],
            }

        paper_ids = [p.id for p in project.papers]
        doc_ids = [d.document_id for d in project.documents]

        return {
            "status": "in_progress",
            "current_node": "load_selected_papers",
            "paper_ids": paper_ids,
            "document_ids": doc_ids,
            "node_history": [
                _make_node_record(
                    "load_selected_papers",
                    "completed",
                    started_at,
                    details={"paper_count": len(paper_ids), "document_count": len(doc_ids)},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 3: Check Document Availability
    # -------------------------------------------------------------------------
    async def check_document_availability(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Check document storage and reuse existing completed extractions without duplicate model calls."""
        started_at = utc_now_iso()
        doc_ids = state.get("document_ids", [])
        if not doc_ids:
            err_msg = "No document full-text records are available to extract in this project."
            return {
                "status": "failed",
                "current_node": "check_document_availability",
                "error_message": err_msg,
                "node_history": [
                    _make_node_record("check_document_availability", "failed", started_at, error=err_msg)
                ],
            }

        extractions = dict(state.get("extractions", {}))
        cached_ids: list[str] = []
        pending_ids: list[str] = []

        for doc_id in doc_ids:
            existing = self.repository.get_scientific_extraction(doc_id)
            if existing and existing.extraction_status == "completed":
                extractions[doc_id] = existing.model_dump()
                cached_ids.append(doc_id)
            else:
                pending_ids.append(doc_id)

        return {
            "status": "in_progress",
            "current_node": "check_document_availability",
            "extractions": extractions,
            "cached_document_ids": cached_ids,
            "pending_document_ids": pending_ids,
            "node_history": [
                _make_node_record(
                    "check_document_availability",
                    "completed",
                    started_at,
                    details={"cached_count": len(cached_ids), "pending_count": len(pending_ids)},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 4: Extract Missing Paper Information
    # -------------------------------------------------------------------------
    async def extract_missing_information(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Run bounded structured scientific extraction on documents lacking completed results."""
        started_at = utc_now_iso()
        pending_ids = list(state.get("pending_document_ids", []))
        extractions = dict(state.get("extractions", {}))
        retry_counts = dict(state.get("retry_counts", {}))
        max_retries = state.get("max_retries_per_node", 2)

        retries_consumed = retry_counts.get("extract_missing_information", 0)

        if not pending_ids:
            # Everything was already cached
            return {
                "status": "in_progress",
                "current_node": "extract_missing_information",
                "extractions": extractions,
                "pending_document_ids": [],
                "node_history": [
                    _make_node_record(
                        "extract_missing_information",
                        "completed",
                        started_at,
                        details={"extracted_count": 0, "note": "All extractions were cached"},
                    )
                ],
            }

        failed_docs: list[str] = []
        for doc_id in pending_ids:
            doc = self.repository.get_document(doc_id)
            if not doc:
                failed_docs.append(doc_id)
                continue
            try:
                extraction = await self.extractor.extract_document(doc)
                if extraction.extraction_status == "failed":
                    failed_docs.append(doc_id)
                else:
                    self.repository.save_scientific_extraction(extraction)
                    extractions[doc_id] = extraction.model_dump()
            except Exception as exc:
                logger.warning("Extraction failed for doc=%s: %s", doc_id, str(exc))
                failed_docs.append(doc_id)

        if failed_docs:
            retry_counts["extract_missing_information"] = retries_consumed + 1
            if retry_counts["extract_missing_information"] > max_retries:
                err_msg = f"Extraction retry budget exhausted. Failed documents: {failed_docs}"
                return {
                    "status": "failed",
                    "current_node": "extract_missing_information",
                    "retry_counts": retry_counts,
                    "error_message": err_msg,
                    "pending_document_ids": failed_docs,
                    "node_history": [
                        _make_node_record(
                            "extract_missing_information",
                            "failed",
                            started_at,
                            error=err_msg,
                            details={"failed_docs": failed_docs, "retries": retry_counts["extract_missing_information"]},
                        )
                    ],
                }

            # Return state ready for conditional retry
            return {
                "status": "in_progress",
                "current_node": "extract_missing_information",
                "retry_counts": retry_counts,
                "extractions": extractions,
                "pending_document_ids": failed_docs,
                "node_history": [
                    _make_node_record(
                        "extract_missing_information",
                        "running",
                        started_at,
                        error=f"Partial failure on {failed_docs}, retrying (attempt {retry_counts['extract_missing_information']}/{max_retries})",
                    )
                ],
            }

        return {
            "status": "in_progress",
            "current_node": "extract_missing_information",
            "extractions": extractions,
            "pending_document_ids": [],
            "node_history": [
                _make_node_record(
                    "extract_missing_information",
                    "completed",
                    started_at,
                    details={"extracted_count": len(pending_ids)},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 5: Validate Extracted Results
    # -------------------------------------------------------------------------
    async def validate_extracted_results(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Validate extracted structures against scientific integrity rules."""
        started_at = utc_now_iso()
        extractions = state.get("extractions", {})
        retry_counts = dict(state.get("retry_counts", {}))
        max_retries = state.get("max_retries_per_node", 2)

        if not extractions:
            err_msg = "No extraction results are available to validate."
            return {
                "status": "failed",
                "current_node": "validate_extracted_results",
                "error_message": err_msg,
                "node_history": [
                    _make_node_record("validate_extracted_results", "failed", started_at, error=err_msg)
                ],
            }

        invalid_docs: list[str] = []
        for doc_id, ext_dict in extractions.items():
            try:
                extraction = ScientificPaperExtraction.model_validate(ext_dict)
                # Integrity check: must have at least title or methodology, and not marked failed
                if extraction.extraction_status == "failed":
                    invalid_docs.append(doc_id)
                elif not extraction.paper_title and not extraction.research_methodology:
                    invalid_docs.append(doc_id)
            except Exception:
                invalid_docs.append(doc_id)

        if invalid_docs:
            retries = retry_counts.get("validate_extracted_results", 0) + 1
            retry_counts["validate_extracted_results"] = retries
            if retries > max_retries:
                err_msg = f"Validation retry budget exhausted. Invalid extractions: {invalid_docs}"
                return {
                    "status": "failed",
                    "current_node": "validate_extracted_results",
                    "retry_counts": retry_counts,
                    "error_message": err_msg,
                    "node_history": [
                        _make_node_record(
                            "validate_extracted_results",
                            "failed",
                            started_at,
                            error=err_msg,
                            details={"invalid_docs": invalid_docs},
                        )
                    ],
                }

            # Route back to extraction for invalid documents
            return {
                "status": "in_progress",
                "current_node": "validate_extracted_results",
                "retry_counts": retry_counts,
                "pending_document_ids": invalid_docs,
                "node_history": [
                    _make_node_record(
                        "validate_extracted_results",
                        "running",
                        started_at,
                        error=f"Invalid extractions on {invalid_docs}, scheduling retry.",
                    )
                ],
            }

        return {
            "status": "in_progress",
            "current_node": "validate_extracted_results",
            "node_history": [
                _make_node_record(
                    "validate_extracted_results",
                    "completed",
                    started_at,
                    details={"validated_count": len(extractions)},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 6: Compare Paper Findings
    # -------------------------------------------------------------------------
    async def compare_paper_findings(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Aggregate methodologies, metrics, datasets, and quantitative results into cross-paper comparisons."""
        started_at = utc_now_iso()
        extractions = state.get("extractions", {})
        comparisons: list[dict[str, Any]] = []

        validated_exts = [
            ScientificPaperExtraction.model_validate(raw) for raw in extractions.values()
        ]
        all_titles = [e.paper_title or f"Document {e.document_id}" for e in validated_exts]

        # Methodology comparison
        method_entries = [
            f"{e.paper_title or e.document_id}: {e.research_methodology or 'Not reported'}"
            for e in validated_exts
        ]
        method_passages = [
            sp for e in validated_exts for sp in e.supporting_passages if sp.field_supported in ("methodology", "general")
        ]
        comparisons.append(
            ComparisonItem(
                dimension="Research Methodology",
                paper_titles=all_titles,
                summary="; ".join(method_entries),
                evidence_passages=method_passages[:5],
            ).model_dump()
        )

        # Datasets & Sample sizes
        data_entries = [
            f"{e.paper_title or e.document_id}: Datasets={', '.join(e.dataset_or_material) or 'None reported'} (Sample: {e.sample_size or 'Not reported'})"
            for e in validated_exts
        ]
        data_passages = [
            sp for e in validated_exts for sp in e.supporting_passages if sp.field_supported == "sample_size"
        ]
        comparisons.append(
            ComparisonItem(
                dimension="Datasets & Sample Sizes",
                paper_titles=all_titles,
                summary="; ".join(data_entries),
                evidence_passages=data_passages[:5],
            ).model_dump()
        )

        # Quantitative Results & Metrics
        metric_entries = []
        metric_passages = []
        for e in validated_exts:
            q_strs = [f"{q.metric_name}={q.value}{q.unit or ''}" for q in e.quantitative_results]
            metric_entries.append(
                f"{e.paper_title or e.document_id}: {', '.join(q_strs) or 'No quantitative metrics reported'}"
            )
            metric_passages.extend(
                [sp for sp in e.supporting_passages if sp.field_supported == "quantitative_results"]
            )

        comparisons.append(
            ComparisonItem(
                dimension="Quantitative Results & Evaluation Metrics",
                paper_titles=all_titles,
                summary="; ".join(metric_entries),
                evidence_passages=metric_passages[:5],
            ).model_dump()
        )

        return {
            "status": "in_progress",
            "current_node": "compare_paper_findings",
            "comparisons": comparisons,
            "node_history": [
                _make_node_record(
                    "compare_paper_findings",
                    "completed",
                    started_at,
                    details={"comparison_count": len(comparisons)},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 7: Analyze Potential Conflicts
    # -------------------------------------------------------------------------
    async def analyze_potential_conflicts(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Analyze potential conflicts, diverging outcomes, or contrasting limitations across papers."""
        started_at = utc_now_iso()
        extractions = state.get("extractions", {})
        conflicts: list[dict[str, Any]] = []

        validated_exts = [
            ScientificPaperExtraction.model_validate(raw) for raw in extractions.values()
        ]

        # Contrast architectures and baselines
        models_used = {
            e.paper_title or e.document_id: e.model_architecture_or_intervention
            for e in validated_exts
            if e.model_architecture_or_intervention
        }
        if len(models_used) >= 2 and len(set(models_used.values())) >= 2:
            arch_claims = [f"{title} adopted {arch}" for title, arch in models_used.items()]
            conflicts.append(
                ConflictItem(
                    aspect="Model Architecture Strategy",
                    description="Papers adopt contrasting modeling paradigms or interventions.",
                    author_claims=arch_claims,
                    potential_reconciliation="Different computational constraints, task modalities, or problem requirements.",
                    evidence_passages=[],
                ).model_dump()
            )

        # Contrast quantitative scores on shared metrics
        metrics_by_name: dict[str, list[tuple[str, str, str | None]]] = {}
        for e in validated_exts:
            title = e.paper_title or e.document_id
            for q in e.quantitative_results:
                m_key = q.metric_name.strip().lower()
                metrics_by_name.setdefault(m_key, []).append((title, q.value, q.unit))

        for m_name, results in metrics_by_name.items():
            if len(results) >= 2:
                values = {val for _, val, _ in results}
                if len(values) >= 2:
                    score_claims = [f"{t} achieved {v}{u or ''}" for t, v, u in results]
                    conflicts.append(
                        ConflictItem(
                            aspect=f"Diverging {m_name.upper()} Results",
                            description=f"Differing quantitative outcomes observed across papers on '{m_name}'.",
                            author_claims=score_claims,
                            potential_reconciliation="Variations in dataset scale, preprocessing, hyperparameter budgets, or benchmark test splits.",
                            evidence_passages=[],
                        ).model_dump()
                    )

        # Pairwise claim contradiction and scientific relationship analysis
        analyzer = ScientificContradictionAnalyzer()
        claim_relationships: list[dict[str, Any]] = []
        for i in range(len(validated_exts)):
            for j in range(i + 1, len(validated_exts)):
                rel = analyzer.compare_extractions(validated_exts[i], validated_exts[j])
                claim_relationships.append(rel.model_dump())
                if rel.relationship_label in ("potential_contradiction", "conditional_difference"):
                    conflicts.append(
                        ConflictItem(
                            aspect=f"{rel.relationship_label.replace('_', ' ').title()}: {rel.paper_titles[0]} vs {rel.paper_titles[1]}",
                            description=rel.supporting_rationale,
                            author_claims=[f"{rel.paper_titles[0]} finding", f"{rel.paper_titles[1]} finding"],
                            potential_reconciliation="; ".join(rel.potential_explanations) or None,
                            evidence_passages=rel.source_passages[:3],
                        ).model_dump()
                    )

        return {
            "status": "in_progress",
            "current_node": "analyze_potential_conflicts",
            "conflicts": conflicts,
            "claim_relationships": claim_relationships,
            "node_history": [
                _make_node_record(
                    "analyze_potential_conflicts",
                    "completed",
                    started_at,
                    details={"conflict_count": len(conflicts), "relationship_count": len(claim_relationships)},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 8: Verify Supporting Evidence
    # -------------------------------------------------------------------------
    async def verify_supporting_evidence(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Verify that all evidence quotes used in comparisons and findings link to genuine source document text."""
        started_at = utc_now_iso()
        extractions = state.get("extractions", {})
        retry_counts = dict(state.get("retry_counts", {}))
        max_retries = state.get("max_retries_per_node", 2)

        verified_evidence: list[dict[str, Any]] = []
        discrepancies: list[str] = []

        for doc_id, ext_dict in extractions.items():
            doc = self.repository.get_document(doc_id)
            page_map = {p.page_number: p.text for p in doc.pages} if doc else {}
            extraction = ScientificPaperExtraction.model_validate(ext_dict)

            for sp in extraction.supporting_passages:
                is_valid = verify_quote_in_pages(sp.quote, sp.page_number, page_map=page_map) is not None
                verified_evidence.append(
                    EvidenceVerificationItem(
                        document_id=doc_id,
                        page_number=sp.page_number,
                        quote=sp.quote,
                        verified=is_valid,
                    ).model_dump()
                )
                if not is_valid:
                    discrepancies.append(f"Passage quote on p.{sp.page_number} was not verbatim in doc '{doc_id}'")

        if discrepancies:
            retries = retry_counts.get("verify_supporting_evidence", 0) + 1
            retry_counts["verify_supporting_evidence"] = retries
            if retries > max_retries:
                err_msg = f"Evidence verification failed: {len(discrepancies)} quote(s) could not be verified in source document."
                return {
                    "status": "failed",
                    "current_node": "verify_supporting_evidence",
                    "retry_counts": retry_counts,
                    "error_message": err_msg,
                    "node_history": [
                        _make_node_record(
                            "verify_supporting_evidence",
                            "failed",
                            started_at,
                            error=err_msg,
                            details={"discrepancies": discrepancies},
                        )
                    ],
                }

            return {
                "status": "in_progress",
                "current_node": "verify_supporting_evidence",
                "retry_counts": retry_counts,
                "verified_evidence": verified_evidence,
                "node_history": [
                    _make_node_record(
                        "verify_supporting_evidence",
                        "running",
                        started_at,
                        error=f"Discrepancies found ({len(discrepancies)}), retrying comparison.",
                    )
                ],
            }

        # Audit claim relationships evidence
        raw_relationships = state.get("claim_relationships", [])
        verified_relationships: list[dict[str, Any]] = []
        doc_map = {doc_id: self.repository.get_document(doc_id) for doc_id in extractions.keys()}
        doc_map_clean = {k: v for k, v in doc_map.items() if v is not None}

        for raw_rel in raw_relationships:
            rel = ClaimRelationship.model_validate(raw_rel)
            v_rel = verify_claim_relationship_evidence(rel, doc_map_clean)
            verified_relationships.append(v_rel.model_dump())

        return {
            "status": "in_progress",
            "current_node": "verify_supporting_evidence",
            "verified_evidence": verified_evidence,
            "claim_relationships": verified_relationships,
            "node_history": [
                _make_node_record(
                    "verify_supporting_evidence",
                    "completed",
                    started_at,
                    details={"verified_passages": len(verified_evidence), "verified_relationships": len(verified_relationships)},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 9: Generate Research Report
    # -------------------------------------------------------------------------
    async def generate_report(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Synthesize the final structured ResearchReport."""
        started_at = utc_now_iso()
        project_id = state["project_id"]
        extractions = state.get("extractions", {})
        comparisons_raw = state.get("comparisons", [])
        conflicts_raw = state.get("conflicts", [])
        evidence_raw = state.get("verified_evidence", [])

        validated_exts = [
            ScientificPaperExtraction.model_validate(raw) for raw in extractions.values()
        ]
        paper_titles = [e.paper_title or f"Document {e.document_id}" for e in validated_exts]

        # Extract limitations and future directions across papers
        all_limitations = [lim for e in validated_exts for lim in e.authors_stated_limitations]
        all_future = [fw for e in validated_exts for fw in e.future_work]

        summary_parts = [
            f"Synthesized research analysis of {len(validated_exts)} paper(s): {', '.join(paper_titles)}."
        ]
        if comparisons_raw:
            summary_parts.append(f"Established {len(comparisons_raw)} cross-paper comparative dimensions.")
        if conflicts_raw:
            summary_parts.append(f"Identified {len(conflicts_raw)} potential methodological/empirical divergences.")

        report = ResearchReport(
            report_id=f"report_{project_id}",
            project_id=project_id,
            title=f"PaperTrail Synthesis Report: {state.get('project_name', project_id)}",
            executive_summary=" ".join(summary_parts),
            paper_count=len(validated_exts),
            papers_reviewed=paper_titles,
            comparisons=[ComparisonItem.model_validate(c) for c in comparisons_raw],
            conflicts=[ConflictItem.model_validate(c) for c in conflicts_raw],
            claim_relationships=[
                ClaimRelationship.model_validate(r)
                for r in state.get("claim_relationships", [])
            ],
            verified_evidence=[EvidenceVerificationItem.model_validate(e) for e in evidence_raw],
            limitations=list(dict.fromkeys(all_limitations)),
            future_directions=list(dict.fromkeys(all_future)),
            generated_at=utc_now_iso(),
        )

        return {
            "status": "in_progress",
            "current_node": "generate_report",
            "report": report.model_dump(),
            "node_history": [
                _make_node_record(
                    "generate_report",
                    "completed",
                    started_at,
                    details={"report_id": report.report_id, "paper_count": report.paper_count},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 10: Persist Results
    # -------------------------------------------------------------------------
    async def persist_results(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Save the completed analysis and node audit trail to SQLite."""
        started_at = utc_now_iso()
        project_id = state["project_id"]
        report_data = state.get("report")
        report = ResearchReport.model_validate(report_data) if report_data else None

        node_records = [
            NodeExecutionRecord.model_validate(item) for item in state.get("node_history", [])
        ]
        node_records.append(
            NodeExecutionRecord(
                node_name="persist_results",
                status="completed",
                started_at=started_at,
                completed_at=utc_now_iso(),
                details={"saved": True},
            )
        )

        record = ResearchAnalysisRecord(
            analysis_id=f"analysis_{project_id}",
            project_id=project_id,
            status="completed",
            current_node="persist_results",
            retry_counts=state.get("retry_counts", {}),
            node_history=node_records,
            report=report,
            error_message=None,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )

        saved = self.repository.save_research_analysis(record)

        # Persist structured claim relationships
        raw_relationships = state.get("claim_relationships", [])
        if raw_relationships:
            relationships_to_save = [
                ClaimRelationship.model_validate(r) for r in raw_relationships
            ]
            self.repository.save_claim_relationships(
                project_id=project_id,
                relationships=relationships_to_save,
                analysis_id=saved.analysis_id,
            )

        return {
            "status": "completed",
            "current_node": "persist_results",
            "node_history": [
                _make_node_record(
                    "persist_results",
                    "completed",
                    started_at,
                    details={"analysis_id": saved.analysis_id},
                )
            ],
        }

    # -------------------------------------------------------------------------
    # Node 11: Record Failure State
    # -------------------------------------------------------------------------
    async def record_failure(
        self, state: ResearchAnalysisState
    ) -> dict[str, Any]:
        """Persist controlled failure state and error information to SQLite."""
        started_at = utc_now_iso()
        project_id = state["project_id"]
        err_msg = state.get("error_message", "Unknown research workflow error.")
        failed_node = state.get("current_node", "unknown")

        node_records = [
            NodeExecutionRecord.model_validate(item) for item in state.get("node_history", [])
        ]
        node_records.append(
            NodeExecutionRecord(
                node_name="record_failure",
                status="completed",
                started_at=started_at,
                completed_at=utc_now_iso(),
                error=err_msg,
                details={"failed_at": failed_node},
            )
        )

        record = ResearchAnalysisRecord(
            analysis_id=f"analysis_{project_id}",
            project_id=project_id,
            status="failed",
            current_node=failed_node,
            retry_counts=state.get("retry_counts", {}),
            node_history=node_records,
            report=None,
            error_message=err_msg,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )

        saved = self.repository.save_research_analysis(record)

        # Persist structured claim relationships
        raw_relationships = state.get("claim_relationships", [])
        if raw_relationships:
            relationships_to_save = [
                ClaimRelationship.model_validate(r) for r in raw_relationships
            ]
            self.repository.save_claim_relationships(
                project_id=project_id,
                relationships=relationships_to_save,
                analysis_id=saved.analysis_id,
            )

        return {
            "status": "failed",
            "current_node": "record_failure",
            "error_message": err_msg,
            "node_history": [
                _make_node_record(
                    "record_failure",
                    "completed",
                    started_at,
                    details={"analysis_id": saved.analysis_id, "failed_node": failed_node},
                )
            ],
        }
