"""Pydantic schemas for API responses, error handling, scholarly discovery, PDF extraction, projects, LLM, and scientific extraction."""

from typing import Any, Literal

from pydantic import BaseModel, Field

PaperSource = Literal["openalex", "crossref"]
ExtractionStatus = Literal["completed", "failed"]
ScientificExtractionStatus = Literal["completed", "partial", "failed"]


class HealthResponse(BaseModel):
    """Schema for the health check endpoint response."""

    status: Literal["ok"] = Field(default="ok", description="Service health status.")
    application: str = Field(default="PaperTrail", description="Application name.")


class VersionResponse(BaseModel):
    """Schema for the application version endpoint response."""

    application: str = Field(default="PaperTrail", description="Application name.")
    version: str = Field(..., description="Semantic version of the backend application.")


class ErrorResponse(BaseModel):
    """Standardized schema for API error responses."""

    error: str = Field(..., description="Short error type or status phrase.")
    message: str = Field(..., description="Human-readable explanation of the error.")
    status_code: int = Field(..., description="HTTP status code.")
    details: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional validation error details when applicable.",
    )


class Paper(BaseModel):
    """Normalized scholarly paper representation across discovery providers."""

    id: str = Field(..., description="Internal deterministic identifier for the paper.")
    title: str = Field(..., min_length=1, description="Title of the scholarly work.")
    authors: list[str] = Field(
        default_factory=list,
        description="Ordered list of author display names.",
    )
    publication_year: int | None = Field(
        default=None,
        description="Year the work was published, if known.",
    )
    doi: str | None = Field(
        default=None,
        description="Normalized lowercase DOI (e.g., '10.1038/nature12373'), if available.",
    )
    abstract: str | None = Field(
        default=None,
        description="Plain-text abstract of the paper, if available.",
    )
    source: PaperSource = Field(
        ...,
        description="Upstream provider that supplied the primary record ('openalex' or 'crossref').",
    )
    landing_page_url: str | None = Field(
        default=None,
        description="URL of the paper's publisher or repository landing page.",
    )
    open_access_pdf_url: str | None = Field(
        default=None,
        description="Direct open-access PDF URL, only when explicitly provided and verified as a PDF link.",
    )


class PaperSearchResponse(BaseModel):
    """Structured response for GET /api/papers/search."""

    query: str = Field(..., description="Search query string.")
    limit: int = Field(..., description="Maximum number of deduplicated results requested.")
    count: int = Field(..., description="Number of papers returned in results.")
    cached: bool = Field(
        default=False,
        description="Whether this response was served from the local search cache.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings (e.g., if one upstream source was unavailable).",
    )
    results: list[Paper] = Field(
        default_factory=list,
        description="Normalized and deduplicated list of discovered scholarly papers.",
    )


class ExtractedPage(BaseModel):
    """Structured representation of text extracted from a single PDF page."""

    page_number: int = Field(..., ge=1, description="1-based page number in the PDF document.")
    text: str = Field(..., description="Extracted plain text content for this page.")
    character_count: int = Field(
        ..., ge=0, description="Number of non-whitespace characters extracted from this page."
    )
    word_count: int = Field(
        ..., ge=0, description="Number of words extracted from this page."
    )


class DocumentMetadata(BaseModel):
    """Persisted metadata and extraction status for an uploaded PDF document."""

    document_id: str = Field(
        ..., description="Stable internal identifier for the document."
    )
    project_id: str | None = Field(
        default=None, description="Optional research project ID this document belongs to."
    )
    paper_id: str | None = Field(
        default=None, description="Optional scholarly paper ID associated with this document."
    )
    filename: str = Field(
        ..., description="Sanitized safe filename of the uploaded PDF."
    )
    stored_path: str = Field(
        ..., description="Relative path inside the application-managed storage directory."
    )
    file_size_bytes: int = Field(
        ..., ge=1, description="Size of the uploaded PDF file in bytes."
    )
    page_count: int = Field(
        ..., ge=1, description="Total number of pages in the PDF document."
    )
    total_characters: int = Field(
        ..., ge=0, description="Total non-whitespace characters extracted across all pages."
    )
    total_words: int = Field(
        ..., ge=0, description="Total words extracted across all pages."
    )
    extraction_status: ExtractionStatus = Field(
        default="completed", description="Status of text extraction ('completed' or 'failed')."
    )
    created_at: str = Field(
        ..., description="ISO-8601 UTC timestamp when the document was ingested."
    )


