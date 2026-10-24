# PaperTrail Frontend

A high-performance scientific integrity and literature synthesis portal built with **Next.js 16 (Turbopack)**, **React 19**, **TypeScript**, **Tailwind CSS v4**, and **@xyflow/react**.

PaperTrail provides an interactive workspace for researchers to formulate hypotheses, discover scholarly literature, inspect structured claim extractions, monitor multi-agent LangGraph workflow execution, analyze empirical tensions and contradictions, and navigate an interactive claim-to-evidence graph.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │        PaperTrail Web Portal         │
                      │    (Next.js 16 + React 19 + TS)      │
                      └──────────────────┬───────────────────┘
                                         │  HTTP / JSON REST API
                                         ▼
                      ┌──────────────────────────────────────┐
                      │       PaperTrail FastAPI Backend     │
                      │         (Uvicorn on Port 8000)       │
                      └──────────┬─────────────────┬─────────┘
                                 │                 │
                ┌────────────────┴────────┐   ┌────┴────────────────────┐
                │ LangGraph Orchestration │   │ SQLite Database Engine  │
                │  - Claim Extraction     │   │  - Projects & Papers    │
                │  - Conflict Analysis    │   │  - Document Page Text   │
                │  - Evidence Verification│   │  - Claims & Relations   │
                │  - Report Synthesis     │   │  - Analysis Checkpoints │
                └─────────────────────────┘   └─────────────────────────┘
```

The frontend acts as a reactive presentation and interaction layer. It never directly modifies raw database records or triggers unbound model execution; all scientific parsing, evidence auditing, and LangGraph pipeline state transitions are executed deterministically on the backend.

---

## Screen Architecture & Workflow

PaperTrail guides researchers through a six-stage scientific review lifecycle:

```
  Dashboard ───► New Research ───► Literature Discovery ───► Paper Library
                                                                  │
      ┌───────────────────────────────────────────────────────────┘
      ▼
  Analysis Workspace ───► Comparison Explorer ───► Evidence Graph ───► Research Report
