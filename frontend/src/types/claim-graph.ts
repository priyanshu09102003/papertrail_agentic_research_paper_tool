export type ClaimGraphNodeType = 'paper' | 'claim' | 'evidence' | 'dataset' | 'method' | 'metric';

export type ClaimGraphEdgeType =
  | 'reports'
  | 'supported_by'
  | 'agrees_with'
  | 'agreement'
  | 'potentially_contradicts'
  | 'potential_contradiction'
  | 'conditional_difference'
  | 'extension'
  | 'incomparable'
  | 'unresolved'
  | 'uses_dataset'
  | 'evaluated_using'
  | 'depends_on';

export interface ClaimGraphNodeData {
  id: string;
  type: ClaimGraphNodeType;
  label: string;
  title: string;
  document_id?: string | null;
  paper_title?: string | null;
  page_number?: number | null;
  quote?: string | null;
  field_supported?: string | null;
  status?: string | null;
  pdf_url?: string | null;
  details?: Record<string, unknown>;
  position?: { x: number; y: number };
}

export interface ClaimGraphEdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  relationship_type: ClaimGraphEdgeType;
  is_contradiction: boolean;
  verification_status?: 'verified' | 'unverified' | null;
  rationale?: string | null;
  details?: {
    research_question_compatibility?: string;
    dataset_or_population_compatibility?: string;
    methodology_compatibility?: string;
    metric_compatibility?: string;
    quantitative_differences?: Array<{
      metric_name: string;
      paper_1_value?: string;
      paper_2_value?: string;
      difference_summary?: string;
      statistical_significance_reported?: boolean;
      significance_details?: string;
    }>;
    potential_explanations?: string[];
    unresolved_information?: string[];
  };
}

export interface ProjectClaimGraphResponse {
  project_id: string;
  nodes: ClaimGraphNodeData[];
  edges: ClaimGraphEdgeData[];
  available_papers: Array<{ id: string; title: string }>;
  available_relationship_types: string[];
  is_empty: boolean;
  message?: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
}