class ExtractedDocument(BaseModel):
    """Structured document representation returned after safe PDF ingestion and text extraction."""

    document_id: str = Field(
        ..., description="Unique deterministic identifier for the extracted document."
    )
    project_id: str | None = Field(
        default=None, description="Optional research project ID this document belongs to."
    )
    paper_id: str | None = Field(
        default=None, description="Optional scholarly paper ID associated with this document."
    )
    filename: str = Field(
        ..., description="Sanitized safe filename of the uploaded PDF."
    )
    stored_path: str | None = Field(
        default=None, description="Relative path inside the application-managed storage directory."
    )
    file_size_bytes: int = Field(
        ..., ge=1, description="Size of the uploaded PDF file in bytes."
    )
    page_count: int = Field(
        ..., ge=1, description="Total number of pages in the PDF document."
    )
    total_characters: int = Field(
        ..., ge=0, description="Total non-whitespace characters extracted across all pages."
    )
    total_words: int = Field(
        ..., ge=0, description="Total words extracted across all pages."
    )
    extraction_status: ExtractionStatus = Field(
        default="completed", description="Status of text extraction ('completed' or 'failed')."
    )
    created_at: str | None = Field(
        default=None, description="ISO-8601 UTC timestamp when the document was persisted."
    )
    pages: list[ExtractedPage] = Field(
        default_factory=list,
        description="Ordered page-by-page extracted text.",
    )


class ProjectCreateRequest(BaseModel):
    """Request schema for creating a new research project."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="Name of the research project."
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Optional project description or research goal."
    )


class ProjectResponse(BaseModel):
    """Summary schema for a persisted research project."""

    id: str = Field(..., description="Stable internal project identifier.")
    name: str = Field(..., description="Project name.")
    description: str | None = Field(default=None, description="Optional project description.")
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp.")
    updated_at: str = Field(..., description="ISO-8601 UTC last-updated timestamp.")


class ProjectDetailResponse(ProjectResponse):
    """Detailed schema for a research project including associated papers and document metadata."""

    papers: list[Paper] = Field(
        default_factory=list,
        description="Scholarly papers associated with this project.",
    )
    documents: list[DocumentMetadata] = Field(
        default_factory=list,
        description="Uploaded PDF document metadata associated with this project.",
    )


class ProjectDeleteResponse(BaseModel):
    """Response returned when a research project is deleted."""

    deleted_project_id: str = Field(..., description="ID of the deleted research project.")
    removed_files_count: int = Field(
        ..., ge=0, description="Number of managed PDF files deleted from disk storage."
    )
    status: Literal["deleted"] = Field(default="deleted")


class LLMTextResponse(BaseModel):
    """Validated Pydantic schema for plain-text LLM generation outputs."""

    provider: str = Field(..., min_length=1, description="Identifier of the LLM provider (e.g., 'ollama').")
    model: str = Field(..., min_length=1, description="Model name used for generation (e.g., 'qwen2.5:1.5b').")
    text: str = Field(..., min_length=1, description="Non-empty generated text response.")


class LLMStatusResponse(BaseModel):
    """Validated Pydantic schema for checking local LLM provider and model readiness."""

    provider: str = Field(..., description="LLM provider name.")
    model: str = Field(..., description="Configured default model name.")
    service_reachable: bool = Field(..., description="Whether the local LLM service is reachable.")
    model_available: bool = Field(
        ..., description="Whether the configured model is installed and ready."
    )
    status: Literal["ready", "model_missing", "unavailable"] = Field(
        ..., description="High-level readiness status."
    )
    message: str = Field(..., description="Safe user-facing status description.")


# -----------------------------------------------------------------------------
# Structured Scientific-Paper Extraction Schemas
# -----------------------------------------------------------------------------


class SupportingPassage(BaseModel):
    """A verified verbatim passage from the source document supporting an extracted finding."""

    document_id: str = Field(..., description="Identifier of the source document.")
    page_number: int = Field(..., ge=1, description="Verified 1-based page number in the source document.")
    field_supported: str = Field(
        ..., description="Name of the extracted field or claim this passage supports."
    )
    quote: str = Field(
        ..., min_length=1, description="Exact verbatim passage verified in the source page text."
    )


class ExtractedClaim(BaseModel):
    """Separates the authors' explicit finding/claim from any model interpretation."""

    author_claim: str = Field(
        ..., min_length=1, description="What the paper's authors explicitly state."
    )
    model_interpretation: str | None = Field(
        default=None,
        description="Optional model note or contextual summary, kept distinct from the authors' claim.",
    )
    supporting_quote: str | None = Field(
        default=None,
        description="Verbatim quote from the source page supporting this claim, if verified.",
    )
    page_number: int | None = Field(
        default=None, ge=1, description="Verified 1-based page number where the quote appears."
    )
    verified_in_source: bool = Field(
        default=False,
        description="True only if supporting_quote was verified verbatim in the source page text.",
    )


