'use client';

import React, { useEffect, useState } from 'react';
import {
  Split,
  AlertTriangle,
  CheckCircle2,
  BookOpen,
  Layers,
  Database,
  BarChart2,
  RefreshCw,
  ExternalLink,
  Info,
  HelpCircle,
} from 'lucide-react';
import {
  ClaimRelationship,
  ResearchAnalysisRecord,
  ScientificPaperExtraction,
} from '@/types/papertrail';
import { api } from '@/services/api';
import { ScreenId } from './Navbar';

interface ComparisonExplorerScreenProps {
  projectId: string;
  projectName?: string;
  onNavigate: (screen: ScreenId) => void;
}

export function ComparisonExplorerScreen({
  projectId,
  projectName,
  onNavigate,
}: ComparisonExplorerScreenProps) {
  const [extractions, setExtractions] = useState<ScientificPaperExtraction[]>([]);
  const [relationships, setRelationships] = useState<ClaimRelationship[]>([]);
  const [analysis, setAnalysis] = useState<ResearchAnalysisRecord | null>(null);
  const [loading, setLoading] = useState(true);

  // Tab filter: all, contradictions, agreement, conditional
  const [relFilter, setRelFilter] = useState<string>('all');

  const loadData = async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [extList, relList, analysisRec] = await Promise.allSettled([
        api.listProjectExtractions(projectId),
        api.listProjectRelationships(projectId),
        api.getProjectAnalysis(projectId),
      ]);

      if (extList.status === 'fulfilled') setExtractions(extList.value);
      if (relList.status === 'fulfilled') setRelationships(relList.value);
      if (analysisRec.status === 'fulfilled') setAnalysis(analysisRec.value);
    } catch (err) {
      console.error('Failed to load comparisons', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [projectId]);

  const filteredRelationships = relationships.filter((r) => {
    if (relFilter === 'all') return true;
    return r.relationship_label === relFilter;
  });

  const contradictionsCount = relationships.filter(
    (r) => r.relationship_label === 'potential_contradiction'
  ).length;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#f7f8f8]">
              Cross-Paper Comparison Explorer
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#7170ff]/10 text-[#7170ff] font-semibold">
              {relationships.length} relationship(s) evaluated
            </span>
          </div>
          <p className="text-xs text-[#8b8f98] mt-0.5">
            Project: <span className="text-[#f7f8f8] font-medium">{projectName || projectId}</span>
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 p-1 rounded-full bg-[#0f1011] border border-[#ffffff14] text-xs">
          {[
            { id: 'all', label: `All (${relationships.length})` },
            { id: 'potential_contradiction', label: `Contradictions (${contradictionsCount})` },
            { id: 'agreement', label: 'Agreement' },
            { id: 'conditional_difference', label: 'Conditional Differences' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setRelFilter(tab.id)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                relFilter === tab.id
                  ? 'bg-[#7170ff] text-white shadow-sm'
                  : 'text-[#8b8f98] hover:text-[#f7f8f8]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12 text-[#8b8f98] gap-2 text-xs">
          <RefreshCw className="w-5 h-5 animate-spin text-[#7170ff]" />
          Loading comparison data...
        </div>
      ) : relationships.length === 0 && extractions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#ffffff14] p-12 text-center space-y-3 bg-[#0f1011]">
          <Split className="w-8 h-8 text-[#8b8f98] mx-auto opacity-50" />
          <h3 className="text-sm font-semibold text-[#f7f8f8]">No Comparisons Available</h3>
          <p className="text-xs text-[#8b8f98] max-w-sm mx-auto">
            You must analyze at least two papers to synthesize cross-paper comparisons and evaluate potential contradictions.
          </p>
          <button
            onClick={() => onNavigate('analysis')}
            className="px-4 py-2 rounded-full bg-[#e5e5e6] text-[#08090a] text-xs font-semibold"
          >
            Go to Analysis Workspace
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Section 1: Potential Contradictions & Claim Relationships */}
          <div className="space-y-4">
            <h2 className="text-sm font-semibold text-[#f7f8f8] flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-[#ff5b5b]" />
              Synthesized Claim Relationships
            </h2>

            <div className="grid grid-cols-1 gap-4">
              {filteredRelationships.map((rel) => {
                const isContra = rel.relationship_label === 'potential_contradiction';
                return (
                  <div
                    key={rel.relationship_id}
                    className={`portal-card rounded-2xl p-6 space-y-4 transition-all ${
                      isContra
                        ? '!border-[#ff5b5b]/50 bg-[#ff5b5b]/05 shadow-[0_0_25px_rgba(255,91,91,0.12)]'
                        : 'hover:border-white/[0.18]'
                    }`}
                  >
                    {/* Relationship Badge Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs uppercase font-bold tracking-wider px-3 py-1 rounded-full ${
                            isContra
                              ? 'bg-[#ff5b5b]/20 text-[#ff5b5b] border border-[#ff5b5b]/30'
                              : 'bg-[#7170ff]/20 text-[#7170ff] border border-[#7170ff]/30'
                          }`}
                        >
                          {rel.relationship_label.replace(/_/g, ' ')}
                        </span>
                        <span className="text-[11px] font-mono text-[#2ecc71]">
                          ✓ {rel.verification_status} against document text
                        </span>
                      </div>

                      <div className="text-[11px] font-mono text-[#8b8f98]">
                        ID: {rel.relationship_id}
                      </div>
                    </div>

                    {/* Compared Papers Titles */}
                    <div className="text-sm font-semibold text-[#f7f8f8] leading-snug">
                      {(rel.paper_titles || []).join('  ⚡ vs.  ')}
                    </div>

                    {/* Scientific Rationale */}
                    <div className="p-4 rounded-lg bg-[#121314] border border-[#ffffff0a] space-y-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#8b8f98]">
                        Scientific Reasoning & Evaluation
                      </span>
                      <p className="text-xs text-[#f7f8f8] leading-relaxed">
                        {rel.supporting_rationale}
                      </p>
                    </div>

                    {/* Compatibility Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
                      <div className="p-2.5 rounded-lg bg-[#121314] border border-[#ffffff0a]">
                        <span className="text-[#8b8f98] block text-[10px]">Research Question</span>
                        <span className="font-semibold text-[#f7f8f8] capitalize">
                          {rel.research_question_compatibility}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-[#121314] border border-[#ffffff0a]">
                        <span className="text-[#8b8f98] block text-[10px]">Dataset / Population</span>
                        <span className="font-semibold text-[#f7f8f8] capitalize">
                          {rel.dataset_or_population_compatibility}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-[#121314] border border-[#ffffff0a]">
                        <span className="text-[#8b8f98] block text-[10px]">Methodology</span>
                        <span className="font-semibold text-[#f7f8f8] capitalize">
                          {rel.methodology_compatibility}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-[#121314] border border-[#ffffff0a]">
                        <span className="text-[#8b8f98] block text-[10px]">Metric Compatibility</span>
                        <span className="font-semibold text-[#f7f8f8] capitalize">
                          {rel.metric_compatibility}
                        </span>
                      </div>
                    </div>

                    {/* Quantitative Differences (if any) */}
                    {rel.quantitative_differences && rel.quantitative_differences.length > 0 && (
                      <div className="space-y-2 pt-2 border-t border-[#ffffff0a]">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[#8b8f98]">
                          Quantitative Metric Comparison
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                          {rel.quantitative_differences.map((qd, idx) => (
                            <div
                              key={idx}
                              className="p-3 rounded-lg bg-[#121314] border border-[#ffffff0a] space-y-1"
                            >
                              <div className="font-semibold text-[#f7f8f8]">{qd.metric_name}</div>
                              <div className="text-[11px] text-[#8b8f98]">
                                {qd.difference_summary}
                              </div>
                              <div className="text-[10px] text-[#f5c542] italic">
                                {qd.significance_details}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Explanations & Unresolved Information */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-[#ffffff0a] text-xs">
                      {(rel.potential_explanations?.length ?? 0) > 0 && (
                        <div>
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[#8b8f98]">
                            Potential Explanations for Divergence
                          </span>
                          <ul className="mt-1 list-disc list-inside text-[11px] text-[#a1a5ad] space-y-1">
                            {rel.potential_explanations.map((exp, idx) => (
                              <li key={idx}>{exp}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {(rel.unresolved_information?.length ?? 0) > 0 && (
                        <div>
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[#8b8f98]">
                            Unresolved Information
                          </span>
                          <ul className="mt-1 list-disc list-inside text-[11px] text-[#a1a5ad] space-y-1">
                            {rel.unresolved_information.map((unr, idx) => (
                              <li key={idx}>{unr}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Section 2: Structured Methodology & Dataset Comparison Table */}
          {extractions.length > 0 && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-[#f7f8f8] flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#7170ff]" />
                Paper Extraction Comparison Matrix
              </h2>

              <div className="overflow-x-auto rounded-xl border border-[#ffffff14] bg-[#0f1011]">
                <table className="w-full text-left text-xs text-[#8b8f98]">
                  <thead className="bg-[#121314] text-[11px] uppercase tracking-wider text-[#f7f8f8] border-b border-[#ffffff14]">
                    <tr>
                      <th className="py-3 px-4 font-semibold">Paper Title</th>
                      <th className="py-3 px-4 font-semibold">Methodology</th>
                      <th className="py-3 px-4 font-semibold">Datasets</th>
                      <th className="py-3 px-4 font-semibold">Metrics</th>
                      <th className="py-3 px-4 font-semibold">Primary Finding</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#ffffff0a]">
                    {extractions.map((ext) => (
                      <tr key={ext.extraction_id} className="hover:bg-[#ffffff06] transition-colors">
                        <td className="py-3.5 px-4 font-medium text-[#f7f8f8] max-w-[220px]">
                          {ext.paper_title || ext.document_id}
                        </td>
                        <td className="py-3.5 px-4 max-w-[220px]">
                          {ext.research_methodology || 'N/A'}
                        </td>
                        <td className="py-3.5 px-4">
                          {(ext.dataset_or_material || []).join(', ') || 'N/A'}
                        </td>
                        <td className="py-3.5 px-4">
                          {(ext.evaluation_metrics || []).join(', ') || 'N/A'}
                        </td>
                        <td className="py-3.5 px-4 italic max-w-[240px]">
                          {(ext.main_findings?.length ?? 0) > 0
                            ? ext.main_findings[0].author_claim
                            : 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
