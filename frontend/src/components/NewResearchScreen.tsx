'use client';

import React, { useState } from 'react';
import {
  Sparkles,
  ArrowRight,
  Search,
  Calendar,
  Layers,
  Cpu,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import { api } from '@/services/api';
import { ScreenId } from './Navbar';

interface NewResearchScreenProps {
  onNavigate: (screen: ScreenId, projectId?: string, initialSearchParams?: {
    query: string;
    fromYear?: number;
    toYear?: number;
    limit?: number;
  }) => void;
  onProjectCreated: (projectId: string) => void;
}

export function NewResearchScreen({
  onNavigate,
  onProjectCreated,
}: NewResearchScreenProps) {
  const currentYear = new Date().getFullYear();

  const [projectName, setProjectName] = useState('');
  const [researchQuestion, setResearchQuestion] = useState(
    'Compare CNNs and Vision Transformers for plant disease detection.'
  );
  const [description, setDescription] = useState('');
  const [fromYear, setFromYear] = useState<number>(2018);
  const [toYear, setToYear] = useState<number>(currentYear);
  const [limit, setLimit] = useState<number>(10);
  const [provider, setProvider] = useState<'auto' | 'gemini' | 'ollama'>('auto');

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanTitle = projectName.trim() || researchQuestion.trim();
    if (!cleanTitle) {
      setErrorMessage('Please enter a research project title or research question.');
      return;
    }
    if (fromYear > toYear) {
      setErrorMessage('The starting publication year must be earlier than or equal to the ending year.');
      return;
    }

    setLoading(true);
    try {
      const descPayload = description.trim()
        ? `${description.trim()}\n\nResearch Question: ${researchQuestion.trim()}`
        : `Research Question: ${researchQuestion.trim()}`;

      const created = await api.createProject(cleanTitle, descPayload);
      onProjectCreated(created.id);

      // Transition straight into Discovery Screen with pre-configured search query and filters
      onNavigate('discovery', created.id, {
        query: researchQuestion.trim(),
        fromYear,
        toYear,
        limit,
      });
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to create research project.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-6 space-y-8 animate-fadeIn">
      {/* Title */}
      <div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#7170ff]/10 text-[#7170ff] text-xs font-semibold mb-3">
          <Sparkles className="w-3.5 h-3.5" />
          Initiate New Research Study
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-[#f7f8f8]">
          Configure Research Project & Literature Scope
        </h1>
        <p className="text-sm text-[#8b8f98] mt-1">
          Specify your core scientific inquiry. PaperTrail will search open-access scholarly databases and build your comparative evidence matrix.
        </p>
      </div>

      {/* Form Card */}
      <form
        onSubmit={handleSubmit}
        className="portal-form-container rounded-2xl p-6 sm:p-8 space-y-6"
      >
        {errorMessage && (
          <div className="flex items-center gap-2.5 p-3.5 rounded-lg bg-[#ff5b5b]/10 border border-[#ff5b5b]/30 text-[#ff5b5b] text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Research Question */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-wider text-[#f7f8f8]">
            Research Question / Hypothesis <span className="text-[#ff5b5b]">*</span>
          </label>
          <textarea
            rows={3}
            value={researchQuestion}
            onChange={(e) => setResearchQuestion(e.target.value)}
            placeholder="e.g., Compare CNNs and Vision Transformers for plant disease detection."
            className="w-full text-sm portal-input rounded-xl p-3.5 text-[#f7f8f8] placeholder-[#8b8f98]/50 focus:outline-none transition-all"
            required
          />
          <p className="text-[11px] text-[#8b8f98]">
            This question will guide the initial discovery search across OpenAlex and Crossref.
          </p>
        </div>

        {/* Project Name */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-wider text-[#f7f8f8]">
            Project Name (Optional)
          </label>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="e.g., Plant Disease Vision Transformers Benchmark"
            className="w-full text-sm portal-input rounded-xl p-3 text-[#f7f8f8] placeholder-[#8b8f98]/50 focus:outline-none transition-all"
          />
        </div>

        {/* Publication Year Range & Max Results */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-2">
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b8f98] flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-[#7170ff]" />
              From Year
            </label>
            <input
              type="number"
              min={1950}
              max={currentYear}
              value={fromYear}
              onChange={(e) => setFromYear(parseInt(e.target.value) || 2018)}
              className="w-full text-sm portal-input rounded-xl p-3 text-[#f7f8f8] focus:outline-none"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b8f98] flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-[#7170ff]" />
              To Year
            </label>
            <input
              type="number"
              min={1950}
              max={currentYear}
              value={toYear}
              onChange={(e) => setToYear(parseInt(e.target.value) || currentYear)}
              className="w-full text-sm portal-input rounded-xl p-3 text-[#f7f8f8] focus:outline-none"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b8f98] flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-[#7170ff]" />
              Max Papers
            </label>
            <select
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value))}
              className="w-full text-sm portal-input rounded-xl p-3 text-[#f7f8f8] focus:outline-none cursor-pointer"
            >
              <option value={5} className="bg-[#0c0d12] text-[#f7f8f8]">5 Papers</option>
              <option value={10} className="bg-[#0c0d12] text-[#f7f8f8]">10 Papers</option>
              <option value={20} className="bg-[#0c0d12] text-[#f7f8f8]">20 Papers</option>
              <option value={30} className="bg-[#0c0d12] text-[#f7f8f8]">30 Papers</option>
            </select>
          </div>
        </div>

        {/* LLM Provider Selection */}
        <div className="space-y-2.5 pt-3 border-t border-white/[0.08]">
          <label className="block text-xs font-semibold uppercase tracking-wider text-[#8b8f98] flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-[#7170ff]" />
            Extraction Model Provider
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              {
                id: 'auto',
                label: 'Auto (Recommended)',
                desc: 'Gemini if API key configured, otherwise Ollama fallback.',
              },
              {
                id: 'gemini',
                label: 'Google Gemini',
                desc: 'Fast cloud extraction with structured JSON schemas.',
              },
              {
                id: 'ollama',
                label: 'Local Ollama',
                desc: '100% private local inference (qwen2.5:1.5b).',
              },
            ].map((opt) => (
              <label
                key={opt.id}
                onClick={() => setProvider(opt.id as 'auto' | 'gemini' | 'ollama')}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  provider === opt.id
                    ? 'border-[#7170ff] bg-[#7170ff]/15 text-[#f7f8f8] shadow-[0_0_20px_rgba(113,112,255,0.2)]'
                    : 'border-white/[0.1] bg-[#0c0d12]/80 text-[#8b8f98] hover:border-white/[0.22] hover:bg-[#12141c]'
                }`}
              >
                <div className="text-xs font-semibold text-[#f7f8f8]">{opt.label}</div>
                <div className="text-[10px] text-[#8b8f98] mt-1.5 leading-snug">{opt.desc}</div>
              </label>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="pt-4 flex items-center justify-between border-t border-white/[0.08]">
          <button
            type="button"
            onClick={() => onNavigate('dashboard')}
            className="px-4 py-2 text-xs font-medium text-[#8b8f98] hover:text-[#f7f8f8] transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-gradient-to-r from-[#7170ff] to-[#5856d6] hover:from-[#8281ff] hover:to-[#6a68e6] disabled:opacity-50 text-white text-xs font-semibold transition-all shadow-[0_4px_20px_rgba(113,112,255,0.35)] cursor-pointer"
          >
            {loading ? 'Creating Project...' : 'Start Discovery'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