class QuantitativeResult(BaseModel):
    """Preserves exact reported numeric values, units, and source evidence."""

    metric_name: str = Field(..., min_length=1, description="Reported metric or measurement name.")
    value: str = Field(
        ..., min_length=1, description="Exact numeric value as written in the paper (e.g., '94.2', '0.031')."
    )
    unit: str | None = Field(
        default=None, description="Exact unit as written (e.g., '%', 'ms', 'dB'), or None if unitless."
    )
    context: str | None = Field(
        default=None, description="Dataset, task, or condition associated with the numeric result."
    )
    supporting_quote: str = Field(
        ..., min_length=1, description="Exact verbatim quote from the source page containing the value."
    )
    page_number: int = Field(..., ge=1, description="Verified 1-based source page number.")


class ScientificPaperExtraction(BaseModel):
    """Validated structured scientific extraction for a processed research document."""

    extraction_id: str = Field(
        ..., description="Deterministic identifier for this extraction record (ext_<document_id>)."
    )
    document_id: str = Field(..., description="Identifier of the source ExtractedDocument.")
    paper_title: str | None = Field(
        default=None, description="Paper title if explicitly present in the document, else None."
    )
    is_abstract_only: bool = Field(
        default=False,
        description="True if the source text appears to be only an abstract rather than a full paper.",
    )
    research_question: str | None = Field(
        default=None, description="Core research question investigated, if explicitly stated."
    )
    study_objective: str | None = Field(
        default=None, description="Primary objective or goal of the study, if stated."
    )
    research_methodology: str | None = Field(
        default=None, description="Authors' reported research methodology or experimental design."
    )
    dataset_or_material: list[str] = Field(
        default_factory=list,
        description="Datasets, corpora, or experimental materials explicitly used.",
    )
    sample_size: str | None = Field(
        default=None,
        description="Reported sample size (e.g., 'N = 450 participants'), or None if not reported.",
    )
    model_architecture_or_intervention: str | None = Field(
        default=None,
        description="Model architecture, algorithm, or experimental intervention when relevant.",
    )
    baselines: list[str] = Field(
        default_factory=list,
        description="Baseline models or control conditions explicitly compared against.",
    )
    evaluation_metrics: list[str] = Field(
        default_factory=list,
        description="Evaluation metrics or statistical measures explicitly reported.",
    )
    main_findings: list[ExtractedClaim] = Field(
        default_factory=list,
        description="Main findings distinguishing authors' explicit claims from model interpretation.",
    )
    quantitative_results: list[QuantitativeResult] = Field(
        default_factory=list,
        description="Verified quantitative results preserving exact numeric values and units.",
    )
    authors_stated_limitations: list[str] = Field(
        default_factory=list,
        description="Limitations explicitly stated by the authors.",
    )
    future_work: list[str] = Field(
        default_factory=list,
        description="Future work directions explicitly reported by the authors.",
    )
    supporting_passages: list[SupportingPassage] = Field(
        default_factory=list,
        description="Verified verbatim source passages linked to document_id and page_number.",
    )
    page_numbers: list[int] = Field(
        default_factory=list,
        description="Sorted list of 1-based page numbers from which verified evidence was extracted.",
    )
    extraction_status: ScientificExtractionStatus = Field(
        ..., description="Overall extraction status ('completed', 'partial', or 'failed')."
    )
    chunk_count: int = Field(default=1, ge=1, description="Number of bounded text chunks processed.")
    failed_chunks: int = Field(default=0, ge=0, description="Number of chunks that failed extraction.")
    warnings: list[str] = Field(
        default_factory=list,
        description="Scientific integrity or chunk-level warnings.",
    )
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp.")
    updated_at: str = Field(..., description="ISO-8601 UTC last-updated timestamp.")


