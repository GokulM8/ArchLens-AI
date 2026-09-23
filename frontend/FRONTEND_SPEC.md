# ArchLens AI — Frontend Specification & Backend Contract

Everything the frontend does today, every field it consumes, and exactly what a backend
must return for it to keep working without UI changes.

- Stack: TanStack Start (v1) + React 19 + TypeScript + Tailwind v4, Vite 7.
- Current data source: **all analysis happens in the browser.** No backend, no LLM, no GitHub API.
- Single integration seam: `src/services/api.ts`. Replacing the bodies of those functions with
  HTTP calls is the entire backend migration — no component changes required.

---

## 1. Routes (pages)

| Route | File | Purpose | Data source |
|---|---|---|---|
| `/` | `src/routes/index.tsx` | Landing page: Hero → Pipeline → AnalysisConsole → ArchitectureExplorer → AIExplanation → HealthDashboard → ArchitectureDiff → Technologies → FinalCTA | mock payloads |
| `/analyze` | `src/routes/analyze.tsx` | 3-phase flow: `input` → `progress` → `result` | real upload or mock |
| `/architecture` | `src/routes/architecture.tsx` | Sample system map + explorer, explanation, health, diff | mock payloads |
| `/document` | `src/routes/document.tsx` | Standalone written architecture document (Poppins, print/PDF) | current session, else mock |
| `/privacy`, `/terms` | `src/routes/privacy.tsx`, `terms.tsx` | Static legal pages | none |

Every route defines its own `head()` with title, description, `og:title`, `og:description`
(`/document` also sets `og:type` and `twitter:card`). Root layout: `src/routes/__root.tsx`
(Navbar, Footer, skip-link, Google Fonts, favicon).

No route uses loaders or server functions. Nothing is server-rendered from data — the whole
analysis result lives in client memory.

---

## 2. The single integration seam — `src/services/api.ts`

```ts
export interface AnalysisRequest {
  source: string;            // GitHub URL, or the uploaded archive's filename
  kind: "git" | "zip";
  file?: File | null;        // present only for kind === "zip"
}

export interface AnalysisResult {
  summary: AnalysisSummary;
  graph: ArchitectureGraphData;
  health: ArchitectureHealth;
  explanation: AIExplanation;
  aiSummary: string[];       // 3–5 paragraphs of prose
}
```

Exported functions the UI calls:

| Function | Signature | Today | Backend replacement |
|---|---|---|---|
| `analyzeRepository` | `(req: AnalysisRequest) => Promise<AnalysisResult>` | ZIP → real in-browser analysis; git URL → mock after 300 ms | `POST /v1/analyses` (multipart for ZIP, JSON for URL) returning `AnalysisResult` |
| `getArchitectureGraph` | `() => Promise<ArchitectureGraphData>` | returns `mockGraph` | `GET /v1/analyses/:id/graph` |
| `getArchitectureHealth` | `() => Promise<ArchitectureHealth>` | returns `mockHealth` | `GET /v1/analyses/:id/health` |
| `getArchitectureDiff` | `() => Promise<ArchitectureDiffData>` | returns `mockDiff` | `GET /v1/analyses/:id/diff?from=&to=` |
| `getAnalysisStages` | `() => AnalysisStage[]` (sync) | static stage list | may stay static, or stream real progress |

Side effect to preserve: on success `analyzeRepository` calls `setRepoSession({repository, result, index, real, analyzedAt})`; on the mock path it calls `setRepoSession(null)`.

---

## 3. Data contract (`src/types/architecture.ts`)

Field names and types must match exactly; optional fields are genuinely optional and the UI
falls back safely when absent.

### ArchitectureNode
```ts
type ArchitectureNodeType =
  "client" | "gateway" | "service" | "module" | "model" | "datastore" | "cache" | "external";

interface ArchitectureNode {
  id: string;                              // unique, referenced by edges
  type: ArchitectureNodeType;              // drives icon, colour tier, layer
  label: string;                           // display name
  description?: string;
  confidence?: number;                     // 0..1 → rendered as a percentage bar
  position?: { x: number; y: number };     // layout hint; omit and layers are used
  layer?: number;                          // column index for the blueprint layout
  metadata?: {
    dependencies?: string[];               // outgoing file paths / names
    consumers?: string[];                  // incoming users, or API consumers
    sourcePath?: string;                   // representative file
    lines?: [number, number];              // inclusive line range
    dependencyCount?: number;
    consumerCount?: number;
    snippet?: string;                      // real source excerpt (≈14 lines)
    snippetLanguage?: string;              // "python" | "tsx" | "yaml" | ...
    snippetStart?: number;                 // 1-based first line of the excerpt
    snippetSignals?: string[];             // "what ArchLens read here" bullets
    [key: string]: unknown;                // extras used today: fileCount, routeCount, groupPath
  };
}
```

