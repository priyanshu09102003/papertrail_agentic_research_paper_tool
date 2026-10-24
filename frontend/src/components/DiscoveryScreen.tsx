'use client';

import React, { useEffect, useState } from 'react';
import {
  Search,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  Plus,
  RefreshCw,
  Upload,
  AlertCircle,
  ArrowRight,
  Filter,
  CheckSquare,
  Square,
  FileText,
} from 'lucide-react';
import { Paper } from '@/types/papertrail';
import { api } from '@/services/api';
import { ScreenId } from './Navbar';

interface DiscoveryScreenProps {
  projectId: string;
  projectName?: string;
  initialParams?: {
    query: string;
    fromYear?: number;
    toYear?: number;
    limit?: number;
  };
  onNavigate: (screen: ScreenId) => void;
}

export function DiscoveryScreen({
  projectId,
  projectName,
  initialParams,
  onNavigate,
}: DiscoveryScreenProps) {
  const currentYear = new Date().getFullYear();

  const [query, setQuery] = useState(initialParams?.query || '');
  const [fromYear, setFromYear] = useState<number | undefined>(initialParams?.fromYear || 2018);
  const [toYear, setToYear] = useState<number | undefined>(initialParams?.toYear || currentYear);
  const [limit, setLimit] = useState<number>(initialParams?.limit || 10);
  const [source, setSource] = useState<'openalex' | 'crossref' | 'all'>('openalex');

  const [loading, setLoading] = useState(false);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selectedPaperMap, setSelectedPaperMap] = useState<Record<string, boolean>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Upload state
  const [uploading, setUploading] = useState(false);

  // Expanded abstract IDs
  const [expandedAbstracts, setExpandedAbstracts] = useState<Record<string, boolean>>({});

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const resp = await api.searchPapers({
        query: query.trim(),
        source,
        fromYear,
        toYear,
        limit,
      });
      const paperList: Paper[] = resp.results || resp.papers || [];
      setPapers(paperList);
      // Pre-select all returned papers for convenience
      const preselect: Record<string, boolean> = {};
      paperList.forEach((p) => {
        preselect[p.id] = true;
      });
      setSelectedPaperMap(preselect);

      if (paperList.length === 0) {
        setErrorMessage(`No scientific papers found for "${query.trim()}". Try broadening your search.`);
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Paper search request failed.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialParams?.query) {
      handleSearch();
    }
  }, [initialParams?.query]);

  const toggleSelectPaper = (paperId: string) => {
    setSelectedPaperMap((prev) => ({
      ...prev,
      [paperId]: !prev[paperId],
    }));
  };

  const selectAll = () => {
    const all: Record<string, boolean> = {};
    papers.forEach((p) => {
      all[p.id] = true;
    });
    setSelectedPaperMap(all);
  };

  const deselectAll = () => {
    setSelectedPaperMap({});
  };

  const selectedCount = Object.values(selectedPaperMap).filter(Boolean).length;

  const handleAddSelectedToProject = async () => {
    if (!projectId) {
      setErrorMessage('Please select or create an active project first.');
      return;
    }
    const selectedList = papers.filter((p) => selectedPaperMap[p.id]);
    if (selectedList.length === 0) return;

    setLoading(true);
    setSuccessMessage(null);
    try {
      let added = 0;
      for (const p of selectedList) {
        await api.addPaperToProject(projectId, p);
        added++;
      }
      setSuccessMessage(`Successfully added ${added} paper(s) to project.`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to add papers to project.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setUploading(true);
    setErrorMessage(null);
    try {
      const doc = await api.uploadProjectDocument(projectId, file);
      setSuccessMessage(`Uploaded and extracted '${doc.filename}' (${doc.page_count} pages).`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to upload PDF.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#f7f8f8]">
            Literature Discovery & Paper Selection
          </h1>
          <p className="text-xs text-[#8b8f98] mt-0.5">
            Target Project: <span className="text-[#f7f8f8] font-medium">{projectName || projectId}</span>
          </p>
        </div>

        <button
          onClick={() => onNavigate('library')}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[#ffffff14] hover:bg-[#ffffff24] text-[#f7f8f8] text-xs font-semibold transition-all"
        >
          View Project Library
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Search Bar & Scope Filters */}
      <form
        onSubmit={handleSearch}
        className="portal-form-container rounded-2xl p-6 space-y-4"
      >
        <div className="flex flex-col sm:flex-row items-center gap-2.5">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-[#8b8f98] absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by keywords, title, or scientific topic..."
              className="w-full text-sm portal-input rounded-xl pl-10 pr-4 py-2.5 text-[#f7f8f8] placeholder-[#8b8f98]/50 focus:outline-none"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-[#7170ff] to-[#5856d6] hover:from-[#8281ff] hover:to-[#6a68e6] text-white text-xs font-semibold transition-all shadow-[0_4px_16px_rgba(113,112,255,0.3)] shrink-0 disabled:opacity-50 cursor-pointer"
          >
            {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
            Discover Papers
          </button>
        </div>

        {/* Secondary Parameters */}
        <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-white/[0.08] text-xs text-[#8b8f98]">
          <div className="flex items-center gap-2">
            <span>Database:</span>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as 'openalex' | 'crossref' | 'all')}
              className="portal-input rounded-lg px-2.5 py-1 text-[#f7f8f8] focus:outline-none cursor-pointer"
            >
              <option value="openalex" className="bg-[#0c0d12] text-[#f7f8f8]">OpenAlex (Recommended)</option>
              <option value="crossref" className="bg-[#0c0d12] text-[#f7f8f8]">Crossref</option>
              <option value="all" className="bg-[#0c0d12] text-[#f7f8f8]">All Sources</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span>Year:</span>
            <input
              type="number"
              placeholder="From"
              value={fromYear || ''}
              onChange={(e) => setFromYear(parseInt(e.target.value) || undefined)}
              className="w-20 portal-input rounded-lg px-2 py-1 text-[#f7f8f8] text-center"
            />
            <span>to</span>
            <input
              type="number"
              placeholder="To"
              value={toYear || ''}
              onChange={(e) => setToYear(parseInt(e.target.value) || undefined)}
              className="w-20 portal-input rounded-lg px-2 py-1 text-[#f7f8f8] text-center"
            />
          </div>

          <div className="flex items-center gap-2">
            <span>Results:</span>
            <select
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value))}
              className="portal-input rounded-lg px-2.5 py-1 text-[#f7f8f8] focus:outline-none cursor-pointer"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={30}>30</option>
            </select>
          </div>

          {/* Direct PDF Upload Option */}
          <div className="ml-auto flex items-center gap-2">
            <label className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md border border-[#ffffff14] hover:bg-[#ffffff0a] cursor-pointer text-[#f7f8f8] transition-all">
              <Upload className="w-3.5 h-3.5 text-[#7170ff]" />
              <span>{uploading ? 'Uploading PDF...' : 'Upload PDF'}</span>
              <input
                type="file"
                accept=".pdf"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
            </label>
          </div>
        </div>
      </form>

      {/* Feedback Alerts */}
      {errorMessage && (
        <div className="flex items-center gap-2.5 p-3.5 rounded-lg bg-[#ff5b5b]/10 border border-[#ff5b5b]/30 text-[#ff5b5b] text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
      {successMessage && (
        <div className="flex items-center justify-between p-3.5 rounded-lg bg-[#2ecc71]/10 border border-[#2ecc71]/30 text-[#2ecc71] text-xs">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button
            onClick={() => onNavigate('library')}
            className="underline font-semibold hover:opacity-80"
          >
            Go to Library →
          </button>
        </div>
      )}

      {/* Results Controls Bar */}
      {papers.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-2">
          <div className="flex items-center gap-3 text-xs text-[#8b8f98]">
            <span>{papers.length} papers found</span>
            <span>•</span>
            <button onClick={selectAll} className="hover:text-[#f7f8f8] underline">
              Select All
            </button>
            <button onClick={deselectAll} className="hover:text-[#f7f8f8] underline">
              Deselect All
            </button>
          </div>

          <button
            onClick={handleAddSelectedToProject}
            disabled={selectedCount === 0 || loading}
            className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-[#e5e5e6] hover:bg-[#f7f8f8] disabled:opacity-40 text-[#08090a] text-xs font-semibold shadow-md transition-all"
          >
            <Plus className="w-4 h-4" />
            Add {selectedCount} Selected Paper(s) to Project
          </button>
        </div>
      )}

      {/* Paper Cards List */}
      <div className="space-y-3.5">
        {papers.map((paper) => {
          const isSelected = !!selectedPaperMap[paper.id];
          const isExpanded = !!expandedAbstracts[paper.id];

          return (
            <div
              key={paper.id}
              onClick={() => toggleSelectPaper(paper.id)}
              className={`portal-card rounded-2xl p-5 transition-all cursor-pointer ${
                isSelected
                  ? '!border-[#7170ff] bg-[#7170ff]/10 shadow-[0_0_20px_rgba(113,112,255,0.15)]'
                  : 'hover:border-white/[0.18]'
              }`}
            >
              <div className="flex items-start gap-4">
                {/* Selection Checkbox */}
                <div className="pt-0.5 shrink-0 text-[#7170ff]">
                  {isSelected ? (
                    <CheckSquare className="w-5 h-5" />
                  ) : (
                    <Square className="w-5 h-5 text-[#8b8f98]" />
                  )}
                </div>

                {/* Paper Details */}
                <div className="flex-1 space-y-2 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-[#ffffff0a] text-[#8b8f98]">
                      {paper.source}
                    </span>
                    {paper.publication_year && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#ffffff0a] text-[#f7f8f8]">
                        {paper.publication_year}
                      </span>
                    )}
                    {paper.open_access_pdf_url && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#2ecc71]/10 text-[#2ecc71]">
                        Open Access PDF
                      </span>
                    )}
                  </div>

                  <h3 className="text-sm font-semibold text-[#f7f8f8] leading-snug">
                    {paper.title}
                  </h3>

                  {(paper.authors?.length ?? 0) > 0 && (
                    <p className="text-xs text-[#8b8f98] truncate">
                      {paper.authors.join(', ')}
                    </p>
                  )}

                  {paper.abstract && (
                    <div>
                      <p
                        className={`text-xs text-[#a1a5ad] leading-relaxed ${
                          isExpanded ? '' : 'line-clamp-2'
                        }`}
                      >
                        {paper.abstract}
                      </p>
                      {paper.abstract.length > 180 && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setExpandedAbstracts((prev) => ({
                              ...prev,
                              [paper.id]: !prev[paper.id],
                            }));
                          }}
                          className="mt-1 text-[11px] text-[#7170ff] hover:underline font-medium"
                        >
                          {isExpanded ? 'Show less' : 'Read full abstract'}
                        </button>
                      )}
                    </div>
                  )}

                  {/* External Links */}
                  <div className="flex items-center gap-3 pt-1 text-[11px] text-[#8b8f98]">
                    {paper.doi && (
                      <a
                        href={`https://doi.org/${paper.doi}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="hover:text-[#f7f8f8] underline inline-flex items-center gap-1 font-mono"
                      >
                        doi:{paper.doi}
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                    {paper.open_access_pdf_url && (
                      <a
                        href={paper.open_access_pdf_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-[#2ecc71] hover:underline inline-flex items-center gap-1"
                      >
                        Direct PDF
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
