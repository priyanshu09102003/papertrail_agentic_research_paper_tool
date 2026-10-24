'use client';

import React, { useEffect, useState } from 'react';
import {
  Library,
  BookOpen,
  FileText,
  Trash2,
  ExternalLink,
  Plus,
  RefreshCw,
  Cpu,
  ArrowRight,
  Upload,
  CheckCircle2,
  AlertCircle,
  FolderOpen,
} from 'lucide-react';
import { DocumentMetadata, Paper } from '@/types/papertrail';
import { api } from '@/services/api';
import { ScreenId } from './Navbar';

interface PaperLibraryScreenProps {
  projectId: string;
  projectName?: string;
  onNavigate: (screen: ScreenId) => void;
}

export function PaperLibraryScreen({
  projectId,
  projectName,
  onNavigate,
}: PaperLibraryScreenProps) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Uploading state
  const [uploading, setUploading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadLibrary = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [paperList, docList] = await Promise.all([
        api.listProjectPapers(projectId),
        api.listProjectDocuments(projectId),
      ]);
      setPapers(paperList);
      setDocuments(docList);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load project library.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLibrary();
  }, [projectId]);

  const handleRemovePaper = async (paperId: string, title: string) => {
    if (!confirm(`Remove "${title}" from this project?`)) return;
    try {
      await api.removePaperFromProject(projectId, paperId);
      setPapers((prev) => prev.filter((p) => p.id !== paperId));
      setActionMessage(`Removed paper from project library.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to remove paper.');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setUploading(true);
    setError(null);
    try {
      const doc = await api.uploadProjectDocument(projectId, file);
      setDocuments((prev) => [doc, ...prev]);
      setActionMessage(`Uploaded '${doc.filename}' (${doc.page_count} pages).`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to upload PDF.');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const totalItems = papers.length + documents.length;

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#f7f8f8]">
              Project Paper Library
            </h1>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#7170ff]/10 text-[#7170ff] font-semibold">
              {totalItems} source(s)
            </span>
          </div>
          <p className="text-xs text-[#8b8f98] mt-0.5">
            Project: <span className="text-[#f7f8f8] font-medium">{projectName || projectId}</span>
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => onNavigate('discovery')}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full border border-[#ffffff14] hover:bg-[#ffffff0a] text-[#f7f8f8] text-xs font-medium transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            Discover More Papers
          </button>

          <label className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full border border-[#ffffff14] hover:bg-[#ffffff0a] text-[#f7f8f8] text-xs font-medium cursor-pointer transition-all">
            <Upload className="w-3.5 h-3.5 text-[#7170ff]" />
            <span>{uploading ? 'Uploading...' : 'Upload PDF'}</span>
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>

          {totalItems >= 2 && (
            <button
              onClick={() => onNavigate('analysis')}
              className="inline-flex items-center gap-2 px-5 py-2 rounded-full bg-[#e5e5e6] hover:bg-[#f7f8f8] text-[#08090a] text-xs font-semibold shadow-md transition-all"
            >
              <Cpu className="w-4 h-4" />
              Launch Analysis Workspace
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Action Messages */}
      {error && (
        <div className="flex items-center gap-2.5 p-3.5 rounded-lg bg-[#ff5b5b]/10 border border-[#ff5b5b]/30 text-[#ff5b5b] text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {actionMessage && (
        <div className="flex items-center gap-2.5 p-3.5 rounded-lg bg-[#2ecc71]/10 border border-[#2ecc71]/30 text-[#2ecc71] text-xs">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{actionMessage}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center p-12 text-[#8b8f98] gap-2 text-xs">
          <RefreshCw className="w-5 h-5 animate-spin text-[#7170ff]" />
          Loading project papers...
        </div>
      ) : totalItems === 0 ? (
        <div className="rounded-xl border border-dashed border-[#ffffff14] p-12 text-center space-y-4 bg-[#0f1011]">
          <Library className="w-10 h-10 text-[#8b8f98] mx-auto opacity-50" />
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-[#f7f8f8]">No Papers in This Project Yet</h3>
            <p className="text-xs text-[#8b8f98] max-w-md mx-auto">
              Add papers via scholarly discovery or upload research PDFs directly to build your comparison corpus.
            </p>
          </div>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => onNavigate('discovery')}
              className="px-5 py-2 rounded-full bg-[#e5e5e6] text-[#08090a] text-xs font-semibold"
            >
              Discover Papers
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          {/* Uploaded PDF Documents Section */}
          {documents.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#8b8f98]">
                <FolderOpen className="w-4 h-4 text-[#7170ff]" />
                Uploaded Research PDFs ({documents.length})
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {documents.map((doc) => (
                  <div
                    key={doc.document_id}
                    className="portal-card rounded-2xl p-4 flex flex-col justify-between space-y-3"
                  >
                    <div>
                      <div className="flex items-center justify-between text-[11px] text-[#8b8f98]">
                        <span className="font-mono">{doc.document_id}</span>
                        <span className="px-2 py-0.5 rounded bg-[#2ecc71]/10 text-[#2ecc71] font-semibold">
                          {doc.extraction_status}
                        </span>
                      </div>
                      <h4 className="text-xs font-semibold text-[#f7f8f8] mt-1.5 leading-snug line-clamp-2">
                        {doc.filename}
                      </h4>
                      <div className="flex items-center gap-3 mt-2 text-[11px] text-[#8b8f98] font-mono">
                        <span>{doc.page_count} pages</span>
                        <span>•</span>
                        <span>{Math.round(doc.file_size_bytes / 1024)} KB</span>
                        <span>•</span>
                        <span>{doc.total_words} words</span>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-[#ffffff0a] flex items-center justify-between">
                      <a
                        href={api.getDocumentFileUrl(doc.document_id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-[#7170ff] hover:underline inline-flex items-center gap-1 font-medium"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        View PDF File
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Associated Scholarly Papers Section */}
          {papers.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#8b8f98]">
                <BookOpen className="w-4 h-4 text-[#7170ff]" />
                Discovered Papers ({papers.length})
              </div>
              <div className="space-y-3">
                {papers.map((paper) => (
                  <div
                    key={paper.id}
                    className="portal-card rounded-2xl p-5 space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[#ffffff0a] text-[#8b8f98]">
                            {paper.source}
                          </span>
                          {paper.publication_year && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#ffffff0a] text-[#f7f8f8]">
                              {paper.publication_year}
                            </span>
                          )}
                          {paper.open_access_pdf_url && (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#2ecc71]/10 text-[#2ecc71]">
                              Open Access
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
                      </div>

                      <button
                        onClick={() => handleRemovePaper(paper.id, paper.title)}
                        className="text-[#8b8f98] hover:text-[#ff5b5b] p-1.5 rounded-lg hover:bg-[#ffffff0a] transition-colors shrink-0"
                        title="Remove paper from project"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {paper.abstract && (
                      <p className="text-xs text-[#a1a5ad] line-clamp-3 leading-relaxed">
                        {paper.abstract}
                      </p>
                    )}

                    <div className="flex items-center gap-4 pt-1 text-[11px] text-[#8b8f98]">
                      {paper.doi && (
                        <a
                          href={`https://doi.org/${paper.doi}`}
                          target="_blank"
                          rel="noopener noreferrer"
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
                          className="text-[#2ecc71] hover:underline inline-flex items-center gap-1"
                        >
                          Direct PDF
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