### ArchitectureEdge
```ts
interface ArchitectureEdge {
  id: string;
  source: string;   // node id
  target: string;   // node id
  type: "imports" | "calls" | "reads" | "writes" | "queries";
  confidence?: number;   // 0..1
  label?: string;        // e.g. "7 imports"
}
```
Edge type affects rendering: `reads`/`writes`/`queries` draw dashed, others solid; `calls`
edges animate. In the report, types map to verbs: imports / calls over HTTP / reads from /
writes to / queries.

### AnalysisSummary
```ts
{ repository: string; branch: string; filesScanned: number; modules: number;
  apiRoutes: number; externalServices: number; circularDependencies: number;
  languages: { name: string; share: number }[] }   // share is 0..1, rendered as %
```

### ArchitectureHealth
```ts
{ score: number;            // 0..100
  grade: string;            // "A" | "B+" | "B" | "C" | "D"
  strengths: string[]; warnings: string[];
  metrics: { key: string; label: string; value: number; score: number; unit?: string; hint?: string }[] }
```
`value` is the raw figure shown next to `unit`; `score` (0..100) drives the bar width.

### AIExplanation
```ts
{ nodeId: string; question: string; verdict: string; evidence: string[]; confidence: number }
```
`verdict` is typewritten on scroll-into-view; `evidence` rows reveal sequentially.

### ArchitectureDiffData
```ts
{ versionA: { label: string; graph: ArchitectureGraphData };
  versionB: { label: string; graph: ArchitectureGraphData };
  changes: { kind: "added" | "modified" | "removed"; label: string; detail: string }[] }
```

### AnalysisStage
```ts
{ id: string; label: string; detail?: string }
```

---

## 4. Client-side analysis pipeline (what a backend must reproduce)

### 4.1 Ingest — `src/lib/repoIngest.ts`
- Unzips with `fflate` in the browser; nothing is executed, nothing is uploaded.
- Limits: **max 4000 files**, **max 240 000 bytes per file**.
- Ignored path segments: `node_modules, .git, dist, build, .next, .venv, venv, __pycache__, .turbo, coverage, .cache, vendor`.
- Text-only: extension → language map (ts, tsx, js, jsx, mjs, cjs, py, rb, go, rs, java, kt, php, cs, c, h, cpp, hpp, swift, sql, sh, yml/yaml, json, toml, css, scss, html, md, txt, env, dockerfile). Dotfiles allowed only for `.env/.gitignore/.dockerignore/.editorconfig`; extensionless allowed for Dockerfile/Makefile/Procfile.
- Skips files containing a NUL byte (binary heuristic).
- Strips a single shared archive root folder (`repo-main/`).
- Repository name = shared root folder, else the filename minus `.zip`.
- Output per file: `{ path, name, ext, language, content, lines, bytes }` plus a `skipped` count.
- Errors thrown (shown as UI alerts): "The archive contains no files.", "No readable source files were found in the archive."

### 4.2 Static analysis — `src/lib/repoAnalysis.ts`
Import parsing by regex, per language: JS/TS (`import … from`, `require()`), Python (`import`, `from … import`), Go (import block strings). Resolution tries relative paths, `@/` and `~/` aliases (→ `src/…`, `…`, `app/…`), dotted Python modules, and extensions `"" .ts .tsx .js .jsx .mjs .py .go .rb .java /index.* /__init__.py`. Unresolved specifiers become externals (scoped packages keep `@scope/name`).

Per-file index (`IndexedFile`): `path, language, lines, bytes, content, imports[], externals[], usedBy[], componentId, symbols[]` (up to 40 top-level `function|class|def|const|interface|type|func` names).

Components: files grouped by first path segment (or `src/<second>`), ranked by file count, **top 10 kept**; the rest go to component id `other`. Type inference by directory-name rules (client / gateway / service / model / datastore / cache / external), then by content heuristics (`@app.get`, `express(`, `createRoot`, `CREATE TABLE`, …), default `module`.

Derived per component: representative file (highest `usedBy*3 + lines`), cross-component dependencies and consumers (max 8 listed, full counts kept), route-handler count, external packages, a 14-line snippet anchored on the first definition line, and inference signals.

**Confidence** = `min(0.99, 0.62 + min(0.2, files/40) + (routes>0 ? 0.1 : 0) + (consumers ? 0.07 : 0))`, rounded to 2 dp.

**Layout**: nodes bucketed by type order `client, gateway, service, module, model, cache, datastore, external`; `x = column * 260`, rows spread vertically around centre.

