'use client';

import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  PlusCircle,
  Search,
  Library,
  Cpu,
  Split,
  GitGraph,
  FileSpreadsheet,
  FolderGit2,
  Sparkles,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { ProjectResponse, LLMStatusResponse } from '@/types/papertrail';
import { api } from '@/services/api';

export type ScreenId =
  | 'dashboard'
  | 'new_research'
  | 'discovery'
  | 'library'
  | 'analysis'
  | 'comparison'
  | 'graph'
  | 'report';

interface NavbarProps {
  activeScreen: ScreenId;
  onNavigate: (screen: ScreenId) => void;
  projects: ProjectResponse[];
  selectedProjectId: string;
  onSelectProject: (id: string) => void;
  refreshProjects: () => void;
}

export function Navbar({
  activeScreen,
  onNavigate,
  projects,
  selectedProjectId,
  onSelectProject,
}: NavbarProps) {
  const [llmStatus, setLlmStatus] = useState<LLMStatusResponse | null>(null);

  useEffect(() => {
    api
      .getLLMStatus()
      .then(setLlmStatus)
      .catch(() => {
        // quiet fallback
      });
  }, []);

  const navItems: Array<{ id: ScreenId; label: string; icon: React.ComponentType<{ className?: string }> }> = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'new_research', label: 'New Research', icon: PlusCircle },
    { id: 'discovery', label: 'Discovery', icon: Search },
    { id: 'library', label: 'Paper Library', icon: Library },
    { id: 'analysis', label: 'Analysis Workspace', icon: Cpu },
    { id: 'comparison', label: 'Comparison', icon: Split },
    { id: 'graph', label: 'Evidence Graph', icon: GitGraph },
    { id: 'report', label: 'Research Report', icon: FileSpreadsheet },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/[0.08] bg-[#07080a]/85 backdrop-blur-xl shadow-[0_4px_24px_rgba(0,0,0,0.4)]">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6">
        <div className="flex h-16 items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => onNavigate('dashboard')}
              className="flex items-center gap-2.5 text-left focus:outline-none group"
            >
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#7170ff] via-[#6366f1] to-[#38bdf8] border border-[#7170ff]/40 flex items-center justify-center text-white shadow-[0_0_20px_rgba(113,112,255,0.35)] transition-transform group-hover:scale-105">
                <svg viewBox="0 0 64 64" fill="none" className="w-5 h-5">
                  <path
                    d="M14 20C14 16.6863 16.6863 14 20 14H36L50 28V46C50 49.3137 47.3137 52 44 52H20C16.6863 52 14 49.3137 14 46V20Z"
                    stroke="#ffffff"
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="opacity-80"
                  />
                  <path d="M22 28H34M22 36H42M22 44H38" stroke="#ffffff" strokeWidth="3" strokeLinecap="round" />
                  <circle cx="42" cy="22" r="3.5" fill="#38bdf8" />
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-extrabold text-sm tracking-tight bg-gradient-to-r from-white via-[#f7f8f8] to-[#9d9cfc] text-transparent bg-clip-text">
                    PaperTrail
                  </span>
                  <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#7170ff]/15 text-[#9d9cfc] border border-[#7170ff]/20">
                    PORTAL
                  </span>
                </div>
                <span className="block text-[10px] text-[#8b8f98] font-mono leading-none tracking-wide">
                  Scientific Integrity Platform
                </span>
              </div>
            </button>
          </div>

          {/* Project Selector & LLM status pill */}
          <div className="flex items-center gap-3">
            {projects.length > 0 && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#0f1011] border border-[#ffffff14]">
                <FolderGit2 className="w-3.5 h-3.5 text-[#8b8f98]" />
                <select
                  value={selectedProjectId}
                  onChange={(e) => onSelectProject(e.target.value)}
                  className="bg-transparent text-xs font-medium text-[#f7f8f8] focus:outline-none cursor-pointer max-w-[200px] truncate"
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id} className="bg-[#0f1011] text-[#f7f8f8]">
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* LLM Status Pill */}
            {llmStatus && (
              <div
                title={llmStatus.message}
                className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#0f1011] border border-[#ffffff14] text-[#8b8f98]"
              >
                {llmStatus.status === 'ready' ? (
                  <CheckCircle2 className="w-3 h-3 text-[#2ecc71]" />
                ) : (
                  <AlertCircle className="w-3 h-3 text-[#f5c542]" />
                )}
                <span className="capitalize">{llmStatus.provider}</span>
                <span className="text-[#a1a5ad] font-mono text-[10px]">({llmStatus.model})</span>
              </div>
            )}
          </div>
        </div>

        {/* Horizontal Navigation Ladder */}
        <nav className="flex items-center gap-1 overflow-x-auto py-1.5 scrollbar-none border-t border-[#ffffff0a]">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeScreen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-150 ${
                  isActive
                    ? 'bg-[#7170ff] text-white shadow-sm shadow-[#7170ff]/20 font-semibold'
                    : 'text-[#8b8f98] hover:text-[#f7f8f8] hover:bg-[#ffffff0a]'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-[#8b8f98]'}`} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
