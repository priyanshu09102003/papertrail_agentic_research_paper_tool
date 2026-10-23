'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Node,
  Edge,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import {
  ClaimGraphEdgeData,
  ClaimGraphNodeData,
  ProjectClaimGraphResponse,
} from '@/types/claim-graph';
import {
  PaperNode,
  ClaimNode,
  EvidenceNode,
  DatasetNode,
  MethodNode,
  MetricNode,
} from './nodes/CustomNodes';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  Filter,
  Info,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const nodeTypes = {
  paper: PaperNode,
  claim: ClaimNode,
  evidence: EvidenceNode,
  dataset: DatasetNode,
  method: MethodNode,
  metric: MetricNode,
};

interface ClaimGraphViewerProps {
  projectId: string;
  projectName?: string;
}

export function ClaimGraphViewer({ projectId, projectName }: ClaimGraphViewerProps) {
  const [graphData, setGraphData] = useState<ProjectClaimGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected item for details panel
  const [selectedNode, setSelectedNode] = useState<ClaimGraphNodeData | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<ClaimGraphEdgeData | null>(null);

  // Filtering state
  const [selectedPaperFilter, setSelectedPaperFilter] = useState<string>('all');
  const [selectedRelFilter, setSelectedRelFilter] = useState<string>('all');
  const [claimSearch, setClaimSearch] = useState<string>('');
  const [contradictionsOnly, setContradictionsOnly] = useState<boolean>(false);

  // Fetch graph from backend API
  const fetchGraph = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/projects/${projectId}/claim-graph`);
      if (!resp.ok) {
        throw new Error(`Failed to load research graph (HTTP ${resp.status})`);
      }
      const data: ProjectClaimGraphResponse = await resp.json();
      setGraphData(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred while loading graph.');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Transform raw backend graphData into ReactFlow nodes & edges with filtering applied
  const { flowNodes, flowEdges } = useMemo(() => {
    if (!graphData || graphData.is_empty) {
      return { flowNodes: [], flowEdges: [] };
    }

    const { nodes: rawNodes, edges: rawEdges } = graphData;

    // Filter nodes by paper selection
    let activeNodes = rawNodes;
    if (selectedPaperFilter !== 'all') {
      const paperDocId = selectedPaperFilter.replace('paper_', '');
      activeNodes = rawNodes.filter(
        (n) => n.id === selectedPaperFilter || n.document_id === paperDocId
      );
    }

    // Filter claims by text search
    if (claimSearch.trim()) {
      const query = claimSearch.toLowerCase();
      const matchingClaimIds = new Set(
        rawNodes
          .filter((n) => n.type === 'claim' && n.title.toLowerCase().includes(query))
          .map((n) => n.id)
      );

      // Keep claims matching query and nodes connected to them
      if (matchingClaimIds.size > 0) {
        const connectedNodeIds = new Set<string>(matchingClaimIds);
        rawEdges.forEach((e) => {
          if (matchingClaimIds.has(e.source)) connectedNodeIds.add(e.target);
          if (matchingClaimIds.has(e.target)) connectedNodeIds.add(e.source);
        });
        activeNodes = activeNodes.filter((n) => connectedNodeIds.has(n.id));
      }
    }

    const activeNodeIdSet = new Set(activeNodes.map((n) => n.id));

    // Filter edges
    let activeEdges = rawEdges.filter(
      (e) => activeNodeIdSet.has(e.source) && activeNodeIdSet.has(e.target)
    );

    if (contradictionsOnly) {
      activeEdges = activeEdges.filter((e) => e.is_contradiction);
      const contradictionNodeIds = new Set<string>();
      activeEdges.forEach((e) => {
        contradictionNodeIds.add(e.source);
        contradictionNodeIds.add(e.target);
      });
      activeNodes = activeNodes.filter((n) => contradictionNodeIds.has(n.id));
    } else if (selectedRelFilter !== 'all') {
      activeEdges = activeEdges.filter((e) => e.relationship_type === selectedRelFilter);
    }

    // Convert to ReactFlow Node array
    const nodes: Node[] = activeNodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position || { x: 0, y: 0 },
      data: n,
    }));

    // Convert to ReactFlow Edge array with explicit styling
    const edges: Edge[] = activeEdges.map((e) => {
      let strokeColor = '#94a3b8'; // default slate-400
      let strokeWidth = 1.5;
      let isDashed = false;
      let isAnimated = false;

      if (e.is_contradiction) {
        strokeColor = '#ef4444'; // Red for potential contradiction
        strokeWidth = 2.5;
        isAnimated = true;
      } else if (e.relationship_type === 'supported_by') {
        strokeColor = '#10b981'; // Emerald for supported evidence
        strokeWidth = 2;
      } else if (e.relationship_type === 'agrees_with' || e.relationship_type === 'agreement') {
        strokeColor = '#0ea5e9'; // Blue for agreement
        strokeWidth = 2;
      } else if (e.relationship_type === 'conditional_difference') {
        strokeColor = '#f59e0b'; // Amber for conditional difference
        strokeWidth = 2;
        isDashed = true;
      } else if (e.relationship_type === 'uses_dataset') {
        strokeColor = '#f59e0b';
        isDashed = true;
      } else if (e.relationship_type === 'depends_on') {
        strokeColor = '#06b6d4';
        isDashed = true;
      } else if (e.relationship_type === 'evaluated_using') {
        strokeColor = '#8b5cf6';
        isDashed = true;
      }

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        type: 'smoothstep',
        animated: isAnimated,
        style: {
          stroke: strokeColor,
          strokeWidth,
          strokeDasharray: isDashed ? '5 5' : undefined,
        },
        labelStyle: {
          fill: e.is_contradiction ? '#b91c1c' : '#334155',
          fontWeight: e.is_contradiction ? 700 : 500,
          fontSize: 11,
        },
        labelBgStyle: {
          fill: e.is_contradiction ? '#fee2e2' : '#f8fafc',
          fillOpacity: 0.95,
        },
        labelBgBorderRadius: 6,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 16,
          height: 16,
        },
        data: e,
      };
    });

    return { flowNodes: nodes, flowEdges: edges };
  }, [graphData, selectedPaperFilter, selectedRelFilter, claimSearch, contradictionsOnly]);

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  // Sync internal state when filters change
  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node.data as unknown as ClaimGraphNodeData);
    setSelectedEdge(null);
  }, []);

  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdge(edge.data as unknown as ClaimGraphEdgeData);
    setSelectedNode(null);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
    setSelectedEdge(null);
  }, []);

  // Loading state
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[460px] bg-zinc-50 dark:bg-zinc-950 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-8">
        <RefreshCw className="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin mb-4" />
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          Loading Claim-to-Evidence Graph...
        </h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          Synthesizing claims, verified evidence passages, and contradiction matrices.
        </p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[460px] bg-red-50/50 dark:bg-red-950/20 rounded-2xl border border-red-200 dark:border-red-900 p-8 text-center">
        <AlertTriangle className="w-10 h-10 text-red-600 dark:text-red-400 mb-3" />
        <h3 className="text-base font-semibold text-red-900 dark:text-red-200">
          Failed to Load Graph
        </h3>
        <p className="text-sm text-red-700 dark:text-red-400 mt-1 max-w-md">
          {error}
        </p>
        <button
          onClick={fetchGraph}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      </div>
    );
  }

  // Empty state
  if (!graphData || graphData.is_empty || flowNodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[460px] bg-zinc-50 dark:bg-zinc-900/40 rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-800 p-10 text-center">
        <div className="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-950 flex items-center justify-center text-blue-600 dark:text-blue-400 mb-3">
          <BookOpen className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          No Analyzed Claims Found
        </h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 max-w-md">
          {graphData?.message ||
            'Upload and analyze research papers in this project to generate the claim-to-evidence graph.'}
        </p>
        <button
          onClick={fetchGraph}
          className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-xs font-semibold rounded-lg hover:opacity-90 transition-opacity"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Check Again
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full h-[calc(100vh-140px)] min-h-[600px] border border-zinc-200 dark:border-zinc-800 rounded-2xl overflow-hidden bg-white dark:bg-zinc-950 shadow-sm relative">
      {/* Top Filter and Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/80 backdrop-blur z-10">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">
              Claim-to-Evidence Graph
            </span>
            {projectName && (
              <span className="text-xs text-zinc-500 dark:text-zinc-400 hidden sm:inline">
                • {projectName}
              </span>
            )}
          </div>
          <span className="text-xs bg-zinc-200/70 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium px-2 py-0.5 rounded-full">
            {flowNodes.length} nodes • {flowEdges.length} edges
          </span>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Claim Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search claims..."
              value={claimSearch}
              onChange={(e) => setClaimSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 w-36 sm:w-44 text-zinc-900 dark:text-zinc-100"
            />
          </div>

          {/* Paper Filter */}
          <select
            value={selectedPaperFilter}
            onChange={(e) => setSelectedPaperFilter(e.target.value)}
            className="text-xs bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 px-2.5 py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All Papers ({graphData.available_papers.length})</option>
            {graphData.available_papers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title.length > 25 ? `${p.title.slice(0, 25)}...` : p.title}
              </option>
            ))}
          </select>

          {/* Relationship Type Filter */}
          <select
            value={selectedRelFilter}
            onChange={(e) => setSelectedRelFilter(e.target.value)}
            className="text-xs bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 px-2.5 py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">All Relationships</option>
            {graphData.available_relationship_types.map((rel) => (
              <option key={rel} value={rel}>
                {rel.replace(/_/g, ' ')}
              </option>
            ))}
          </select>

          {/* Contradictions Quick Toggle */}
          <button
            onClick={() => setContradictionsOnly(!contradictionsOnly)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              contradictionsOnly
                ? 'bg-red-600 text-white shadow-sm ring-2 ring-red-400/40'
                : 'bg-white dark:bg-zinc-800 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900/60 hover:bg-red-50 dark:hover:bg-red-950/30'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            Contradictions Only
          </button>

          <button
            onClick={fetchGraph}
            title="Refresh Graph"
            className="p-1.5 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-200/60 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 w-full h-full relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          onPaneClick={onPaneClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.2}
          maxZoom={1.8}
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#94a3b833" />
          <Controls position="bottom-left" showInteractive={false} />
          <MiniMap
            position="bottom-right"
            zoomable
            pannable
            nodeColor={(n) => {
              if (n.type === 'paper') return '#3b82f6';
              if (n.type === 'claim') return '#a855f7';
              if (n.type === 'evidence') return '#10b981';
              if (n.type === 'dataset') return '#f59e0b';
              if (n.type === 'method') return '#06b6d4';
              if (n.type === 'metric') return '#6366f1';
              return '#94a3b8';
            }}
            className="!bg-white/90 dark:!bg-zinc-900/90 !border !border-zinc-200 dark:!border-zinc-800 !rounded-xl !shadow-md"
          />
        </ReactFlow>

        {/* Legend Overlay */}
        <div className="absolute top-4 left-4 bg-white/90 dark:bg-zinc-900/90 backdrop-blur border border-zinc-200 dark:border-zinc-800 rounded-xl p-3 shadow-md pointer-events-none text-[11px] flex flex-col gap-1.5 z-10">
          <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-xs mb-0.5">Legend</span>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Paper</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Claim</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Evidence (Page cited)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
            <span className="text-zinc-600 dark:text-zinc-400">Dataset / Method</span>
          </div>
          <div className="pt-1 mt-1 border-t border-zinc-200 dark:border-zinc-800 flex items-center gap-2 font-medium">
            <span className="w-3.5 h-1 bg-red-500 rounded" />
            <span className="text-red-600 dark:text-red-400">Potential Contradiction</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3.5 h-1 bg-emerald-500 rounded" />
            <span className="text-emerald-600 dark:text-emerald-400">Supported By</span>
          </div>
        </div>

        {/* Node Details Slide-Out Panel */}
        {selectedNode && (
          <div className="absolute top-4 right-4 bottom-4 w-80 sm:w-96 bg-white/95 dark:bg-zinc-900/95 backdrop-blur border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl p-5 flex flex-col overflow-y-auto z-20 transition-all duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-200 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200">
                  {selectedNode.type}
                </span>
                {selectedNode.status && (
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
                    • {selectedNode.status}
                  </span>
                )}
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-4 flex-1 space-y-4">
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                  {selectedNode.type === 'evidence' ? 'Verbatim Passage' : 'Title / Text'}
                </label>
                <p className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-100 leading-relaxed">
                  {selectedNode.quote || selectedNode.title || selectedNode.label}
                </p>
              </div>

              {selectedNode.paper_title && (
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                    Source Paper
                  </label>
                  <p className="mt-1 text-xs text-zinc-700 dark:text-zinc-300 font-medium">
                    {selectedNode.paper_title}
                  </p>
                </div>
              )}

              {selectedNode.page_number && (
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 text-xs font-semibold rounded-lg">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Verified on Page {selectedNode.page_number}
                  </span>
                </div>
              )}

              {selectedNode.field_supported && (
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                    Field Supported
                  </label>
                  <p className="mt-1 text-xs font-mono text-zinc-600 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-2 py-1 rounded">
                    {selectedNode.field_supported}
                  </p>
                </div>
              )}

              {/* Direct Link to PDF */}
              {selectedNode.pdf_url && (
                <div className="pt-2">
                  <a
                    href={
                      selectedNode.pdf_url.startsWith('http')
                        ? selectedNode.pdf_url
                        : `${API_BASE}${selectedNode.pdf_url}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-xl shadow-sm transition-colors"
                  >
                    <BookOpen className="w-4 h-4" />
                    {selectedNode.page_number
                      ? `Open PDF at Page ${selectedNode.page_number}`
                      : 'View Original PDF'}
                    <ExternalLink className="w-3.5 h-3.5 ml-auto" />
                  </a>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Edge Details Slide-Out Panel */}
        {selectedEdge && (
          <div className="absolute top-4 right-4 bottom-4 w-80 sm:w-96 bg-white/95 dark:bg-zinc-900/95 backdrop-blur border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl p-5 flex flex-col overflow-y-auto z-20 transition-all duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-200 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${
                    selectedEdge.is_contradiction
                      ? 'bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-300'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200'
                  }`}
                >
                  {selectedEdge.relationship_type.replace(/_/g, ' ')}
                </span>
                {selectedEdge.verification_status && (
                  <span className="text-[10px] text-zinc-500 dark:text-zinc-400">
                    • {selectedEdge.verification_status}
                  </span>
                )}
              </div>
              <button
                onClick={() => setSelectedEdge(null)}
                className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 p-1 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-4 flex-1 space-y-4">
              {selectedEdge.rationale && (
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                    Scientific Rationale
                  </label>
                  <p className="mt-1 text-xs text-zinc-800 dark:text-zinc-200 leading-relaxed bg-zinc-50 dark:bg-zinc-800/60 p-3 rounded-xl border border-zinc-200 dark:border-zinc-700">
                    {selectedEdge.rationale}
                  </p>
                </div>
              )}

              {selectedEdge.details && (
                <div className="space-y-2 pt-2 border-t border-zinc-200 dark:border-zinc-800 text-xs">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                    Compatibility Breakdown
                  </span>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="p-2 bg-zinc-50 dark:bg-zinc-800 rounded-lg">
                      <span className="text-zinc-400 block text-[10px]">Dataset</span>
                      <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                        {selectedEdge.details.dataset_or_population_compatibility || 'N/A'}
                      </span>
                    </div>
                    <div className="p-2 bg-zinc-50 dark:bg-zinc-800 rounded-lg">
                      <span className="text-zinc-400 block text-[10px]">Method</span>
                      <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                        {selectedEdge.details.methodology_compatibility || 'N/A'}
                      </span>
                    </div>
                  </div>

                  {selectedEdge.details.potential_explanations &&
                    selectedEdge.details.potential_explanations.length > 0 && (
                      <div className="mt-3">
                        <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">
                          Potential Explanations
                        </label>
                        <ul className="mt-1 list-disc list-inside text-[11px] text-zinc-700 dark:text-zinc-300 space-y-1">
                          {selectedEdge.details.potential_explanations.map((exp, idx) => (
                            <li key={idx}>{exp}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