# -----------------------------------------------------------------------------
# Structured Scientific Comparison & Contradiction Schemas
# -----------------------------------------------------------------------------

ClaimRelationshipLabel = Literal[
    "agreement",
    "potential_contradiction",
    "conditional_difference",
    "extension",
    "incomparable",
    "unresolved",
]

CompatibilityLevel = Literal[
    "compatible",
    "partially_compatible",
    "incompatible",
    "unknown",
]

VerificationStatus = Literal[
    "verified",
    "unverified",
    "failed",
]


class QuantitativeDifference(BaseModel):
    """Preserves quantitative comparisons between two reported results."""

    metric_name: str = Field(..., description="Name of the metric evaluated.")
    paper_1_value: str = Field(..., description="Exact numeric value from paper 1.")
    paper_1_unit: str | None = Field(default=None, description="Unit from paper 1, if any.")
    paper_2_value: str = Field(..., description="Exact numeric value from paper 2.")
    paper_2_unit: str | None = Field(default=None, description="Unit from paper 2, if any.")
    difference_summary: str = Field(..., description="Explanation of the numeric difference.")
    statistical_significance_reported: bool = Field(
        default=False,
        description="Whether statistical significance (p-value, confidence interval, variance) was reported.",
    )
    significance_details: str | None = Field(
        default=None,
        description="Explicit detail on statistical significance or missing variance.",
    )


class ClaimRelationship(BaseModel):
    """Structured scientific comparison and potential contradiction between findings."""

    relationship_id: str = Field(..., description="Unique deterministic identifier for this relationship.")
    claim_ids: list[str] = Field(default_factory=list, description="Identifiers of claims being compared.")
    source_paper_ids: list[str] = Field(default_factory=list, description="Source paper or document IDs.")
    paper_titles: list[str] = Field(default_factory=list, description="Titles of the compared papers.")
    source_passages: list[SupportingPassage] = Field(
        default_factory=list, description="Source evidence passages supporting the compared claims."
    )

    # Deterministic Compatibility Checks (Compare like with like)
    research_question_compatibility: CompatibilityLevel = Field(
        default="unknown", description="Compatibility of the investigated research questions."
    )
    dataset_or_population_compatibility: CompatibilityLevel = Field(
        default="unknown", description="Compatibility of datasets, corpora, or study populations."
    )
    methodology_compatibility: CompatibilityLevel = Field(
        default="unknown", description="Compatibility of experimental setups, models, or interventions."
    )
    metric_compatibility: CompatibilityLevel = Field(
        default="unknown", description="Compatibility of evaluation metrics and measurement procedures."
    )

    # Detailed Analysis & Scientific Integrity
    quantitative_differences: list[QuantitativeDifference] = Field(
        default_factory=list, description="Specific quantitative differences, if metrics are comparable."
    )
    potential_explanations: list[str] = Field(
        default_factory=list, description="Possible explanations for divergence (e.g., sample size, pre-training)."
    )
    relationship_label: ClaimRelationshipLabel = Field(
        ..., description="Standardized classification of the relationship."
    )
    supporting_rationale: str = Field(
        ..., min_length=1, description="Explicit rationale explaining the scientific reasoning behind this classification."
    )
    unresolved_information: list[str] = Field(
        default_factory=list, description="Missing or unreported information preventing full reconciliation."
    )
    verification_status: VerificationStatus = Field(
        default="unverified", description="Evidence verification status evaluated against ground-truth document text."
    )
    created_at: str | None = Field(default=None, description="ISO-8601 UTC timestamp.")


# -----------------------------------------------------------------------------
# LangGraph Research Analysis Schemas
# -----------------------------------------------------------------------------

AnalysisExecutionStatus = Literal["pending", "in_progress", "completed", "failed"]
NodeStatus = Literal["pending", "running", "completed", "failed", "skipped"]


