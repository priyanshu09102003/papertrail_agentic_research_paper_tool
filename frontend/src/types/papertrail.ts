export interface ProjectResponse {
  id: string;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  publication_year?: number | null;
  doi?: string | null;
  abstract?: string | null;
  source: 'openalex' | 'crossref' | 'manual' | 'local';
  landing_page_url?: string | null;
  open_access_pdf_url?: string | null;
}

export interface PaperSearchResponse {
  query: string;
  limit?: number;
  count?: number;
  total_results?: number;
  cached?: boolean;
  warnings?: string[];
  errors?: string[];
  source?: string;
  results?: Paper[];
  papers?: Paper[];
}

export interface DocumentMetadata {
  document_id: string;
  project_id?: string | null;
  paper_id?: string | null;
  filename: string;
  stored_path: string;
  file_size_bytes: number;
  page_count: number;
  total_characters: number;
  total_words: number;
  extraction_status: string;
  created_at: string;
}

export interface SupportingPassage {
  document_id: string;
  page_number: number;
  field_supported: string;
  quote: string;
}

export interface ExtractedClaim {
  author_claim: string;
  model_interpretation?: string | null;
}

export interface QuantitativeResult {
  metric_name: string;
  value: string;
  unit?: string | null;
  context?: string | null;
  supporting_quote: string;
  page_number: number;
}

export interface ScientificPaperExtraction {
  extraction_id: string;
  document_id: string;
  paper_title?: string | null;
  is_abstract_only: boolean;
  research_question?: string | null;
  study_objective?: string | null;
  research_methodology?: string | null;
  dataset_or_material: string[];
  sample_size?: string | null;
  model_architecture_or_intervention?: string | null;
  baselines: string[];
  evaluation_metrics: string[];
  main_findings: ExtractedClaim[];
  quantitative_results: QuantitativeResult[];
  authors_stated_limitations: string[];
  supporting_passages: SupportingPassage[];
  extraction_status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export type ClaimRelationshipLabel =
  | 'agreement'
  | 'potential_contradiction'
  | 'conditional_difference'
  | 'extension'
  | 'incomparable'
  | 'unresolved';

export interface QuantitativeDifference {
  metric_name: string;
  paper_1_value?: string | null;
  paper_1_unit?: string | null;
  paper_2_value?: string | null;
  paper_2_unit?: string | null;
  difference_summary: string;
  statistical_significance_reported: boolean;
  significance_details?: string | null;
}

export interface ClaimRelationship {
  relationship_id: string;
  claim_ids: string[];
  source_paper_ids: string[];
  paper_titles: string[];
  source_passages: SupportingPassage[];
  research_question_compatibility: string;
  dataset_or_population_compatibility: string;
  methodology_compatibility: string;
  metric_compatibility: string;
  quantitative_differences: QuantitativeDifference[];
  potential_explanations: string[];
  relationship_label: ClaimRelationshipLabel;
  supporting_rationale: string;
  unresolved_information: string[];
  verification_status: 'verified' | 'unverified';
  created_at?: string | null;
}

export interface NodeExecutionRecord {
  node_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  started_at: string;
  completed_at?: string | null;
  error?: string | null;
  details: Record<string, unknown>;
}

export interface ComparisonItem {
  dimension: string;
  paper_titles: string[];
  summary: string;
  evidence_passages: SupportingPassage[];
}

export interface ConflictItem {
  aspect: string;
  description: string;
  author_claims: string[];
  potential_reconciliation?: string | null;
  evidence_passages: SupportingPassage[];
}

export interface EvidenceVerificationItem {
  document_id: string;
  page_number: number;
  quote: string;
  verified: boolean;
}

export interface ResearchReport {
  report_id: string;
  project_id: string;
  title: string;
  executive_summary: string;
  paper_count: number;
  papers_reviewed: string[];
  comparisons: ComparisonItem[];
  conflicts: ConflictItem[];
  claim_relationships: ClaimRelationship[];
  verified_evidence: EvidenceVerificationItem[];
  limitations: string[];
  future_directions: string[];
  generated_at: string;
}

export interface ResearchAnalysisRecord {
  analysis_id: string;
  project_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  current_node?: string | null;
  retry_counts: Record<string, number>;
  node_history: NodeExecutionRecord[];
  report?: ResearchReport | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LLMStatusResponse {
  provider: string;
  model: string;
  service_reachable: boolean;
  model_available: boolean;
  status: 'ready' | 'model_missing' | 'unavailable';
  message: string;
}