**Edges**: aggregated cross-component file imports, weight = import count, **top 26**; type = `queries` if target is a datastore, `reads` if cache, `calls` if service, else `imports`; `confidence = min(0.99, 0.7 + weight/30)`; label = "N imports".

**Summary**: `branch` is hardcoded `"uploaded"`; `modules` = total groups; `apiRoutes` = regex count of `@app/@router/@api .get|post|put|patch|delete`, `app/router.<verb>(`, `@Get/Post/Put/DeleteMapping`; `externalServices` = distinct external packages; `languages` = share of bytes excluding text/markdown/json, top 6.

**Circular dependencies**: DFS back-edge count over the file import graph (a cheap cycle proxy, not distinct cycles).

**Health metrics** (all clamped 0–100):
| key | label | value | score formula |
|---|---|---|---|
| `modularity` | Modularity | node count | `60 + nodes*4 − coupling*12` |
| `coupling` | Coupling | edges/components (2 dp) | `100 − coupling*22` |
| `cycles` | Cycle freedom | cycle count | `100 − cycles*12` |
| `size` | File size discipline | avg lines | `110 − avgLines/4 − bigFiles*2` |
| `reach` | Connectedness | isolated files | `100 − (orphans/files)*160` |

`score` = mean of the five; grade thresholds `≥90 A, ≥80 B+, ≥70 B, ≥60 C, else D`.
Strengths/warnings are generated from cycles, files >400 lines, coupling <2, orphans, routes found.

**Explanation**: focuses the component with the highest `consumerCount + dependencyCount`;
`evidence` reuses its snippet signals. **aiSummary**: 4 generated paragraphs (scale, languages
+ routes, third-party surface, score + top warning). No LLM is involved.

Returned `RepoIndex`: `{ repository, files: Record<path, IndexedFile>, paths[], componentFiles: Record<componentId, path[]>, externals: {name, count}[] }`.

### 4.3 Session state — `src/lib/repoStore.ts`, `src/lib/useAnalysis.ts`
- In-memory only (`useSyncExternalStore`). **No localStorage, no cookies, no persistence** — a page reload loses the analysis.
- `RepoSession = { repository, result, index, real, analyzedAt }`.
- `getFileContent(path)` returns whole real file text for the source viewer.
- `useAnalysis()` returns the uploaded session if present, otherwise the mock payloads, with a `real` flag the UI uses to show "Showing the sample repository".

---

## 5. Features screen by screen

### Landing (`/`)
- **Hero + HeroGraph** — blueprint node canvas: Frontend → API branching to Auth/Users/Prediction converging on Database. Ports, types, confidence bars, dependency counts, curved solid links, dashed data links, travelling pulses, hover tracing, node inspector, dotted grid, "Inference active" status, reduced-motion aware.
- **Pipeline** — the 8-step concept flow (Repository → Static analysis → Dependency graph → Architecture inference → AI explanation → Visualization → Health → Diff).
- **AnalysisConsole** — animated staged log built from `getAnalysisStages()`.
- **ArchitectureExplorer** — `ArchitectureGraph` + `NodeInspector` side by side; `withHeading` prop.
- **AIExplanation** — typewriter verdict, blinking caret, sequential evidence, accessible full-text `aria-label`.
- **HealthDashboard** — score, grade, five metric bars, strengths and warnings; `compact` prop.
- **ArchitectureDiff** — version A/B mini graphs plus added/modified/removed change list.
- **Technologies**, **FinalCTA**, **Navbar** (anchor + route links), **Footer**.

### Analyze (`/analyze`)
1. **Input** (`RepositoryInput`) — ZIP drag-and-drop, file picker, `.zip` validation, GitHub URL field with `https://…/…` validation, Enter-to-submit, `aria-invalid`/`aria-describedby` errors. Note shown: pasted URLs load the sample.
2. **Progress** (`AnalysisProgress`) — staged animation; the result is only shown once both the stage animation and the analysis promise complete.
3. **Result** (`ResultDashboard`) — repository header, branch, circular-dependency count, four stats (files, modules, api routes, external services), graph + inspector, health, AI summary, buttons: **Full report · document / PDF**, **Architecture document** (`/document`), **New analysis**.

Errors from ingest surface as a `role="alert"` banner and return to the input phase.

### Graph components
- `ArchitectureGraph` / `ArchitectureCanvas` — custom SVG blueprint canvas: normalized layout, curved gradient links, arrow markers, animated `calls` edges, hover hit areas, travelling pulses, typed compact cards with confidence and dependency counts, selected / linked / dimmed states.
- **Zoom controls**: −/+ buttons, live percentage, reset, clamped **50%–220%**.
- **Full view**: fullscreen dialog with Escape/close, body-scroll lock, accessible labels.
- `MiniGraph` — compact variant for the diff section.

