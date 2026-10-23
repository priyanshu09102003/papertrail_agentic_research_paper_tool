'use client';

import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  BookOpen,
  Sparkles,
  FileSearch,
  Database,
  Cpu,
  BarChart2,
  ExternalLink,
  CheckCircle2,
} from 'lucide-react';
import { ClaimGraphNodeData } from '@/types/claim-graph';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function PaperNode({ data, selected }: NodeProps & { data: ClaimGraphNodeData }) {
  const pdfLink = data.pdf_url ? (data.pdf_url.startsWith('http') ? data.pdf_url : `${API_BASE}${data.pdf_url}`) : null;

  return (
    <div
      className={`px-4 py-3 rounded-xl border-2 bg-white dark:bg-zinc-900 shadow-md transition-all duration-150 min-w-[240px] max-w-[280px] ${
        selected ? 'border-blue-600 ring-2 ring-blue-400/40 shadow-lg' : 'border-blue-200 dark:border-blue-900/60 hover:border-blue-400'
      }`}
    >
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-blue-600 !border-2 !border-white" />
      <div className="flex items-center gap-2 mb-1.5">
        <div className="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300">
          <BookOpen className="w-4 h-4" />
        </div>
        <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700 dark:text-blue-400">
          Paper
        </span>
        {pdfLink && (
          <a
            href={pdfLink}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            title="Open Original PDF"
            className="ml-auto text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
      <h4 className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 line-clamp-2 leading-snug">
        {data.title || data.label}
      </h4>
      {data.document_id && (
        <span className="mt-2 inline-block font-mono text-[10px] text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
          {data.document_id}
        </span>
      )}
    </div>
  );
}

export function ClaimNode({ data, selected }: NodeProps & { data: ClaimGraphNodeData }) {
  return (
    <div
      className={`px-4 py-3 rounded-xl border-2 bg-white dark:bg-zinc-900 shadow-md transition-all duration-150 min-w-[240px] max-w-[300px] ${
        selected ? 'border-purple-600 ring-2 ring-purple-400/40 shadow-lg' : 'border-purple-200 dark:border-purple-900/60 hover:border-purple-400'
      }`}
    >
      <Handle type="target" position={Position.Left} className="!w-3 !h-3 !bg-purple-600 !border-2 !border-white" />
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-purple-600 !border-2 !border-white" />
      <Handle type="source" position={Position.Bottom} id="bottom" className="!w-3 !h-3 !bg-purple-600 !border-2 !border-white" />
      <Handle type="target" position={Position.Top} id="top" className="!w-3 !h-3 !bg-purple-600 !border-2 !border-white" />

      <div className="flex items-center gap-2 mb-1.5">
        <div className="p-1.5 rounded-lg bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300">
          <Sparkles className="w-4 h-4" />
        </div>
        <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700 dark:text-purple-400">
          Scientific Claim
        </span>
      </div>
      <p className="text-xs text-zinc-800 dark:text-zinc-200 line-clamp-3 leading-relaxed font-medium">
        &ldquo;{data.title || data.label}&rdquo;
      </p>
      {data.paper_title && (
        <p className="mt-2 text-[10px] text-zinc-500 dark:text-zinc-400 truncate">
          From: <span className="italic">{data.paper_title}</span>
        </p>
      )}
    </div>
  );
}

export function EvidenceNode({ data, selected }: NodeProps & { data: ClaimGraphNodeData }) {
  const pdfPageLink = data.pdf_url
    ? data.pdf_url.startsWith('http')
      ? data.pdf_url
      : `${API_BASE}${data.pdf_url}`
    : null;

  return (
    <div
      className={`px-4 py-3 rounded-xl border-2 bg-emerald-50/40 dark:bg-emerald-950/20 shadow-md transition-all duration-150 min-w-[250px] max-w-[320px] ${
        selected ? 'border-emerald-600 ring-2 ring-emerald-400/40 shadow-lg' : 'border-emerald-300 dark:border-emerald-800/60 hover:border-emerald-500'
      }`}
    >
      <Handle type="target" position={Position.Left} className="!w-3 !h-3 !bg-emerald-600 !border-2 !border-white" />
      <div className="flex items-center gap-2 mb-1.5">
        <div className="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300">
          <FileSearch className="w-4 h-4" />
        </div>
        <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
          Evidence Passage
        </span>
        {data.page_number && (
          <span className="ml-auto inline-flex items-center gap-1 text-[11px] font-semibold bg-emerald-200/70 dark:bg-emerald-800/60 text-emerald-900 dark:text-emerald-200 px-2 py-0.5 rounded-full">
            <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            Page {data.page_number}
          </span>
        )}
      </div>
      <p className="text-xs text-zinc-700 dark:text-zinc-300 line-clamp-3 italic leading-relaxed bg-white/60 dark:bg-zinc-900/60 p-2 rounded-lg border border-emerald-100 dark:border-emerald-900/40">
        &ldquo;{data.quote || data.title || data.label}&rdquo;
      </p>
      <div className="mt-2 flex items-center justify-between text-[10px] text-emerald-800 dark:text-emerald-400 font-medium">
        <span>Verified source passage</span>
        {pdfPageLink && (
          <a
            href={pdfPageLink}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 hover:underline text-emerald-700 dark:text-emerald-300"
          >
            PDF Page {data.page_number || ''}
            <ExternalLink className="w-2.5 h-2.5" />
          </a>
        )}
      </div>
    </div>
  );
}

export function DatasetNode({ data, selected }: NodeProps & { data: ClaimGraphNodeData }) {
  return (
    <div
      className={`px-3.5 py-2.5 rounded-xl border-2 bg-amber-50/50 dark:bg-amber-950/20 shadow-sm transition-all duration-150 min-w-[180px] max-w-[240px] ${
        selected ? 'border-amber-600 ring-2 ring-amber-400/40' : 'border-amber-300 dark:border-amber-800 hover:border-amber-500'
      }`}
    >
      <Handle type="target" position={Position.Left} className="!w-2.5 !h-2.5 !bg-amber-600 !border-2 !border-white" />
      <div className="flex items-center gap-2">
        <div className="p-1 rounded-md bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300">
          <Database className="w-3.5 h-3.5" />
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-amber-800 dark:text-amber-400">
            Dataset
          </span>
          <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 truncate">
            {data.title || data.label}
          </p>
        </div>
      </div>
    </div>
  );
}

export function MethodNode({ data, selected }: NodeProps & { data: ClaimGraphNodeData }) {
  return (
    <div
      className={`px-3.5 py-2.5 rounded-xl border-2 bg-cyan-50/50 dark:bg-cyan-950/20 shadow-sm transition-all duration-150 min-w-[180px] max-w-[240px] ${
        selected ? 'border-cyan-600 ring-2 ring-cyan-400/40' : 'border-cyan-300 dark:border-cyan-800 hover:border-cyan-500'
      }`}
    >
      <Handle type="target" position={Position.Left} className="!w-2.5 !h-2.5 !bg-cyan-600 !border-2 !border-white" />
      <div className="flex items-center gap-2">
        <div className="p-1 rounded-md bg-cyan-100 dark:bg-cyan-900 text-cyan-700 dark:text-cyan-300">
          <Cpu className="w-3.5 h-3.5" />
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-800 dark:text-cyan-400">
            Methodology
          </span>
          <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 line-clamp-2">
            {data.title || data.label}
          </p>
        </div>
      </div>
    </div>
  );
}

export function MetricNode({ data, selected }: NodeProps & { data: ClaimGraphNodeData }) {
  return (
    <div
      className={`px-3.5 py-2.5 rounded-xl border-2 bg-slate-50 dark:bg-slate-900 shadow-sm transition-all duration-150 min-w-[170px] max-w-[220px] ${
        selected ? 'border-indigo-600 ring-2 ring-indigo-400/40' : 'border-slate-300 dark:border-slate-700 hover:border-slate-500'
      }`}
    >
      <Handle type="target" position={Position.Left} className="!w-2.5 !h-2.5 !bg-indigo-600 !border-2 !border-white" />
      <div className="flex items-center gap-2">
        <div className="p-1 rounded-md bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
          <BarChart2 className="w-3.5 h-3.5" />
        </div>
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-800 dark:text-indigo-400">
            Evaluation Metric
          </span>
          <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 truncate">
            {data.title || data.label}
          </p>
        </div>
      </div>
    </div>
  );
}
