import {
  ClaimRelationship,
  DocumentMetadata,
  LLMStatusResponse,
  Paper,
  PaperSearchResponse,
  ProjectResponse,
  ResearchAnalysisRecord,
  ScientificPaperExtraction,
} from '@/types/papertrail';
import { ProjectClaimGraphResponse } from '@/types/claim-graph';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function handleResponse<T>(res: Response, fallbackErrMsg: string): Promise<T> {
  if (!res.ok) {
    let detail = fallbackErrMsg;
    try {
      const errData = await res.json();
      if (errData && typeof errData === 'object' && 'detail' in errData) {
        detail = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch {
      detail = `${fallbackErrMsg} (HTTP ${res.status})`;
    }
    throw new Error(detail);
  }
  if (res.status === 204) {
    return {} as T;
  }
  return res.json();
}

export const api = {
  // Projects
  async fetchProjects(): Promise<ProjectResponse[]> {
    try {
      const res = await fetch(`${API_BASE}/api/projects`);
      return await handleResponse<ProjectResponse[]>(res, 'Failed to fetch projects');
    } catch (err: unknown) {
      console.warn('Backend server not reachable at', API_BASE, err);
      return [];
    }
  },

  async createProject(name: string, description?: string): Promise<ProjectResponse> {
    const res = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), description: description?.trim() || null }),
    });
    return handleResponse<ProjectResponse>(res, 'Failed to create project');
  },

  async getProject(projectId: string): Promise<ProjectResponse> {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}`);
    return handleResponse<ProjectResponse>(res, `Failed to load project '${projectId}'`);
  },

  async deleteProject(projectId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}`, {
      method: 'DELETE',
    });
    return handleResponse<void>(res, 'Failed to delete project');
  },

  // Papers Discovery & Association
  async searchPapers(params: {
    query: string;
    source?: 'openalex' | 'crossref' | 'all';
    fromYear?: number | null;
    toYear?: number | null;
    limit?: number;
  }): Promise<PaperSearchResponse> {
    const url = new URL(`${API_BASE}/api/papers/search`);
    url.searchParams.set('q', params.query);
    url.searchParams.set('query', params.query);
    if (params.source && params.source !== 'all') url.searchParams.set('source', params.source);
    if (params.fromYear) url.searchParams.set('from_year', params.fromYear.toString());
    if (params.toYear) url.searchParams.set('to_year', params.toYear.toString());
    if (params.limit) url.searchParams.set('limit', params.limit.toString());

    const res = await fetch(url.toString());
    return handleResponse<PaperSearchResponse>(res, 'Paper search request failed');
  },

  async addPaperToProject(projectId: string, paper: Paper): Promise<Paper> {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/papers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(paper),
    });
    return handleResponse<Paper>(res, 'Failed to add paper to project');
  },

  async removePaperFromProject(projectId: string, paperId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/papers/${paperId}`, {
      method: 'DELETE',
    });
    return handleResponse<void>(res, 'Failed to remove paper from project');
  },

  async listProjectPapers(projectId: string): Promise<Paper[]> {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/papers`);
      return await handleResponse<Paper[]>(res, 'Failed to list project papers');
    } catch (err: unknown) {
      console.warn(`Failed to list papers for project ${projectId}:`, err);
      return [];
    }
  },

  // Documents & Storage
  async uploadProjectDocument(projectId: string, file: File): Promise<DocumentMetadata> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/documents`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<DocumentMetadata>(res, 'PDF upload failed');
  },

  async listProjectDocuments(projectId: string): Promise<DocumentMetadata[]> {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/documents`);
      return await handleResponse<DocumentMetadata[]>(res, 'Failed to list project documents');
    } catch (err: unknown) {
      console.warn(`Failed to list documents for project ${projectId}:`, err);
      return [];
    }
  },

  getDocumentFileUrl(documentId: string, pageNumber?: number | null): string {
    const base = `${API_BASE}/api/documents/${documentId}/file`;
    return pageNumber ? `${base}#page=${pageNumber}` : base;
  },

  // Extractions & Relationships
  async listProjectExtractions(projectId: string): Promise<ScientificPaperExtraction[]> {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/extractions`);
      return await handleResponse<ScientificPaperExtraction[]>(res, 'Failed to retrieve extractions');
    } catch (err: unknown) {
      console.warn(`Failed to retrieve extractions for project ${projectId}:`, err);
      return [];
    }
  },

  async listProjectRelationships(projectId: string): Promise<ClaimRelationship[]> {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/relationships`);
      return await handleResponse<ClaimRelationship[]>(res, 'Failed to retrieve claim relationships');
    } catch (err: unknown) {
      console.warn(`Failed to retrieve relationships for project ${projectId}:`, err);
      return [];
    }
  },

  // Research Analysis Orchestration
  async startProjectAnalysis(
    projectId: string,
    provider: 'auto' | 'gemini' | 'ollama' = 'auto'
  ): Promise<ResearchAnalysisRecord> {
    const url = new URL(`${API_BASE}/api/projects/${projectId}/analysis`);
    url.searchParams.set('provider', provider);
    const res = await fetch(url.toString(), {
      method: 'POST',
    });
    return handleResponse<ResearchAnalysisRecord>(res, 'Failed to start research analysis');
  },

  async getProjectAnalysis(projectId: string): Promise<ResearchAnalysisRecord | null> {
    try {
      const res = await fetch(`${API_BASE}/api/projects/${projectId}/analysis`);
      if (res.status === 404) {
        return null;
      }
      return await handleResponse<ResearchAnalysisRecord>(res, 'Failed to fetch analysis status');
    } catch (err: unknown) {
      console.warn(`Failed to fetch analysis for project ${projectId}:`, err);
      return null;
    }
  },

  // Interactive Graph
  async fetchClaimGraph(projectId: string): Promise<ProjectClaimGraphResponse> {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/claim-graph`);
    return handleResponse<ProjectClaimGraphResponse>(res, 'Failed to load claim graph');
  },

  // System & LLM Status
  async getLLMStatus(): Promise<LLMStatusResponse> {
    try {
      const res = await fetch(`${API_BASE}/api/llm/status`);
      return await handleResponse<LLMStatusResponse>(res, 'Failed to check LLM readiness');
    } catch {
      return {
        status: 'unavailable',
        provider: 'none',
        model: 'unreachable',
        service_reachable: false,
        model_available: false,
        message: 'Backend server starting up or not running on port 8000.',
      };
    }
  },
};
