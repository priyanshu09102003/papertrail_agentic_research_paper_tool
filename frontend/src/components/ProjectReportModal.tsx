'use client';

import React, { useEffect, useState } from 'react';
import {
  X,
  Copy,
  Check,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  Cpu,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import { ResearchAnalysisRecord, ResearchReport } from '@/types/papertrail';
import { api } from '@/services/api';

interface ProjectReportModalProps {
  projectId: string;
  projectName?: string;
  onClose: () => void;
  onNavigateToWorkspace: (projectId: string) => void;
}

export function ProjectReportModal({
  projectId,
  projectName,
  onClose,
  onNavigateToWorkspace,
}: ProjectReportModalProps) {
  const [analysis, setAnalysis] = useState<ResearchAnalysisRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    api
      .getProjectAnalysis(projectId)
      .then((data) => setAnalysis(data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load report.'))
      .finally(() => setLoading(false));
  }, [projectId]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const report: ResearchReport | undefined = analysis?.report ?? undefined;

  const handleCopyReport = () => {
    if (!report) return;
    const text = `
# ${report.title}
Project: ${projectName || projectId}
Generated: ${report.generated_at}

## Executive Summary
${report.executive_summary}

## Papers Reviewed (${report.paper_count || (report.papers_reviewed || []).length})
${(report.papers_reviewed || []).map((p) => `- ${p}`).join('\n')}

## Key Comparisons
${(report.comparisons || []).map((c) => `### ${c.dimension}\n${c.summary}`).join('\n\n')}

## Conflicts & Divergences
${(report.conflicts || []).map((cf) => `### ${cf.aspect}\n${cf.description}\nReconciliation: ${cf.potential_reconciliation || 'N/A'}`).join('\n\n')}

## Limitations
${(report.limitations || []).map((l) => `- ${l}`).join('\n')}

## Future Directions
${(report.future_directions || []).map((f) => `- ${f}`).join('\n')}
    `.trim();

    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-md animate-fadeIn"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl border border-[#ffffff1c] bg-[#0c0d10] shadow-[0_16px_50px_rgba(0,0,0,0.85)] overflow-hidden animate-fadeIn"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#ffffff10] bg-[#101114]/90 shrink-0">
          <div className="flex items-center gap-3 min-w-0 pr-4">
            <div className="p-2 rounded-lg bg-[#7170ff]/10 border border-[#7170ff]/20 text-[#7170ff] shrink-0">
              <FileSpreadsheet className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-[#7170ff]/15 text-[#9d9cfc]">
                  Research Synthesis Report
                </span>
                <span className="text-xs font-mono text-[#8b8f98] truncate">
                  ID: {projectId}
                </span>
              </div>
              <h2 className="text-sm font-semibold text-[#f7f8f8] truncate mt-0.5">
                {projectName || projectId}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {report && (
              <button
                onClick={handleCopyReport}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#ffffff14] hover:bg-[#ffffff0a] text-xs font-medium text-[#f7f8f8] transition-all"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-[#2ecc71]" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            )}

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#8b8f98] hover:text-[#f7f8f8] hover:bg-[#ffffff14] transition-colors"
              title="Close modal (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body with internal sleek scrollbar */}
        <div className="flex-1 overflow-y-auto p-6 sm:p-8 custom-scrollbar space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-[#8b8f98] space-y-3">
              <RefreshCw className="w-6 h-6 animate-spin text-[#7170ff]" />
              <p className="text-xs">Loading project research synthesis...</p>
            </div>
          ) : !report ? (
            <div className="rounded-xl border border-dashed border-[#ffffff14] p-12 text-center space-y-4 bg-[#121316]">
              <FileSpreadsheet className="w-10 h-10 text-[#8b8f98] mx-auto opacity-50" />
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-[#f7f8f8]">No Synthesis Report Generated Yet</h3>
                <p className="text-xs text-[#8b8f98] max-w-md mx-auto leading-relaxed">
                  This project has not completed an end-to-end scientific analysis workflow yet. Launch the workspace to extract claims, detect contradictions, and synthesize findings.
                </p>
              </div>
              <div className="pt-2">
                <button
                  onClick={() => {
                    onClose();
                    onNavigateToWorkspace(projectId);
                  }}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[#7170ff] hover:bg-[#8584ff] text-white text-xs font-semibold shadow-md transition-all"
                >
                  <Cpu className="w-3.5 h-3.5" />
                  Launch Analysis Workspace for this Project →
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-6 animate-fadeIn">
              {/* Report Title & Metadata */}
              <div className="pb-3 border-b border-[#ffffff10]">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#f7f8f8]">
                  {report.title}
                </h1>
                <p className="text-xs text-[#8b8f98] mt-1 font-mono">
                  Synthesized on {new Date(report.generated_at).toLocaleString()} • {report.paper_count} Paper(s)
                </p>
              </div>

              {/* Scientific Integrity Scope Notice */}
              <div className="rounded-xl border border-[#ffffff14] bg-[#121316] p-4 flex items-start gap-3 text-xs text-[#8b8f98]">
                <ShieldAlert className="w-4 h-4 text-[#f5c542] shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <span className="font-semibold text-[#f7f8f8]">Scientific Reporting Disclaimer:</span>
                  <p className="leading-relaxed">
                    This automated exploratory literature synthesis audits source claims and evidence passages. In compliance with academic reporting standards, it does not claim to be a manual PRISMA-compliant systematic review.
                  </p>
                </div>
              </div>

              {/* Executive Summary */}
              <div className="portal-card rounded-xl p-5 space-y-2">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#7170ff]">Executive Summary</h2>
                <p className="text-xs text-[#c5c8ce] leading-relaxed whitespace-pre-line">
                  {report.executive_summary}
                </p>
              </div>

              {/* Papers Reviewed */}
              <div className="portal-card rounded-xl p-5 space-y-3">
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#8b8f98]">
                  Analyzed Papers ({report.paper_count || (report.papers_reviewed || []).length})
                </h2>
                <ul className="divide-y divide-[#ffffff0a] text-xs text-[#f7f8f8]">
                  {(report.papers_reviewed || []).map((paperTitle, idx) => (
                    <li key={idx} className="py-2 flex items-center gap-2">
                      <span className="w-4 h-4 rounded-full bg-[#ffffff0a] text-[#8b8f98] font-mono text-[10px] flex items-center justify-center shrink-0">
                        {idx + 1}
                      </span>
                      <span className="font-medium truncate">{paperTitle}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Key Cross-Paper Comparisons */}
              {(report.comparisons?.length ?? 0) > 0 && (
                <div className="portal-card rounded-xl p-5 space-y-3">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-[#8b8f98]">
                    Cross-Paper Comparisons
                  </h2>
                  <div className="space-y-2.5">
                    {(report.comparisons || []).map((comp, idx) => (
                      <div key={idx} className="p-3.5 rounded-lg bg-[#141519] border border-[#ffffff0a] space-y-1">
                        <span className="text-xs font-semibold text-[#7170ff]">{comp.dimension}</span>
                        <p className="text-xs text-[#a1a5ad] leading-relaxed">{comp.summary}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Conflicts & Divergent Findings */}
              {(report.conflicts?.length ?? 0) > 0 && (
                <div className="rounded-xl border border-[#ff5b5b]/30 bg-[#ff5b5b]/05 p-5 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#ff5b5b]">
                    <AlertTriangle className="w-4 h-4" />
                    Identified Discrepancies & Contradictions
                  </div>
                  <div className="space-y-2.5">
                    {(report.conflicts || []).map((conflict, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-lg bg-[#0e0f12] border border-[#ff5b5b]/20 space-y-1.5 text-xs"
                      >
                        <div className="font-semibold text-[#f7f8f8]">{conflict.aspect}</div>
                        <p className="text-[#a1a5ad] leading-relaxed">{conflict.description}</p>
                        {conflict.potential_reconciliation && (
                          <div className="p-2.5 rounded bg-[#131417] text-[11px] text-[#8b8f98]">
                            <span className="font-semibold text-[#f7f8f8]">Potential Reconciliation: </span>
                            {conflict.potential_reconciliation}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Verified Evidence Passages Table */}
              {(report.verified_evidence?.length ?? 0) > 0 && (
                <div className="portal-card rounded-xl p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xs font-bold uppercase tracking-wider text-[#8b8f98] flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#2ecc71]" />
                      Audited Ground-Truth Evidence Passages
                    </h2>
                    <span className="text-[10px] font-mono text-[#2ecc71]">100% Verbatim Verified</span>
                  </div>

                  <div className="overflow-x-auto rounded-lg border border-[#ffffff0a]">
                    <table className="w-full text-left text-xs text-[#8b8f98]">
                      <thead className="bg-[#141519] text-[10px] uppercase text-[#f7f8f8]">
                        <tr>
                          <th className="py-2 px-3">Document ID</th>
                          <th className="py-2 px-3">Page</th>
                          <th className="py-2 px-3">Verified Source Quote</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#ffffff0a]">
                        {(report.verified_evidence || []).map((ev, idx) => (
                          <tr key={idx} className="hover:bg-[#ffffff06]">
                            <td className="py-2.5 px-3 font-mono text-[11px] text-[#f7f8f8]">
                              {ev.document_id}
                            </td>
                            <td className="py-2.5 px-3 font-semibold text-[#f7f8f8]">
                              p. {ev.page_number}
                            </td>
                            <td className="py-2.5 px-3 italic text-[#a1a5ad]">
                              &ldquo;{ev.quote}&rdquo;
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Limitations & Future Directions */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {(report.limitations?.length ?? 0) > 0 && (
                  <div className="portal-card rounded-xl p-4 space-y-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[#8b8f98]">Limitations</h3>
                    <ul className="list-disc list-inside space-y-1 text-xs text-[#a1a5ad]">
                      {(report.limitations || []).map((lim, idx) => (
                        <li key={idx}>{lim}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {(report.future_directions?.length ?? 0) > 0 && (
                  <div className="portal-card rounded-xl p-4 space-y-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[#8b8f98]">Future Directions</h3>
                    <ul className="list-disc list-inside space-y-1 text-xs text-[#a1a5ad]">
                      {(report.future_directions || []).map((dir, idx) => (
                        <li key={idx}>{dir}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
