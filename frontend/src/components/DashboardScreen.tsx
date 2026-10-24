'use client';

import React, { useEffect, useState } from 'react';
import {
  FolderGit2,
  BookOpen,
  FileText,
  AlertTriangle,
  Clock,
  ArrowRight,
  PlusCircle,
  RefreshCw,
  GitGraph,
  Split,
  CheckCircle2,
  ExternalLink,
  Sparkles,
} from 'lucide-react';
import {
  ClaimRelationship,
  Paper,
  ProjectResponse,
  ResearchAnalysisRecord,
} from '@/types/papertrail';
import { api } from '@/services/api';
import { ScreenId } from './Navbar';
import { ProjectReportModal } from './ProjectReportModal';

interface DashboardScreenProps {
  onNavigate: (screen: ScreenId, projectId?: string) => void;
  selectedProjectId: string;
  onSelectProject: (id: string) => void;
}

export function DashboardScreen({
  onNavigate,
  selectedProjectId,
  onSelectProject,
}: DashboardScreenProps) {
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [recentPapers, setRecentPapers] = useState<Paper[]>([]);
  const [contradictions, setContradictions] = useState<ClaimRelationship[]>([]);
  const [activeAnalysis, setActiveAnalysis] = useState<ResearchAnalysisRecord | null>(null);

  // Overlay modal state for viewing project report
  const [inspectingProject, setInspectingProject] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const projList = await api.fetchProjects();
      setProjects(projList);

      const targetId = selectedProjectId || (projList.length > 0 ? projList[0].id : null);
      if (targetId) {
        // Load target project details
        const [papers, rels, analysis] = await Promise.allSettled([
          api.listProjectPapers(targetId),
          api.listProjectRelationships(targetId),
          api.getProjectAnalysis(targetId),
        ]);

        if (papers.status === 'fulfilled') setRecentPapers(papers.value);
        if (rels.status === 'fulfilled') {
          setContradictions(
            rels.value.filter((r) => r.relationship_label === 'potential_contradiction')
          );
        }
        if (analysis.status === 'fulfilled') setActiveAnalysis(analysis.value);
      }
    } catch (err) {
      console.error('Failed to load dashboard metrics', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, [selectedProjectId]);

  return (
    <div className="space-y-8 animate-fadeIn relative">
      {/* Project Report Modal Overlay */}
      {inspectingProject && (
        <ProjectReportModal
          projectId={inspectingProject.id}
          projectName={inspectingProject.name}
          onClose={() => setInspectingProject(null)}
          onNavigateToWorkspace={(projId) => {
            onSelectProject(projId);
            onNavigate('analysis', projId);
          }}
        />
      )}

      {/* Hero / Quick-start Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.12] bg-gradient-to-r from-[#0d0e11] via-[#101216] to-[#14161c] p-6 sm:p-8 shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
        {/* Subtle accent glow in top-right of banner */}
        <div className="absolute -top-24 -right-24 w-80 h-80 rounded-full bg-[#7170ff]/15 blur-3xl pointer-events-none" />
        <div className="absolute top-0 right-1/4 w-40 h-40 rounded-full bg-[#06b6d4]/10 blur-2xl pointer-events-none" />

        <div className="relative z-10 max-w-2xl space-y-3.5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#7170ff]/15 border border-[#7170ff]/30 text-[#9d9cfc] text-xs font-semibold shadow-inner">
            <GitGraph className="w-3.5 h-3.5" />
            <span>Empirical Scientific Integrity Platform</span>
            <Sparkles className="w-3 h-3 text-[#f5c542]" />
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#f7f8f8] leading-tight">
            Automated Cross-Paper Contradiction Analysis
          </h1>

          <p className="text-sm text-[#8b8f98] leading-relaxed">
            Extract source-grounded claims, audit page-level citations, and detect conflicting findings across scientific literature without assuming numeric variance is contradiction.
          </p>

          <div className="pt-2 flex flex-wrap items-center gap-3">
            <button
              onClick={() => onNavigate('new_research')}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-[#e5e5e6] hover:bg-white text-[#08090a] text-xs font-semibold transition-all shadow-[0_4px_14px_rgba(255,255,255,0.15)] hover:scale-[1.02] active:scale-[0.98]"
            >
              <PlusCircle className="w-4 h-4 text-[#7170ff]" />
              Start New Research Analysis
            </button>
            <button
              onClick={() => onNavigate('discovery')}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-white/[0.14] hover:bg-white/[0.06] text-[#f7f8f8] text-xs font-medium transition-all"
            >
              Search Scientific Papers
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1 */}
        <div className="portal-card rounded-xl p-5 space-y-2 border-t-2 border-t-[#7170ff]/60">
          <div className="flex items-center justify-between text-[#8b8f98]">
            <span className="text-xs font-semibold uppercase tracking-wider">Research Projects</span>
            <div className="p-1.5 rounded-lg bg-[#7170ff]/10 text-[#7170ff]">
              <FolderGit2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[#f7f8f8]">{projects.length}</div>
          <p className="text-[11px] text-[#8b8f98]">Persistent project workspaces in SQLite</p>
        </div>

        {/* Metric 2 */}
        <div className="portal-card rounded-xl p-5 space-y-2 border-t-2 border-t-[#2ecc71]/60">
          <div className="flex items-center justify-between text-[#8b8f98]">
            <span className="text-xs font-semibold uppercase tracking-wider">Papers Analyzed</span>
            <div className="p-1.5 rounded-lg bg-[#2ecc71]/10 text-[#2ecc71]">
              <BookOpen className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[#f7f8f8]">{recentPapers.length}</div>
          <p className="text-[11px] text-[#8b8f98]">Associated papers in active project</p>
        </div>

        {/* Metric 3 */}
        <div className="portal-card rounded-xl p-5 space-y-2 border-t-2 border-t-[#f5c542]/60">
          <div className="flex items-center justify-between text-[#8b8f98]">
            <span className="text-xs font-semibold uppercase tracking-wider">Analysis Status</span>
            <div className="p-1.5 rounded-lg bg-[#f5c542]/10 text-[#f5c542]">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[#f7f8f8] capitalize">
            {activeAnalysis?.status ?? 'Idle'}
          </div>
          <p className="text-[11px] text-[#8b8f98] font-mono">
            {activeAnalysis?.current_node ? `Node: ${activeAnalysis.current_node}` : 'No active pipeline run'}
          </p>
        </div>

        {/* Metric 4 */}
        <div className="portal-card rounded-xl p-5 space-y-2 border-t-2 border-t-[#ff5b5b]/60">
          <div className="flex items-center justify-between text-[#8b8f98]">
            <span className="text-xs font-semibold uppercase tracking-wider">Contradictions Found</span>
            <div className="p-1.5 rounded-lg bg-[#ff5b5b]/10 text-[#ff5b5b]">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-[#ff5b5b]">{contradictions.length}</div>
          <p className="text-[11px] text-[#8b8f98]">Evidence-audited tensions detected</p>
        </div>
      </div>

      {/* Main Two-Column Layout: Both cards have matching fixed height & internal transparent scrollbar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
        {/* Left Column: Recent Projects (Fixed Height + Internal Scroll) */}
        <div className="lg:col-span-2 portal-card rounded-2xl h-[520px] flex flex-col overflow-hidden">
          {/* Header (Shrink-0) */}
          <div className="p-5 sm:p-6 pb-4 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-[#0e0f12]/50">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-[#f7f8f8]">Recent Research Projects</h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.06] text-[#8b8f98]">
                  {projects.length} total
                </span>
              </div>
              <p className="text-xs text-[#8b8f98] mt-0.5">
                Click project title to view its synthesized report overlay
              </p>
            </div>
            <button
              onClick={() => onNavigate('new_research')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-white/[0.12] text-xs font-medium text-[#f7f8f8] hover:bg-white/[0.08] transition-all shrink-0"
            >
              <PlusCircle className="w-3.5 h-3.5 text-[#7170ff]" />
              New Project
            </button>
          </div>

          {/* Scrollable Project List Area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 custom-scrollbar space-y-2">
            {loading ? (
              <div className="flex flex-col items-center justify-center h-full text-[#8b8f98] gap-2 text-xs py-16">
                <RefreshCw className="w-5 h-5 animate-spin text-[#7170ff]" />
                Loading projects...
              </div>
            ) : projects.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full rounded-xl border border-dashed border-white/[0.1] p-8 text-center space-y-3">
                <FolderGit2 className="w-8 h-8 text-[#8b8f98] mx-auto opacity-50" />
                <p className="text-xs text-[#8b8f98]">No research projects found.</p>
                <button
                  onClick={() => onNavigate('new_research')}
                  className="px-4 py-2 rounded-full bg-[#e5e5e6] text-[#08090a] text-xs font-semibold"
                >
                  Create your first project
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {projects.map((proj) => {
                  const isSelected = proj.id === selectedProjectId;
                  return (
                    <div
                      key={proj.id}
                      className={`group flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                        isSelected
                          ? 'bg-[#7170ff]/10 border-[#7170ff]/40 shadow-[0_0_15px_rgba(113,112,255,0.1)]'
                          : 'bg-[#121316]/60 border-white/[0.06] hover:border-white/[0.16] hover:bg-[#16171c]'
                      }`}
                    >
                      <div className="space-y-1 min-w-0 pr-4 flex-1">
                        <div className="flex items-center gap-2">
                          {/* Clicking the TITLE opens the report overlay modal */}
                          <button
                            type="button"
                            onClick={() => {
                              onSelectProject(proj.id);
                              setInspectingProject({ id: proj.id, name: proj.name });
                            }}
                            className="text-xs font-medium text-[#f7f8f8] hover:text-[#9d9cfc] transition-colors truncate text-left font-semibold group-hover:underline flex items-center gap-1.5"
                            title="Click to view comprehensive project report"
                          >
                            <span>{proj.name}</span>
                            <ExternalLink className="w-3 h-3 text-[#7170ff] opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                          </button>

                          {isSelected && (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#7170ff]/25 text-[#9d9cfc] shrink-0">
                              Active
                            </span>
                          )}
                        </div>

                        <p className="text-[11px] text-[#8b8f98] font-mono">
                          ID: {proj.id} • {new Date(proj.created_at).toLocaleDateString()}
                        </p>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {/* Switch active project */}
                        <button
                          onClick={() => onSelectProject(proj.id)}
                          className={`px-2.5 py-1 text-[11px] rounded-lg font-medium transition-all ${
                            isSelected
                              ? 'text-[#9d9cfc] bg-[#7170ff]/20'
                              : 'text-[#8b8f98] hover:text-white hover:bg-white/[0.08]'
                          }`}
                          title="Set as active project"
                        >
                          {isSelected ? 'Active' : 'Select'}
                        </button>

                        {/* View Library */}
                        <button
                          onClick={() => {
                            onSelectProject(proj.id);
                            onNavigate('library', proj.id);
                          }}
                          className="p-1.5 text-xs text-[#8b8f98] hover:text-[#f7f8f8] hover:bg-white/[0.1] rounded-lg transition-colors"
                          title="View Paper Library"
                        >
                          <BookOpen className="w-4 h-4" />
                        </button>

                        {/* View Graph */}
                        <button
                          onClick={() => {
                            onSelectProject(proj.id);
                            onNavigate('graph', proj.id);
                          }}
                          className="p-1.5 text-xs text-[#8b8f98] hover:text-[#7170ff] hover:bg-white/[0.1] rounded-lg transition-colors"
                          title="View Claim-to-Evidence Graph"
                        >
                          <GitGraph className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Contradiction & Quick Audit Alerts (Fixed Matching Height) */}
        <div className="portal-card rounded-2xl h-[520px] flex flex-col overflow-hidden">
          {/* Header (Shrink-0) */}
          <div className="p-5 sm:p-6 pb-4 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-[#0e0f12]/50">
            <h2 className="text-sm font-semibold text-[#f7f8f8] flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-[#ff5b5b]" />
              Potential Contradictions
            </h2>
            <span className="text-[11px] font-mono text-[#8b8f98] px-2 py-0.5 rounded-full bg-white/[0.06]">
              {contradictions.length} flagged
            </span>
          </div>

          {/* Scrollable Contradictions List Area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 custom-scrollbar">
            {contradictions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full rounded-xl border border-dashed border-white/[0.08] p-6 text-center space-y-2 bg-[#121316]/40">
                <CheckCircle2 className="w-7 h-7 text-[#2ecc71] mx-auto opacity-80" />
                <p className="text-xs text-[#f7f8f8] font-medium">No active contradictions</p>
                <p className="text-[11px] text-[#8b8f98] max-w-xs leading-relaxed">
                  Run analysis on two or more papers to detect empirical discrepancies and scientific tensions.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {contradictions.map((rel) => (
                  <div
                    key={rel.relationship_id}
                    className="rounded-xl border border-[#ff5b5b]/30 bg-[#ff5b5b]/05 p-4 space-y-2.5 transition-all hover:border-[#ff5b5b]/50 hover:bg-[#ff5b5b]/10"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-[#ff5b5b]/20 text-[#ff5b5b]">
                        Conflict Detected
                      </span>
                      <span className="text-[10px] text-[#2ecc71] font-mono">
                        ✓ {rel.verification_status}
                      </span>
                    </div>

                    <p className="text-xs text-[#f7f8f8] font-medium leading-snug line-clamp-2">
                      {(rel.paper_titles || []).join(' vs. ') || 'Compared Papers'}
                    </p>

                    <p className="text-[11px] text-[#8b8f98] line-clamp-2 leading-relaxed">
                      {rel.supporting_rationale}
                    </p>

                    <button
                      onClick={() => onNavigate('comparison')}
                      className="text-[11px] text-[#9d9cfc] hover:underline inline-flex items-center gap-1 font-medium pt-1"
                    >
                      View in Comparison Explorer
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
