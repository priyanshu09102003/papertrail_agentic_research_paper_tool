'use client';

import React, { useEffect, useState } from 'react';
import { ClaimGraphViewer } from '@/components/ClaimGraphViewer';
import {
  FolderGit2,
  Sparkles,
  GitGraph,
  RefreshCw,
  PlusCircle,
  FileText,
  AlertCircle,
} from 'lucide-react';
import { ProjectSummary } from '@/types/claim-graph';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function HomePage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [newProjectName, setNewProjectName] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const fetchProjects = async () => {
    setLoadingProjects(true);
    try {
      const resp = await fetch(`${API_BASE}/api/projects`);
      if (resp.ok) {
        const data = await resp.json();
        setProjects(data);
        if (data.length > 0 && !selectedProjectId) {
          setSelectedProjectId(data[0].id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch projects', err);
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    setIsCreating(true);
    try {
      const resp = await fetch(`${API_BASE}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newProjectName }),
      });
      if (resp.ok) {
        const created = await resp.json();
        setProjects([created, ...projects]);
        setSelectedProjectId(created.id);
        setNewProjectName('');
      }
    } catch (err) {
      console.error('Error creating project', err);
    } finally {
      setIsCreating(false);
    }
  };

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black text-zinc-900 dark:text-zinc-50 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 border-b border-zinc-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/80 backdrop-blur px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-md">
              <GitGraph className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight">PaperTrail</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-full">
                  Evidence Graph
                </span>
              </div>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Cross-Paper Scientific Claim & Contradiction Analysis
              </p>
            </div>
          </div>

          {/* Project Selector & Actions */}
          <div className="flex items-center gap-3">
            {loadingProjects ? (
              <RefreshCw className="w-4 h-4 animate-spin text-zinc-400" />
            ) : projects.length > 0 ? (
              <div className="flex items-center gap-2">
                <FolderGit2 className="w-4 h-4 text-zinc-400" />
                <select
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  className="text-xs font-semibold bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 px-3 py-1.5 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.id})
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            {/* Quick create modal or inline form */}
            <form onSubmit={handleCreateProject} className="flex items-center gap-1.5">
              <input
                type="text"
                placeholder="New project name..."
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                className="text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 px-3 py-1.5 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 w-36 sm:w-44"
              />
              <button
                type="submit"
                disabled={isCreating || !newProjectName.trim()}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-colors shadow-sm"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                Create
              </button>
            </form>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 flex flex-col">
        {selectedProjectId ? (
          <ClaimGraphViewer
            projectId={selectedProjectId}
            projectName={selectedProject?.name}
          />
        ) : (
          <div className="flex flex-col items-center justify-center min-h-[460px] bg-white dark:bg-zinc-900/60 rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-800 p-12 text-center">
            <FolderGit2 className="w-12 h-12 text-zinc-400 mb-3" />
            <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              No Project Selected
            </h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 max-w-sm">
              Create a research project or select an existing one above to visualize the claim-to-evidence graph.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
