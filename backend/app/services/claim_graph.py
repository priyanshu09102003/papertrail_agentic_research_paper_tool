"""Transform structured research paper extractions and scientific claim relationships
into an interactive claim-to-evidence graph suitable for canvas visualization.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.db.repository import PaperTrailRepository
from app.schemas import (
    ClaimGraphEdge,
    ClaimGraphEdgeType,
    ClaimGraphNode,
    ClaimGraphNodeType,
    ClaimRelationship,
    ProjectClaimGraphResponse,
    ScientificPaperExtraction,
    SupportingPassage,
)


def _slugify(text: str) -> str:
    """Normalize text into a clean deterministic slug."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
    return clean.strip("_")[:40] or "unknown"


def _truncate(text: str, max_chars: int = 60) -> str:
    """Truncate text with an ellipsis if it exceeds max_chars."""
    stripped = text.strip()
    return f"{stripped[:max_chars]}..." if len(stripped) > max_chars else stripped


class ClaimGraphService:
    """Service to transform stored project analyses into a claim-to-evidence graph."""

    def __init__(self, repository: PaperTrailRepository) -> None:
        self.repo = repository

    def build_claim_graph(self, project_id: str) -> ProjectClaimGraphResponse:
        """Construct the claim-to-evidence graph for a given research project."""
        if not self.repo.project_exists(project_id):
            return ProjectClaimGraphResponse(
                project_id=project_id,
                nodes=[],
                edges=[],
                available_papers=[],
                available_relationship_types=[],
                is_empty=True,
                message=f"Research project '{project_id}' does not exist.",
            )

        # 1. Retrieve all documents and scientific extractions for the project
        doc_metas = self.repo.list_project_documents(project_id) or []
        extractions: list[ScientificPaperExtraction] = []
        doc_filename_map: dict[str, str] = {}

        for meta in doc_metas:
            doc_filename_map[meta.document_id] = meta.filename
            ext = self.repo.get_scientific_extraction(meta.document_id)
            if ext:
                extractions.append(ext)

        # Also retrieve any analyzed paper extractions from the research analysis record if available
        analysis = self.repo.get_research_analysis(project_id)
        if not extractions and analysis and analysis.report and analysis.report.papers_reviewed:
            # Check if any extractions exist in SQLite for reviewed papers
            for meta in doc_metas:
                ext = self.repo.get_scientific_extraction(meta.document_id)
                if ext and ext not in extractions:
                    extractions.append(ext)

        # 2. Retrieve claim relationships (from DB or active report)
        stored_rels = self.repo.get_claim_relationships(project_id)
        if not stored_rels and analysis and analysis.report and analysis.report.claim_relationships:
            stored_rels = analysis.report.claim_relationships

        if not extractions:
            return ProjectClaimGraphResponse(
                project_id=project_id,
                nodes=[],
                edges=[],
                available_papers=[],
                available_relationship_types=[],
                is_empty=True,
                message="No analyzed research papers or structured extractions found for this project.",
            )

        nodes_dict: dict[str, ClaimGraphNode] = {}
        edges_dict: dict[str, ClaimGraphEdge] = {}
        available_papers: list[dict[str, str]] = []

        # Tracking for initial layout positioning
        y_paper = 60.0
        y_claim = 60.0
        y_evidence = 60.0
        y_context = 60.0

        paper_primary_claim_map: dict[str, str] = {}
        paper_all_claims_map: dict[str, list[str]] = {}

        # 3. Build Nodes & Edges from Extractions
        for ext in extractions:
            doc_id = ext.document_id
            paper_title = ext.paper_title or doc_filename_map.get(doc_id, f"Document {doc_id}")
            paper_node_id = f"paper_{doc_id}"

            # --- Paper Node ---
            if paper_node_id not in nodes_dict:
                nodes_dict[paper_node_id] = ClaimGraphNode(
                    id=paper_node_id,
                    type="paper",
                    label=_truncate(paper_title, 45),
                    title=paper_title,
                    document_id=doc_id,
                    paper_title=paper_title,
                    status=ext.extraction_status,
                    pdf_url=f"/api/documents/{doc_id}/file",
                    details={
                        "sample_size": ext.sample_size,
                        "research_question": ext.research_question,
                        "study_objective": ext.study_objective,
                        "model_architecture_or_intervention": ext.model_architecture_or_intervention,
                    },
                    position={"x": 50.0, "y": y_paper},
                )
                y_paper += 160.0
                available_papers.append({"id": paper_node_id, "title": paper_title})

            # --- Claim Nodes ---
            # Extract claims from main_findings (which contain explicit author_claim)
            raw_claims = ext.main_findings if ext.main_findings else []

            paper_all_claims_map[doc_id] = []

            for idx, claim_item in enumerate(raw_claims):
                claim_text = claim_item.author_claim if hasattr(claim_item, "author_claim") else str(claim_item)
                claim_text = claim_text.strip()
                if not claim_text:
                    continue
                claim_node_id = f"claim_{doc_id}_{idx}"
                paper_all_claims_map[doc_id].append(claim_node_id)
                if doc_id not in paper_primary_claim_map:
                    paper_primary_claim_map[doc_id] = claim_node_id

                if claim_node_id not in nodes_dict:
                    nodes_dict[claim_node_id] = ClaimGraphNode(
                        id=claim_node_id,
                        type="claim",
                        label=_truncate(claim_text, 50),
                        title=claim_text,
                        document_id=doc_id,
                        paper_title=paper_title,
                        status="extracted",
                        pdf_url=f"/api/documents/{doc_id}/file",
                        details={"claim_index": idx, "source_paper": paper_title},
                        position={"x": 380.0, "y": y_claim},
                    )
                    y_claim += 140.0

                # Edge: Paper -> reports -> Claim
                edge_p_to_c = f"edge_{paper_node_id}_reports_{claim_node_id}"
                if edge_p_to_c not in edges_dict:
                    edges_dict[edge_p_to_c] = ClaimGraphEdge(
                        id=edge_p_to_c,
                        source=paper_node_id,
                        target=claim_node_id,
                        label="reports",
                        relationship_type="reports",
                        is_contradiction=False,
                        rationale=f"Claim extracted from findings of '{paper_title}'.",
                    )

            # If no claims were extracted, create a synthetic fallback claim from research question or title
            if not paper_all_claims_map[doc_id]:
                fallback_text = ext.research_question or f"Core finding of {paper_title}"
                fallback_claim_id = f"claim_{doc_id}_0"
                paper_all_claims_map[doc_id].append(fallback_claim_id)
                paper_primary_claim_map[doc_id] = fallback_claim_id
                nodes_dict[fallback_claim_id] = ClaimGraphNode(
                    id=fallback_claim_id,
                    type="claim",
                    label=_truncate(fallback_text, 50),
                    title=fallback_text,
                    document_id=doc_id,
                    paper_title=paper_title,
                    status="extracted",
                    pdf_url=f"/api/documents/{doc_id}/file",
                    details={"fallback": True},
                    position={"x": 380.0, "y": y_claim},
                )
                y_claim += 140.0
                edge_p_to_c = f"edge_{paper_node_id}_reports_{fallback_claim_id}"
                edges_dict[edge_p_to_c] = ClaimGraphEdge(
                    id=edge_p_to_c,
                    source=paper_node_id,
                    target=fallback_claim_id,
                    label="reports",
                    relationship_type="reports",
                    is_contradiction=False,
                )

            # Primary claim for linking context
            primary_claim_id = paper_primary_claim_map[doc_id]

            # --- Evidence Passages ---
            for p_idx, sp in enumerate(ext.supporting_passages):
                quote_hash = hashlib.sha256(sp.quote.strip().encode("utf-8")).hexdigest()[:8]
                ev_node_id = f"evidence_{doc_id}_p{sp.page_number}_{quote_hash}"

                if ev_node_id not in nodes_dict:
                    nodes_dict[ev_node_id] = ClaimGraphNode(
                        id=ev_node_id,
                        type="evidence",
                        label=f"Page {sp.page_number} Passage",
                        title=sp.quote,
                        document_id=doc_id,
                        paper_title=paper_title,
                        page_number=sp.page_number,
                        quote=sp.quote,
                        field_supported=sp.field_supported,
                        status="verified",
                        pdf_url=f"/api/documents/{doc_id}/file#page={sp.page_number}",
                        details={"page": sp.page_number, "field": sp.field_supported},
                        position={"x": 720.0, "y": y_evidence},
                    )
                    y_evidence += 130.0

                # Edge: Claim -> supported_by -> Evidence
                edge_c_to_ev = f"edge_{primary_claim_id}_supported_by_{ev_node_id}"
                if edge_c_to_ev not in edges_dict:
                    edges_dict[edge_c_to_ev] = ClaimGraphEdge(
                        id=edge_c_to_ev,
                        source=primary_claim_id,
                        target=ev_node_id,
                        label="supported by",
                        relationship_type="supported_by",
                        is_contradiction=False,
                        rationale=f"Supported by verbatim passage on page {sp.page_number} of '{paper_title}'.",
                    )

            # --- Datasets ---
            for ds in ext.dataset_or_material:
                clean_ds = ds.strip()
                if not clean_ds:
                    continue
                ds_node_id = f"dataset_{_slugify(clean_ds)}"
                if ds_node_id not in nodes_dict:
                    nodes_dict[ds_node_id] = ClaimGraphNode(
                        id=ds_node_id,
                        type="dataset",
                        label=_truncate(clean_ds, 35),
                        title=clean_ds,
                        document_id=doc_id,
                        paper_title=paper_title,
                        position={"x": 1080.0, "y": y_context},
                    )
                    y_context += 110.0

                edge_c_to_ds = f"edge_{primary_claim_id}_uses_dataset_{ds_node_id}"
                if edge_c_to_ds not in edges_dict:
                    edges_dict[edge_c_to_ds] = ClaimGraphEdge(
                        id=edge_c_to_ds,
                        source=primary_claim_id,
                        target=ds_node_id,
                        label="uses dataset",
                        relationship_type="uses_dataset",
                        is_contradiction=False,
                    )

            # --- Methodology ---
            if ext.research_methodology and ext.research_methodology.strip():
                method_text = ext.research_methodology.strip()
                method_node_id = f"method_{_slugify(method_text[:30])}"
                if method_node_id not in nodes_dict:
                    nodes_dict[method_node_id] = ClaimGraphNode(
                        id=method_node_id,
                        type="method",
                        label=_truncate(method_text, 35),
                        title=method_text,
                        document_id=doc_id,
                        paper_title=paper_title,
                        position={"x": 1080.0, "y": y_context},
                    )
                    y_context += 110.0

                edge_c_to_m = f"edge_{primary_claim_id}_depends_on_{method_node_id}"
                if edge_c_to_m not in edges_dict:
                    edges_dict[edge_c_to_m] = ClaimGraphEdge(
                        id=edge_c_to_m,
                        source=primary_claim_id,
                        target=method_node_id,
                        label="depends on",
                        relationship_type="depends_on",
                        is_contradiction=False,
                    )

            # --- Evaluation Metrics ---
            for metric in ext.evaluation_metrics:
                clean_m = metric.strip()
                if not clean_m:
                    continue
                metric_node_id = f"metric_{_slugify(clean_m)}"
                if metric_node_id not in nodes_dict:
                    nodes_dict[metric_node_id] = ClaimGraphNode(
                        id=metric_node_id,
                        type="metric",
                        label=_truncate(clean_m, 35),
                        title=clean_m,
                        document_id=doc_id,
                        paper_title=paper_title,
                        position={"x": 1080.0, "y": y_context},
                    )
                    y_context += 110.0

                edge_c_to_metric = f"edge_{primary_claim_id}_evaluated_using_{metric_node_id}"
                if edge_c_to_metric not in edges_dict:
                    edges_dict[edge_c_to_metric] = ClaimGraphEdge(
                        id=edge_c_to_metric,
                        source=primary_claim_id,
                        target=metric_node_id,
                        label="evaluated using",
                        relationship_type="evaluated_using",
                        is_contradiction=False,
                    )

        # 4. Integrate Stored Cross-Paper Claim Relationships
        label_display_map = {
            "potential_contradiction": "potentially contradicts",
            "agreement": "agrees with",
            "conditional_difference": "conditional difference",
            "extension": "extension",
            "incomparable": "incomparable",
            "unresolved": "unresolved",
        }

        for rel in stored_rels:
            if len(rel.source_paper_ids) >= 2:
                p1_id, p2_id = rel.source_paper_ids[0], rel.source_paper_ids[1]
                c1_id = paper_primary_claim_map.get(p1_id)
                c2_id = paper_primary_claim_map.get(p2_id)

                if c1_id and c2_id and c1_id != c2_id:
                    rel_type: ClaimGraphEdgeType = rel.relationship_label  # type: ignore[assignment]
                    is_contra = (rel.relationship_label == "potential_contradiction")
                    edge_id = f"edge_rel_{rel.relationship_id}"

                    edges_dict[edge_id] = ClaimGraphEdge(
                        id=edge_id,
                        source=c1_id,
                        target=c2_id,
                        label=label_display_map.get(rel.relationship_label, rel.relationship_label),
                        relationship_type=rel_type,
                        is_contradiction=is_contra,
                        verification_status=rel.verification_status,
                        rationale=rel.supporting_rationale,
                        details={
                            "research_question_compatibility": rel.research_question_compatibility,
                            "dataset_or_population_compatibility": rel.dataset_or_population_compatibility,
                            "methodology_compatibility": rel.methodology_compatibility,
                            "metric_compatibility": rel.metric_compatibility,
                            "quantitative_differences": [q.model_dump() for q in rel.quantitative_differences],
                            "potential_explanations": rel.potential_explanations,
                            "unresolved_information": rel.unresolved_information,
                        },
                    )

        # 5. Extract distinct available relationship types for filtering
        rel_types = sorted(list({edge.relationship_type for edge in edges_dict.values()}))

        return ProjectClaimGraphResponse(
            project_id=project_id,
            nodes=list(nodes_dict.values()),
            edges=list(edges_dict.values()),
            available_papers=available_papers,
            available_relationship_types=rel_types,
            is_empty=len(nodes_dict) == 0,
            message="Claim-to-evidence graph generated successfully." if nodes_dict else "Graph is empty.",
        )