### Node inspection & source
- `NodeInspector` — type badge, purpose, dependencies, API consumers, confidence bar, source path and line range, `CodeSnippet`, **View Source** (disabled without a snippet).
- `CodeSnippet` — path/language header, line numbers, inference signals.
- `SourceViewer` — full-window dialog: excerpt ↔ **whole file** toggle (real uploads only), line numbers, copy to clipboard with confirmation, language + line range, "What ArchLens read here" signals, Escape close, scroll lock, `role="dialog" aria-modal`.

### Report / document
- `src/lib/reportContent.ts` → `buildRepositoryReport(result)` produces `RepositoryReport`:
  `title, branch, generatedAt (YYYY-MM-DD), overview[], facts[8], languages[], components[], connections[], health{...}, evidence{...}`.
  Each `ReportComponent`: `id, name, kind, purpose, what, sourcePath, lines, confidence, dependencies[], consumers[], usedIn[], snippet?, snippetStart?, snippetSignals?`.
  `usedIn` is generated from incoming/outgoing edges as readable sentences.
- `ReportDocument` — Poppins typeset, overlay or `standalone` mode, print-to-PDF via the browser dialog, `.no-print` chrome, per-component purpose + code + why it exists.

---

## 6. Design system
- Tokens only, all `oklch`, defined in `src/styles.css` and exposed as Tailwind semantic
  utilities: background `0.16 0.008 250`, surface `0.194`, surface-raised `0.228`, foreground
  `0.965`, muted-foreground `0.66`, subtle `0.5`, accent/primary signal jade `0.84 0.155 168`,
  accent-dim `/0.28`, warning `0.82 0.14 78`, destructive `0.64 0.19 22`, borders
  `white/0.08` and `white/0.16`, input `white/0.12`, ring jade `/0.6`. Radius `0.375rem`.
  Shadows: `--shadow-panel`, `--shadow-glow`.
- Fonts (loaded via `<link>` in `__root.tsx`): Bricolage Grotesque (display), Instrument Sans
  (body), JetBrains Mono (mono), Space Grotesk + DM Mono (blueprint), Poppins (report/PDF).
- Utilities: `panel`, `label-mono`, `text-display`, `noise-texture`, `grid-texture`,
  `blueprint-grid`, print rules.
- Accessibility: skip link, focus-visible ring, `aria-live` inspector, `aria-modal` dialogs,
  keyboard-operable nodes, `prefers-reduced-motion` respected in every animation.

---

## 7. Known inconsistencies to fix before/while wiring the backend

These are real defects found while auditing, not backend requirements:

1. **`HealthDashboard` ignores its data and always renders `mockHealth`** (`src/components/HealthDashboard.tsx:2,8,46,58,66,72,84`). It takes no `health` prop, so the health panel on `/analyze` shows sample numbers even for a genuinely analysed upload. It must accept `health: ArchitectureHealth` and `ResultDashboard` must pass `result.health`.
2. **Mock and real health schemas diverge.** Mock metric keys are `coupling, depth, complexity, cycles` with grade `"GOOD"`; the real analyser emits `modularity, coupling, cycles, size, reach` with grades `A/B+/B/C/D`. Pick one vocabulary and make the backend match it.
3. **Dead service exports.** `getArchitectureGraph`, `getArchitectureHealth`, `getArchitectureDiff` and `getAnalysisStages` have no call sites — `/architecture` imports `mockSummary` directly and `AnalysisProgress` uses the mock stage list directly. Either wire components through these functions (recommended, so the backend swap is one file) or drop them.
4. **`/architecture` and every landing-page section are hardcoded to mock data** and will not reflect an uploaded repository.
5. **`AnalysisProgress` is cosmetic** — its stages and timings are unrelated to the real analysis, which runs concurrently. Real progress needs either streaming from the backend or progress callbacks from the analyser.

## 8. Gaps a backend must close
1. **GitHub URL analysis** — cannot be fetched from the browser; currently falls back to the sample. Needs a server endpoint that clones/reads a repo (and private-repo auth).
2. **Persistence** — no analysis survives a reload; needs analysis IDs and stored results.
3. **Real AI explanations** — `verdict`, `evidence` and `aiSummary` are template-generated, not LLM output.
4. **Architecture diff** — fully mock; needs two stored analyses to compare.
5. **Scale** — 4000-file / 240 KB-per-file limits and regex import parsing are browser
   compromises; a backend can use real parsers/ASTs and full repos.
6. **Cycle counting** — current figure is back-edge count, not distinct cycles.
7. **Branch** — hardcoded `"uploaded"`; real value should come from the repo.
8. **Auth, rate limits, history, sharing** — none exist in the frontend yet.

Any backend that returns the exact shapes in section 3 can be dropped in behind
`src/services/api.ts` with no other changes.
