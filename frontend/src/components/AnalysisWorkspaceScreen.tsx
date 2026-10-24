'use client';

import React, { useEffect, useState } from 'react';
import {
  Cpu,
  RefreshCw,
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowRight,
  Split,
  GitGraph,
  FileSpreadsheet,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import { ResearchAnalysisRecord } from '@/types/papertrail';
import { api } from '@/services/api';
import { ScreenId } from './Navbar';

interface AnalysisWorkspaceScreenProps {
  projectId: string;
  projectName?: string;
  onNavigate: (screen: ScreenId) => void;
}

interface WorkflowStage {
  id: string;
  label: string;
  nodes: string[];
  description: string;
}

const WORKFLOW_STAGES: WorkflowStage[] = [
  {
    id: 'stage_discovery',
    label: 'Paper Discovery & Project Validation',
    nodes: ['validate_project', 'load_papers'],
    description: 'Validates research scope and loads selected scholarly papers.',
  },
  {
    id: 'stage_ingestion',
    label: 'PDF Document Ingestion',
    nodes: ['check_extraction_status'],
    description: 'Verifies binary structure, extracts page text, and checks existing caches.',
  },
  {
    id: 'stage_extraction',
    label: 'Scientific Methodology & Claim Extraction',
    nodes: ['extract_paper_info'],
    description: 'Extracts author claims, quantitative metrics, methods, and datasets.',
  },
  {
    id: 'stage_validation',
    label: 'Extraction Result Validation',
    nodes: ['validate_extractions'],
    description: 'Enforces schema validity and triggers bounded retries if extraction is partial.',
  },
  {
    id: 'stage_comparison',
    label: 'Cross-Paper Comparison & Contradiction Analysis',
    nodes: ['prepare_comparisons', 'analyze_potential_conflicts'],
    description: 'Evaluates empirical comparability and identifies opposing claims under like conditions.',
  },
  {
    id: 'stage_verification',
    label: 'Evidence Passage Verification',
    nodes: ['verify_evidence'],
    description: 'Audits cited quotes against ground-truth document pages to prevent hallucination.',
  },
  {
    id: 'stage_report',
    label: 'Report Synthesis & Persistence',
    nodes: ['generate_report', 'persist_results'],
    description: 'Synthesizes structured research report and persists claim relationships in SQLite.',
  },
];

export function AnalysisWorkspaceScreen({
  projectId,
  projectName,
  onNavigate,
}: AnalysisWorkspaceScreenProps) {
  const [analysis, setAnalysis] = useState<ResearchAnalysisRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Model provider selection
  const [provider, setProvider] = useState<'auto' | 'gemini' | 'ollama'>('auto');

  // Fetch analysis record from backend
  const fetchStatus = async () => {
    if (!projectId) return;
    try {
      const rec = await api.getProjectAnalysis(projectId);
      setAnalysis(rec);
    } catch (err: unknown) {
      console.error('Error fetching analysis status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    // Poll every 3 seconds if status is in_progress
    const interval = setInterval(() => {
      if (analysis?.status === 'in_progress') {
        fetchStatus();
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [projectId, analysis?.status]);

  const handleStartAnalysis = async () => {
    setTriggering(true);
    setError(null);
    try {
      const res = await api.startProjectAnalysis(projectId, provider);
      setAnalysis(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis.');
    } finally {
      setTriggering(false);
    }
  };

  // Determine stage status based strictly on backend node_history
  const getStageStatus = (
    stage: WorkflowStage
  ): 'completed' | 'in_progress' | 'failed' | 'pending' => {
    if (!analysis) return 'pending';
    if (analysis.status === 'failed') {
      const failedNodeInStage = analysis.node_history.find(
        (nh) => stage.nodes.includes(nh.node_name) && nh.status === 'failed'
      );
      if (failedNodeInStage) return 'failed';
    }

    const completedNodes = new Set(
      analysis.node_history.filter((nh) => nh.status === 'completed').map((nh) => nh.node_name)
    );

    const allCompleted = stage.nodes.every((n) => completedNodes.has(n));
    if (allCompleted) return 'completed';

    const runningNodes = new Set(
      analysis.node_history.filter((nh) => nh.status === 'running').map((nh) => nh.node_name)
    );
    if (
      stage.nodes.some(
        (n) => runningNodes.has(n) || (analysis.current_node && stage.nodes.includes(analysis.current_node))
      )
    ) {
      return 'in_progress';
    }

    // If subsequent stages are completed or active, mark prior completed
    const stageIdx = WORKFLOW_STAGES.findIndex((s) => s.id === stage.id);
    const anyFutureRunningOrCompleted = WORKFLOW_STAGES.slice(stageIdx + 1).some((s) =>
      s.nodes.some((n) => completedNodes.has(n) || runningNodes.has(n))
    );
    if (anyFutureRunningOrCompleted) return 'completed';

    return 'pending';
  };

  // Calculate real progress percentage
  const completedStagesCount = WORKFLOW_STAGES.filter(
    (st) => getStageStatus(st) === 'completed'
  ).length;
  const progressPercent = Math.round((completedStagesCount / WORKFLOW_STAGES.length) * 100);

  return (
    <div className="space-y-8 animate-fadeIn max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#f7f8f8]">
              LangGraph Research Analysis Workspace
            </h1>
            <span
              className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase tracking-wider ${
                analysis?.status === 'completed'
                  ? 'bg-[#2ecc71]/10 text-[#2ecc71]'
                  : analysis?.status === 'failed'
                  ? 'bg-[#ff5b5b]/10 text-[#ff5b5b]'
                  : analysis?.status === 'in_progress'
                  ? 'bg-[#7170ff]/10 text-[#7170ff]'
                  : 'bg-[#ffffff0a] text-[#8b8f98]'
              }`}
            >
              {analysis?.status ? analysis.status.replace(/_/g, ' ') : 'Not Started'}
            </span>
          </div>
          <p className="text-xs text-[#8b8f98] mt-0.5">
            Project: <span className="text-[#f7f8f8] font-medium">{projectName || projectId}</span>
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          {/* Provider Selector */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#0f1011] border border-[#ffffff14] text-xs">
            <span className="text-[#8b8f98]">Provider:</span>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as 'auto' | 'gemini' | 'ollama')}
              disabled={triggering || analysis?.status === 'in_progress'}
              className="bg-transparent text-[#f7f8f8] font-semibold focus:outline-none cursor-pointer"
            >
              <option value="auto" className="bg-[#0f1011] text-[#f7f8f8]">
                Auto (Gemini / Ollama)
              </option>
              <option value="gemini" className="bg-[#0f1011] text-[#f7f8f8]">
                Gemini API
              </option>
              <option value="ollama" className="bg-[#0f1011] text-[#f7f8f8]">
                Local Ollama
              </option>
            </select>
          </div>

          <button
            onClick={handleStartAnalysis}
            disabled={triggering || analysis?.status === 'in_progress'}
            className="inline-flex items-center gap-2 px-6 py-2 rounded-full bg-[#e5e5e6] hover:bg-[#f7f8f8] disabled:opacity-40 text-[#08090a] text-xs font-semibold shadow-md transition-all"
          >
            {triggering || analysis?.status === 'in_progress' ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-[#08090a]" />
                Analysis Running...
              </>
            ) : analysis?.status === 'completed' ? (
              <>
                <RefreshCw className="w-4 h-4 text-[#08090a]" />
                Re-run Analysis
              </>
            ) : (
              <>
                <Play className="w-4 h-4 text-[#08090a]" />
                Start Research Analysis
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2.5 p-3.5 rounded-lg bg-[#ff5b5b]/10 border border-[#ff5b5b]/30 text-[#ff5b5b] text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Real Progress Bar Card */}
      <div className="portal-card rounded-2xl p-6 space-y-4 shadow-2xl">
        <div className="flex items-center justify-between text-xs">
          <div className="space-y-0.5">
            <span className="font-semibold text-[#f7f8f8]">Workflow Execution Progress</span>
            <p className="text-[11px] text-[#8b8f98]">
              {completedStagesCount} of {WORKFLOW_STAGES.length} stages completed based on backend state
            </p>
          </div>
          <span className="font-mono text-sm font-bold text-[#7170ff]">{progressPercent}%</span>
        </div>

        {/* Progress Bar Container */}
        <div className="w-full h-2 rounded-full bg-[#121314] border border-[#ffffff0a] overflow-hidden">
          <div
            className={`h-full transition-all duration-500 rounded-full ${
              analysis?.status === 'failed'
                ? 'bg-[#ff5b5b]'
                : analysis?.status === 'completed'
                ? 'bg-[#2ecc71]'
                : 'bg-[#7170ff]'
            }`}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Workflow Execution Stages List */}
      <div className="portal-card rounded-2xl p-6 space-y-4 shadow-2xl">
        <h3 className="text-sm font-semibold text-[#f7f8f8]">Orchestration Stages</h3>

        <div className="divide-y divide-[#ffffff0a]">
          {WORKFLOW_STAGES.map((stage) => {
            const status = getStageStatus(stage);

            return (
              <div
                key={stage.id}
                className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 first:pt-1 last:pb-1"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[#f7f8f8]">{stage.label}</span>
                  </div>
                  <p className="text-[11px] text-[#8b8f98]">{stage.description}</p>
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  {status === 'completed' && (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-[#2ecc71]/10 text-[#2ecc71] border border-[#2ecc71]/20">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Completed
                    </span>
                  )}
                  {status === 'in_progress' && (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-[#7170ff]/10 text-[#7170ff] border border-[#7170ff]/20 animate-pulse">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      In Progress
                    </span>
                  )}
                  {status === 'failed' && (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-[#ff5b5b]/10 text-[#ff5b5b] border border-[#ff5b5b]/20">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Failed
                    </span>
                  )}
                  {status === 'pending' && (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium bg-[#ffffff0a] text-[#8b8f98]">
                      <Clock className="w-3.5 h-3.5" />
                      Pending
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Failure Diagnostics / Fallback with Probable Reason */}
      {analysis?.status === 'failed' && (
        <div className="rounded-xl border border-[#ff5b5b]/30 bg-[#ff5b5b]/05 p-6 space-y-3">
          <div className="flex items-center gap-2 text-[#ff5b5b] font-semibold text-sm">
            <AlertTriangle className="w-5 h-5" />
            Analysis Failed: Diagnostic Fallback
          </div>
          <p className="text-xs text-[#f7f8f8] leading-relaxed">
            {analysis.error_message ||
              'A workflow node failed and exhausted all recoverable retry attempts.'}
          </p>

          <div className="pt-2 border-t border-[#ffffff0a] space-y-1 text-[11px] text-[#8b8f98]">
            <span className="font-semibold text-[#f7f8f8]">Probable Root Causes:</span>
            <ul className="list-disc list-inside space-y-0.5">
              <li>Configured LLM service is offline or unreachable (check Ollama or GEMINI_API_KEY).</li>
              <li>Research PDF text extraction yielded empty pages or corrupted character encodings.</li>
              <li>Verification stage detected unverified claim passages that could not be audited against ground truth text.</li>
            </ul>
          </div>
        </div>
      )}

      {/* Success Navigation Banner */}
      {analysis?.status === 'completed' && (
        <div className="rounded-xl border border-[#2ecc71]/30 bg-[#2ecc71]/05 p-6 space-y-4">
          <div className="flex items-center gap-2 text-[#2ecc71] font-semibold text-sm">
            <CheckCircle2 className="w-5 h-5" />
            Research Analysis Completed Successfully!
          </div>
          <p className="text-xs text-[#8b8f98] leading-relaxed">
            All research stages succeeded. You can now explore the cross-paper comparison matrix, interact with the claim-to-evidence graph, or inspect the synthesized report.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={() => onNavigate('comparison')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#0f1011] border border-[#ffffff14] hover:bg-[#ffffff14] text-xs font-semibold text-[#f7f8f8] transition-all"
            >
              <Split className="w-3.5 h-3.5 text-[#7170ff]" />
              Comparison Explorer
            </button>
            <button
              onClick={() => onNavigate('graph')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#0f1011] border border-[#ffffff14] hover:bg-[#ffffff14] text-xs font-semibold text-[#f7f8f8] transition-all"
            >
              <GitGraph className="w-3.5 h-3.5 text-[#7170ff]" />
              Evidence Graph
            </button>
            <button
              onClick={() => onNavigate('report')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#e5e5e6] hover:bg-[#f7f8f8] text-[#08090a] text-xs font-semibold shadow-sm transition-all"
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              Research Report
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