```

### 1. Dashboard (`DashboardScreen.tsx`)
- **Key Metrics**: Displays total project count, papers analyzed, active pipeline runs, and empirical contradictions detected.
- **Synchronized Fixed-Height Panels**: Side-by-side matching panels for *Recent Research Projects* and *Potential Contradictions* with seamless, borderless scrolling.
- **Instant Synthesis Overlay**: Clicking any project title immediately displays the full research report in a high-contrast modal (`ProjectReportModal.tsx`) with copy-to-clipboard functionality.

### 2. New Research (`NewResearchScreen.tsx`)
- **Hypothesis Formulation**: Researchers enter core inquiry questions (e.g., *"Compare CNNs and Vision Transformers for plant disease detection"*).
- **Scope Configuration**: Configures publication year ranges, candidate limits, and LLM extraction providers (**Auto**, **Google Gemini**, or **Local Ollama**).
- **Elevated Form UI**: High-prominence surface with distinct themed borders, dark inset inputs (`.portal-input`), and focused glow effects.

### 3. Literature Discovery (`DiscoveryScreen.tsx`)
- **Multi-Source Scholarly Search**: Queries open scholarly databases (OpenAlex, Crossref) via backend proxies.
- **Corpus Curation**: Batch selection controls (*Select All*, *Deselect All*) to add candidate papers directly to the active project.
- **Direct PDF Ingestion**: File drop-zone allowing direct research PDF uploads with automated binary validation and text extraction.

### 4. Paper Library (`PaperLibraryScreen.tsx`)
- **Project Corpus Manager**: Lists all scholarly papers and uploaded PDF documents bound to the active project.
- **Metadata Inspection**: Displays DOIs, authors, publication years, page counts, character counts, and open-access links.
- **Workspace Launchpad**: Verifies minimum paper count requirements before unlocking multi-paper comparative analysis.

### 5. Analysis Workspace (`AnalysisWorkspaceScreen.tsx`)
- **Real-Time LangGraph Monitor**: Tracks the 7 orchestrated workflow stages:
  1. *Paper Discovery & Project Validation*
  2. *PDF Document Ingestion*
  3. *Scientific Methodology & Claim Extraction*
  4. *Extraction Result Validation*
  5. *Cross-Paper Comparison & Contradiction Analysis*
  6. *Evidence Passage Verification*
  7. *Report Synthesis & Persistence*
- **Live Progress Bar**: Progress percentage derived directly from backend graph state (no artificial decorative timers).
- **Diagnostic Inspection**: Displays bounded retry counts, step histories, error diagnostics, and node execution status.

### 6. Comparison Explorer (`ComparisonExplorerScreen.tsx`)
- **Side-by-Side Methodology Alignment**: Compares research questions, methodologies, datasets, and quantitative metrics.
- **Classified Claim Relationships**: Categorizes findings into validated relationship types:
  - `potential_contradiction`: Divergent results under comparable methodologies.
  - `agreement`: Independent empirical consensus.
  - `conditional_difference`: Variances attributable to different conditions or datasets.
  - `extension`: Novel additions or refinements to prior work.
- **Audited Evidence Quotes**: Source passages and page numbers verifying that claims are grounded in document text.

### 7. Interactive Evidence Graph (`ClaimGraphScreen.tsx` & `ClaimGraphViewer.tsx`)
- **React Flow Visualization**: Directed node-edge graph mapping connections between papers, claims, evidence passages, datasets, and methods.
- **Custom Visual Nodes**: Distinct custom node types with specialized badges, colors, and metadata tooltips (`CustomNodes.tsx`).
- **Interactive Details Drawer**: Clicking any node or edge displays source papers, verbatim evidence passages, confidence scores, and PDF viewing links.

### 8. Research Report (`ResearchReportScreen.tsx`)
- **Structured Synthesis Document**: Executive summaries, reviewed papers, comparative analyses, conflict reconciliations, and limitations.
- **Markdown Export**: One-click formatted export to clipboard for literature review drafts.

---

## Project & Directory Structure

```
frontend/
├── package.json                      # Project dependencies & npm scripts
├── tsconfig.json                     # TypeScript compiler configuration
├── next.config.ts                    # Next.js 16 configuration (Turbopack)
├── eslint.config.mjs                 # ESLint flat config
├── public/                           # Static assets
└── src/
    ├── app/
    │   ├── globals.css               # Design system, card prominence, invisible scrollbars
    │   ├── layout.tsx                # Root layout with Geist font definition & metadata
    │   └── page.tsx                  # Top-level screen router & background ambient effects
    │
    ├── components/
    │   ├── Navbar.tsx                # Sticky navbar, screen ladder, project switcher & LLM status
    │   ├── BrandLoader.tsx           # Logo animation & glow reveal on initial page load
    │   ├── DashboardScreen.tsx       # System overview, metric cards & synchronized panels
    │   ├── NewResearchScreen.tsx     # Research hypothesis setup with high-contrast form
    │   ├── DiscoveryScreen.tsx       # OpenAlex/Crossref literature discovery & PDF ingestion
    │   ├── PaperLibraryScreen.tsx    # Curated project paper library & document catalog
    │   ├── AnalysisWorkspaceScreen.tsx # Live LangGraph pipeline tracker & diagnostic monitor
    │   ├── ComparisonExplorerScreen.tsx # Cross-paper comparison table & contradiction audit
    │   ├── ClaimGraphScreen.tsx      # Claim-to-evidence graph screen container & filters
    │   ├── ClaimGraphViewer.tsx      # React Flow interactive canvas & inspector drawer
    │   ├── ProjectReportModal.tsx    # Modal overlay displaying the complete research report
    │   ├── ResearchReportScreen.tsx  # Full-screen research synthesis report
    │   └── nodes/
    │       └── CustomNodes.tsx       # Custom React Flow nodes (Paper, Claim, Evidence, etc.)
    │
    ├── services/
    │   └── api.ts                    # Centralized, typed REST API client interfacing with FastAPI
    │
    └── types/
        ├── papertrail.ts             # Domain models (Paper, Claim, Relationship, Report, Analysis)
        ├── claim-graph.ts            # Graph node, edge, filter, and detail panel interfaces
        └── declarations.d.ts         # Global TypeScript environment declarations