class NodeExecutionRecord(BaseModel):
    """Execution audit trail for an individual graph node."""

    node_name: str = Field(..., description="Name of the executed workflow node.")
    status: NodeStatus = Field(..., description="Execution status of this node.")
    started_at: str = Field(..., description="ISO-8601 UTC timestamp when node started.")
    completed_at: str | None = Field(default=None, description="ISO-8601 UTC completion timestamp.")
    error: str | None = Field(default=None, description="Error message if node failed.")
    details: dict[str, Any] = Field(default_factory=dict, description="Summary metadata.")


class ComparisonItem(BaseModel):
    """Structured cross-paper comparison on a specific dimension."""

    dimension: str = Field(..., description="Comparison dimension (e.g., 'methodology', 'dataset', 'metrics').")
    paper_titles: list[str] = Field(default_factory=list, description="Titles of compared papers.")
    summary: str = Field(..., description="Synthesized comparative summary across papers.")
    evidence_passages: list[SupportingPassage] = Field(default_factory=list, description="Linked source evidence.")


class ConflictItem(BaseModel):
    """Explicitly analyzed disagreement, divergent result, or methodological conflict."""

    aspect: str = Field(..., description="Aspect of disagreement (e.g., 'performance claim', 'sample size').")
    description: str = Field(..., description="Detailed description of the tension or conflict.")
    author_claims: list[str] = Field(default_factory=list, description="Explicit author claims from papers.")
    potential_reconciliation: str | None = Field(
        default=None,
        description="Possible explanation (e.g., different benchmark conditions), kept distinct from author claims.",
    )
    evidence_passages: list[SupportingPassage] = Field(default_factory=list, description="Verified supporting quotes.")


class EvidenceVerificationItem(BaseModel):
    """Audit verification for an evidence quote used in comparative synthesis."""

    document_id: str = Field(..., description="Document identifier.")
    page_number: int = Field(..., ge=1, description="Source page number.")
    quote: str = Field(..., min_length=1, description="Passage quote text.")
    verified: bool = Field(..., description="Whether verified verbatim in source document.")


class ResearchReport(BaseModel):
    """Final synthesized research report produced by the LangGraph workflow."""

    report_id: str = Field(..., description="Unique report identifier.")
    project_id: str = Field(..., description="Project identifier.")
    title: str = Field(..., description="Title of the research report.")
    executive_summary: str = Field(..., description="Executive summary of findings across papers.")
    paper_count: int = Field(..., ge=0, description="Total papers analyzed.")
    papers_reviewed: list[str] = Field(default_factory=list, description="List of paper titles reviewed.")
    comparisons: list[ComparisonItem] = Field(default_factory=list, description="Key comparisons across papers.")
    conflicts: list[ConflictItem] = Field(default_factory=list, description="Identified conflicts or divergences.")
    claim_relationships: list[ClaimRelationship] = Field(
        default_factory=list, description="Structured pairwise or grouped scientific claim relationships."
    )
    verified_evidence: list[EvidenceVerificationItem] = Field(default_factory=list, description="Verified evidence quotes.")
    limitations: list[str] = Field(default_factory=list, description="Stated limitations across papers.")
    future_directions: list[str] = Field(default_factory=list, description="Synthesized future work directions.")
    generated_at: str = Field(..., description="ISO-8601 UTC generation timestamp.")


class ResearchAnalysisRecord(BaseModel):
    """Persisted database record of a research analysis run."""

    analysis_id: str = Field(..., description="Deterministic analysis identifier (analysis_<project_id>).")
    project_id: str = Field(..., description="Project identifier.")
    status: AnalysisExecutionStatus = Field(..., description="Workflow execution status.")
    current_node: str | None = Field(default=None, description="Active or final workflow node.")
    retry_counts: dict[str, int] = Field(default_factory=dict, description="Retries consumed per node.")
    node_history: list[NodeExecutionRecord] = Field(default_factory=list, description="Node execution history.")
    report: ResearchReport | None = Field(default=None, description="Synthesized research report if completed.")
    error_message: str | None = Field(default=None, description="Error message if analysis failed.")
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp.")
    updated_at: str = Field(..., description="ISO-8601 UTC last-updated timestamp.")


class ResearchAnalysisStartResponse(BaseModel):
    """Response returned when a research analysis is triggered."""

    analysis_id: str = Field(..., description="Deterministic analysis identifier.")
    project_id: str = Field(..., description="Project identifier.")
    status: AnalysisExecutionStatus = Field(..., description="Current status of the analysis.")
    message: str = Field(..., description="Status summary.")
    is_async: bool = Field(default=True, description="Indicates whether workflow runs asynchronously.")


