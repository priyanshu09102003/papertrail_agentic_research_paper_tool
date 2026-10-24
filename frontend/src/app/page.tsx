'use client';

import React, { useEffect, useState } from 'react';
import { Navbar, ScreenId } from '@/components/Navbar';
import { BrandLoader } from '@/components/BrandLoader';
import { DashboardScreen } from '@/components/DashboardScreen';
import { NewResearchScreen } from '@/components/NewResearchScreen';
import { DiscoveryScreen } from '@/components/DiscoveryScreen';
import { PaperLibraryScreen } from '@/components/PaperLibraryScreen';
import { AnalysisWorkspaceScreen } from '@/components/AnalysisWorkspaceScreen';
import { ComparisonExplorerScreen } from '@/components/ComparisonExplorerScreen';
import { ClaimGraphScreen } from '@/components/ClaimGraphScreen';
import { ResearchReportScreen } from '@/components/ResearchReportScreen';
import { ProjectResponse } from '@/types/papertrail';
import { api } from '@/services/api';

export default function App() {
  const [activeScreen, setActiveScreen] = useState<ScreenId>('dashboard');
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [showBrandLoader, setShowBrandLoader] = useState(true);

  // Cross-screen discovery search params
  const [discoveryParams, setDiscoveryParams] = useState<{
    query: string;
    fromYear?: number;
    toYear?: number;
    limit?: number;
  }>({
    query: '',
  });

  const refreshProjects = async () => {
    try {
      const list = await api.fetchProjects();
      setProjects(list);
      if (list.length > 0 && !selectedProjectId) {
        setSelectedProjectId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load projects list:', err);
    }
  };

  useEffect(() => {
    refreshProjects();
  }, []);

  const handleNavigate = (
    screen: ScreenId,
    projectId?: string,
    initialSearchParams?: {
      query: string;
      fromYear?: number;
      toYear?: number;
      limit?: number;
    }
  ) => {
    if (projectId) {
      setSelectedProjectId(projectId);
    }
    if (initialSearchParams) {
      setDiscoveryParams(initialSearchParams);
    }
    setActiveScreen(screen);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleProjectCreated = (newId: string) => {
    setSelectedProjectId(newId);
    refreshProjects();
  };

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <div className="min-h-screen text-[#f7f8f8] flex flex-col font-sans selection:bg-[#7170ff]/30 selection:text-white relative bg-[#08090a]">
      {/* Background Ambient Flares & Subtle Scientific Grid */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-[15%] left-[10%] w-[680px] h-[680px] rounded-full bg-gradient-to-br from-[#7170ff]/14 via-[#4f46e5]/07 to-transparent blur-[140px]" />
        <div className="absolute top-[35%] -right-[10%] w-[620px] h-[620px] rounded-full bg-gradient-to-bl from-[#38bdf8]/10 via-[#6366f1]/05 to-transparent blur-[150px]" />
        <div className="absolute -bottom-[10%] left-[25%] w-[580px] h-[580px] rounded-full bg-gradient-to-tr from-[#7170ff]/09 via-[#a855f7]/05 to-transparent blur-[140px]" />
        <div className="absolute inset-0 bg-portal-grid opacity-45" />
      </div>

      {/* Brand Logo Animation Loader */}
      {showBrandLoader && <BrandLoader onFinish={() => setShowBrandLoader(false)} />}

      <div className="relative z-10 flex flex-col min-h-screen">
        {/* Top Sticky Navbar */}
        <Navbar
          activeScreen={activeScreen}
          onNavigate={handleNavigate}
          projects={projects}
          selectedProjectId={selectedProjectId}
          onSelectProject={(id) => setSelectedProjectId(id)}
          refreshProjects={refreshProjects}
        />

        {/* Main Content Area */}
        <main className="flex-1 w-full max-w-[1600px] mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {activeScreen === 'dashboard' && (
          <DashboardScreen
            onNavigate={handleNavigate}
            selectedProjectId={selectedProjectId}
            onSelectProject={(id) => setSelectedProjectId(id)}
          />
        )}

        {activeScreen === 'new_research' && (
          <NewResearchScreen
            onNavigate={handleNavigate}
            onProjectCreated={handleProjectCreated}
          />
        )}

        {activeScreen === 'discovery' && (
          <DiscoveryScreen
            projectId={selectedProjectId}
            projectName={selectedProject?.name}
            initialParams={discoveryParams}
            onNavigate={handleNavigate}
          />
        )}

        {activeScreen === 'library' && (
          <PaperLibraryScreen
            projectId={selectedProjectId}
            projectName={selectedProject?.name}
            onNavigate={handleNavigate}
          />
        )}

        {activeScreen === 'analysis' && (
          <AnalysisWorkspaceScreen
            projectId={selectedProjectId}
            projectName={selectedProject?.name}
            onNavigate={handleNavigate}
          />
        )}

        {activeScreen === 'comparison' && (
          <ComparisonExplorerScreen
            projectId={selectedProjectId}
            projectName={selectedProject?.name}
            onNavigate={handleNavigate}
          />
        )}

        {activeScreen === 'graph' && (
          <ClaimGraphScreen
            projectId={selectedProjectId}
            projectName={selectedProject?.name}
          />
        )}

        {activeScreen === 'report' && (
          <ResearchReportScreen
            projectId={selectedProjectId}
            projectName={selectedProject?.name}
            onNavigate={handleNavigate}
          />
        )}
      </main>
      </div>
    </div>
  );
}