```

---

## Backend Connectivity & Data Contracts

The frontend communicates with the FastAPI backend through the centralized client in [src/services/api.ts](file:///c:/Users/priya/Desktop/papertrail/frontend/src/services/api.ts).

### Environment Configuration
The backend URL is resolved through `NEXT_PUBLIC_API_URL` with a sensible local default:

```env
# .env.local (optional, defaults to http://localhost:8000)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Key API Endpoints Consumed

| Endpoint | Method | Purpose |
|:---|:---:|:---|
| `/api/projects` | `GET` / `POST` | List all persisted projects or create a new research scope |
| `/api/projects/{id}` | `GET` / `DELETE` | Retrieve project details or delete with cascading cleanup |
| `/api/papers/search` | `GET` | Query OpenAlex and Crossref for open-access papers |
| `/api/projects/{id}/papers` | `GET` / `POST` | Manage paper associations for a research project |
| `/api/projects/{id}/documents` | `GET` / `POST` | Upload and list validated research PDFs |
| `/api/documents/{id}/file` | `GET` | Stream raw PDF binary for in-browser inspection |
| `/api/projects/{id}/analysis` | `POST` / `GET` | Trigger or monitor LangGraph workflow progress |
| `/api/projects/{id}/relationships`| `GET` | Retrieve evaluated cross-paper claim relationships |
| `/api/projects/{id}/claim-graph` | `GET` | Fetch structured node-and-edge claim graph data |
| `/api/llm/status` | `GET` | Check inference provider availability (Gemini / Ollama) |

### Resilient Error Handling
All API methods in `api.ts` feature fault-tolerant wrappers:
- **Connection Loss**: Network dropouts or backend reloads are caught gracefully, providing fallback states rather than throwing unhandled runtime exceptions.
- **Structured Error Parsing**: Backend validation errors (FastAPI `422` or custom `4xx`/`5xx` error payloads) are parsed and displayed cleanly in UI banners.

---

## Design System & Styling Philosophy

The UI is built on a dark, scientific workstation aesthetic defined in [src/app/globals.css](file:///c:/Users/priya/Desktop/papertrail/frontend/src/app/globals.css):

- **High-Prominence Cards (`.portal-card`)**: Built with dark linear gradients (`#13151b` to `#0d0f14`), 1px translucent borders with top highlight strokes, and multi-layer drop shadows (`rgba(0, 0, 0, 0.85)`).
- **Form Elevation (`.portal-form-container`)**: Enhanced form containers featuring violet-tinted accent borders (`rgba(113, 112, 255, 0.28)`) and ambient glow shadows.
- **Deep Inset Fields (`.portal-input`)**: Custom input and textarea styling with `#0a0b0f` backgrounds, subtle inset shadows, and glowing focus rings.
- **Universal Clean Scrollbars**: Browser scrollbar rails and thumbs are suppressed project-wide (`scrollbar-width: none`, `-ms-overflow-style: none`, `::-webkit-scrollbar { display: none }`), preserving clean card boundaries while retaining full native trackpad and wheel scrollability.
- **Universal Interactive Cursors**: Enforces `cursor: pointer` on all buttons, interactive elements, selects, and summary toggles.
- **Ambient Lighting**: Subtle background radial gradients and a 24px scientific dot-matrix grid (`.bg-portal-grid`) provide visual depth without distraction.

---

## Getting Started

### Prerequisites
- **Node.js**: v18.17.0 or higher (v20+ recommended)
- **Backend Service**: Ensure the PaperTrail FastAPI backend is running on `http://localhost:8000`

### Installation

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install
```

### Development Server

```bash
# Start Next.js development server with Turbopack
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
# Typecheck and compile production bundle
npm run build

# Start production server
npm start
```

### Code Quality

```bash
# Run ESLint checks
npm run lint

# Run TypeScript typecheck without emitting files
npx tsc --noEmit
```

---

## Scientific Integrity Guidelines Enforced by the UI

1. **Grounded Quotes**: Every claim displayed in comparison cards and graph nodes explicitly references verified document text and page numbers.
2. **Conservative Contradictions**: Differences in numbers are never displayed as contradictions unless experimental conditions, datasets, and evaluation metrics are comparable.
3. **Transparent Provenance**: External papers link to official DOIs and open-access PDF sources whenever available.
4. **No Decorative Progress**: Pipeline progress bars correspond directly to validated LangGraph node checkpoints persisted in SQLite.
