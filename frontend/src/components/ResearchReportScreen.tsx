'use client';

import React, { useEffect, useState } from 'react';
import {
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  Copy,
  Check,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
} from 'lucide-react';
import { ResearchAnalysisRecord, ResearchReport } from '@/types/papertrail';
import { api } from '@/services/api';
import { ScreenId } from './Navbar';

interface ResearchReportScreenProps {
  projectId: string;
  projectName?: string;
  onNavigate: (screen: ScreenId) => void;
}

export function ResearchReportScreen({
  projectId,
  projectName,
  onNavigate,
}: ResearchReportScreenProps) {
  const [analysis, setAnalysis] = useState<ResearchAnalysisRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    api
      .getProjectAnalysis(projectId)
      .then(setAnalysis)
      .catch((err) => console.error('Failed to load report', err))
      .finally(() => setLoading(false));
  }, [projectId]);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center p-16 text-[#8b8f98] gap-2 text-xs">
        <RefreshCw className="w-5 h-5 animate-spin text-[#7170ff]" />
        Loading research synthesis report...
      </div>
    );
  }

  if (!report) {
    return (
      <div className="rounded-xl border border-dashed border-[#ffffff14] p-12 text-center space-y-3 bg-[#0f1011] max-w-xl mx-auto">
        <FileSpreadsheet className="w-8 h-8 text-[#8b8f98] mx-auto opacity-50" />
        <h3 className="text-sm font-semibold text-[#f7f8f8]">No Research Report Generated</h3>
        <p className="text-xs text-[#8b8f98]">
          Run the research analysis workflow in the Analysis Workspace to synthesize a comprehensive report.
        </p>
        <button
          onClick={() => onNavigate('analysis')}
          className="px-4 py-2 rounded-full bg-[#e5e5e6] text-[#08090a] text-xs font-semibold"
        >
          Go to Analysis Workspace
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fadeIn">
      {/* Header & Copy Button */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-[#ffffff14]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#7170ff] bg-[#7170ff]/10 px-2.5 py-0.5 rounded-full">
            Synthesized Research Report
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-[#f7f8f8] mt-2">
            {report.title}
          </h1>
          <p className="text-xs text-[#8b8f98] mt-1 font-mono">
            Project: {projectName || projectId} • Generated: {new Date(report.generated_at).toLocaleString()}
          </p>
        </div>

        <button
          onClick={handleCopyReport}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#ffffff14] hover:bg-[#ffffff0a] text-xs font-semibold text-[#f7f8f8] transition-all"
        >
          {copied ? <Check className="w-4 h-4 text-[#2ecc71]" /> : <Copy className="w-4 h-4" />}
          {copied ? 'Copied Markdown' : 'Copy Report'}
        </button>
      </div>

      {/* Scientific Integrity Label Requirement */}
      <div className="rounded-xl border border-[#ffffff14] bg-[#121314] p-4 flex items-start gap-3 text-xs text-[#8b8f98]">
        <ShieldAlert className="w-4 h-4 text-[#f5c542] shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <span className="font-semibold text-[#f7f8f8]">Scientific Integrity Scope Notice:</span>
          <p className="leading-relaxed">
            This document represents an automated exploratory literature synthesis across selected research papers. In compliance with scientific reporting guidelines, it does not claim to be a PRISMA-compliant systematic review.
          </p>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="portal-card rounded-2xl p-6 sm:p-7 space-y-3 shadow-xl">
        <h2 className="text-sm font-semibold text-[#f7f8f8]">Executive Summary</h2>
        <p className="text-xs text-[#c5c8ce] leading-relaxed whitespace-pre-line">
          {report.executive_summary}
        </p>
      </div>

      {/* Papers Reviewed */}
      <div className="portal-card rounded-2xl p-6 space-y-3">
        <h2 className="text-sm font-semibold text-[#f7f8f8]">
          Analyzed Papers ({report.paper_count || (report.papers_reviewed || []).length})
        </h2>
        <ul className="divide-y divide-[#ffffff0a] text-xs text-[#f7f8f8]">
          {(report.papers_reviewed || []).map((paperTitle, idx) => (
            <li key={idx} className="py-2.5 flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-[#ffffff0a] text-[#8b8f98] font-mono text-[10px] flex items-center justify-center shrink-0">
                {idx + 1}
              </span>
              <span className="font-medium">{paperTitle}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Key Cross-Paper Comparisons */}
      {(report.comparisons?.length ?? 0) > 0 && (
        <div className="portal-card rounded-2xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-[#f7f8f8]">Key Comparisons Across Papers</h2>
          <div className="space-y-3">
            {(report.comparisons || []).map((comp, idx) => (
              <div key={idx} className="p-4 rounded-lg bg-[#121314] border border-[#ffffff0a] space-y-2">
                <span className="text-xs font-semibold text-[#7170ff] uppercase tracking-wider">
                  {comp.dimension}
                </span>
                <p className="text-xs text-[#a1a5ad] leading-relaxed">{comp.summary}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conflicts & Divergent Findings */}
      {(report.conflicts?.length ?? 0) > 0 && (
        <div className="rounded-xl border border-[#ff5b5b]/30 bg-[#ff5b5b]/05 p-6 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-[#ff5b5b]">
            <AlertTriangle className="w-4 h-4" />
            Analyzed Conflicts & Potential Contradictions
          </div>
          <div className="space-y-3">
            {(report.conflicts || []).map((conflict, idx) => (
              <div
                key={idx}
                className="p-4 rounded-lg bg-[#0f1011] border border-[#ff5b5b]/20 space-y-2 text-xs"
              >
                <div className="font-semibold text-[#f7f8f8]">{conflict.aspect}</div>
                <p className="text-[#a1a5ad] leading-relaxed">{conflict.description}</p>
                {conflict.potential_reconciliation && (
                  <div className="p-3 rounded bg-[#121314] text-[11px] text-[#8b8f98]">
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
        <div className="portal-card rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#f7f8f8] flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[#2ecc71]" />
              Audited Evidence Passages
            </h2>
            <span className="text-[11px] font-mono text-[#2ecc71]">
              100% Verbatim Verified
            </span>
          </div>

          <div className="overflow-x-auto rounded-lg border border-[#ffffff0a]">
            <table className="w-full text-left text-xs text-[#8b8f98]">
              <thead className="bg-[#121314] text-[10px] uppercase text-[#f7f8f8]">
                <tr>
                  <th className="py-2.5 px-3">Document ID</th>
                  <th className="py-2.5 px-3">Page</th>
                  <th className="py-2.5 px-3">Verbatim Source Quote</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#ffffff0a]">
                {(report.verified_evidence || []).map((ev, idx) => (
                  <tr key={idx} className="hover:bg-[#ffffff06]">
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#f7f8f8]">
                      {ev.document_id}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-[#f7f8f8]">
                      Page {ev.page_number}
                    </td>
                    <td className="py-2.5 px-3 italic text-[#a1a5ad] max-w-md">
                      &ldquo;{ev.quote}&rdquo;
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-[10px] text-[#2ecc71] font-semibold bg-[#2ecc71]/10 px-2 py-0.5 rounded-full">
                        Verified
                      </span>
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
          <div className="portal-card rounded-2xl p-6 space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#f7f8f8]">
              Reported Limitations
            </h3>
            <ul className="list-disc list-inside space-y-1.5 text-xs text-[#a1a5ad]">
              {(report.limitations || []).map((lim, idx) => (
                <li key={idx}>{lim}</li>
              ))}
            </ul>
          </div>
        )}

        {(report.future_directions?.length ?? 0) > 0 && (
          <div className="portal-card rounded-2xl p-6 space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#f7f8f8]">
              Future Research Directions
            </h3>
            <ul className="list-disc list-inside space-y-1.5 text-xs text-[#a1a5ad]">
              {(report.future_directions || []).map((dir, idx) => (
                <li key={idx}>{dir}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