class GraphNodeInfo(BaseModel):
    """Metadata describing a workflow graph node."""

    name: str = Field(..., description="Node name.")
    description: str = Field(..., description="Node purpose in the research workflow.")


class GraphEdgeInfo(BaseModel):
    """Metadata describing an edge or conditional transition."""

    source: str = Field(..., description="Source node name.")
    target: str = Field(..., description="Target node name.")
    is_conditional: bool = Field(default=False, description="Whether transition is conditional.")
    condition_description: str | None = Field(default=None, description="Condition description.")


class GraphStructureResponse(BaseModel):
    """Inspected structure of the LangGraph research analysis workflow."""

    workflow_name: str = Field(default="PaperTrail Research Analysis Workflow")
    nodes: list[GraphNodeInfo] = Field(default_factory=list)
    edges: list[GraphEdgeInfo] = Field(default_factory=list)
    mermaid_diagram: str = Field(..., description="Mermaid diagram representation of the graph.")


# -----------------------------------------------------------------------------
# Claim-to-Evidence Interactive Graph Schemas
# -----------------------------------------------------------------------------

ClaimGraphNodeType = Literal["paper", "claim", "evidence", "dataset", "method", "metric"]
ClaimGraphEdgeType = Literal[
    "reports",
    "supported_by",
    "agrees_with",
    "agreement",
    "potentially_contradicts",
    "potential_contradiction",
    "conditional_difference",
    "extension",
    "incomparable",
    "unresolved",
    "uses_dataset",
    "evaluated_using",
    "depends_on",
]


class ClaimGraphNode(BaseModel):
    """A node in the interactive claim-to-evidence graph."""

    id: str = Field(..., description="Unique deterministic identifier for the node.")
    type: ClaimGraphNodeType = Field(..., description="Category of node in the claim-to-evidence graph.")
    label: str = Field(..., description="Short display label.")
    title: str = Field(..., description="Full text title or description.")
    document_id: str | None = Field(default=None, description="Source document identifier if applicable.")
    paper_title: str | None = Field(default=None, description="Title of the source research paper.")
    page_number: int | None = Field(default=None, description="Page number in the original PDF.")
    quote: str | None = Field(default=None, description="Verbatim quote from source document.")
    field_supported: str | None = Field(default=None, description="Section or finding field supported by evidence.")
    status: str | None = Field(default=None, description="Status (e.g. verified, unverified, completed).")
    pdf_url: str | None = Field(default=None, description="Direct download/view URL for the PDF if available.")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional contextual metadata.")
    position: dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0},
        description="Suggested 2D layout coordinates for initial canvas placement.",
    )


class ClaimGraphEdge(BaseModel):
    """A directed edge in the interactive claim-to-evidence graph."""

    id: str = Field(..., description="Unique deterministic identifier for the directed edge.")
    source: str = Field(..., description="Source node ID.")
    target: str = Field(..., description="Target node ID.")
    label: str = Field(..., description="Display label for the edge relationship.")
    relationship_type: ClaimGraphEdgeType = Field(..., description="Standardized relationship classification.")
    is_contradiction: bool = Field(default=False, description="True if edge represents a potential contradiction.")
    verification_status: VerificationStatus | None = Field(
        default=None, description="Verification status evaluated against source text."
    )
    rationale: str | None = Field(default=None, description="Scientific rationale or justification.")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional relationship parameters.")


class ProjectClaimGraphResponse(BaseModel):
    """Full claim-to-evidence graph response for a research project."""

    project_id: str = Field(..., description="Project identifier.")
    nodes: list[ClaimGraphNode] = Field(default_factory=list, description="Unique deduplicated graph nodes.")
    edges: list[ClaimGraphEdge] = Field(default_factory=list, description="Unique deduplicated directed edges.")
    available_papers: list[dict[str, str]] = Field(default_factory=list, description="List of paper id & titles for filtering.")
    available_relationship_types: list[str] = Field(default_factory=list, description="Distinct edge relationship types present.")
    is_empty: bool = Field(default=False, description="True if no analyzed papers or claims exist.")
    message: str | None = Field(default=None, description="Descriptive message when graph is empty or partial.")

