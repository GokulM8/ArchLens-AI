# ArchLens AI — Python Repository Analyzer + Architecture Copilot

ArchLens AI reconstructs a Python repository's architecture from its source code. It has three parts:

- **Deterministic engine (Phases 1–5).** Produces five artifacts: `analysis.json`, `graph.json`, `architecture.json`, `health.json` and `evolution.json`. No AI and no configuration required.
- **Web app.** A FastAPI `/v1/analyses` API plus a TanStack Start frontend. Upload a ZIP, then explore the inferred architecture graph, health score and summary, and diff two analyses.
- **Optional LLM Architecture Copilot (Phase 6).** Explains and answers questions about an analysis, grounded in the artifacts: in the web UI per uploaded analysis (`/v1/analyses/{id}/copilot`), and via `/llm/*` and CLI commands. Providers: NVIDIA Nemotron, OpenAI-compatible, or an offline mock. Env-gated and never required — see [docs/LLM.md](docs/LLM.md).

**The deterministic engine is the source of truth.** The web UI's graph, health, "explanation" and "summary" are generated from the artifacts with no model call. Only the separate Copilot panel uses an LLM, and its answers distinguish facts cited from the analysis (checked against it) from the model's interpretation and suggestions.

## What works today

| Capability | Status |
|---|---|
| Python static analysis (AST: modules, classes, functions, routes, imports, dependencies) | ✅ |
| Dependency graph, architecture inference, health/risk, evolution artifacts | ✅ |
| CLI `python -m archlens analyze PATH` | ✅ |
| HTTP API `/v1/analyses`: ZIP upload, results, graph, health, diff | ✅ ([contract](docs/API.md)) |
| Web UI: upload → graph + inspector (with real source excerpts) → health → summary → report | ✅ |
| Stored analyses survive backend restarts (files on disk / Docker volume) | ✅ |
| Diff between two stored analyses | ✅ |
| Docker Compose: nginx + frontend + backend, with real health checks | ✅ |
| Optional LLM Copilot over uploaded analyses (web panel, `/v1/analyses/{id}/copilot`) | ✅ mock-tested; NVIDIA endpoint: smoke test pending an API key |
| Optional LLM Copilot over CLI output (`/llm/*`, CLI `explain`/`ask`) | ✅ |
| Per-IP rate limits, daily LLM quota, output-token ceiling | ✅ in-memory, single process |
| Git / GitHub URL input | ❌ API returns `501 git_not_supported` |
| Languages other than Python | ❌ |
| Authentication, multi-user isolation, retention | ❌ |
| HTTPS inside the stack | ❌ terminate TLS in front (see below) |

## Repository layout

```
backend/    FastAPI app, deterministic pipeline, LLM copilot, tests
frontend/   TanStack Start (React 19, Vite) web UI
nginx/      reverse proxy config used by docker-compose
docs/API.md /v1 request/response contract
examples/   sample FastAPI project to analyse
scripts/    clean-appledouble.sh (see "External drives" below)
```

## Local development

### Backend

Requires Python ≥ 3.11.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# CLI: analyse a repository, write the five artifacts to ./output
python -m archlens analyze ../examples/fastapi_project -o output

# API on http://localhost:8000 (stores uploads under ./output/analyses)
uvicorn app.api:app --reload --port 8000
```

### Frontend

Requires [Bun](https://bun.sh) (the lockfile is `bun.lock`).

```bash
cd frontend
bun install
bun run dev          # Vite dev server (http://localhost:5173), proxies /api → http://localhost:8000
```

To use the production build locally:

```bash
bun run build && bun run start   # srvx on $PORT (default 3000)
```

`bun run start` serves pages and assets but has **no `/api` proxy**. Use the
Vite dev server or Docker Compose (nginx) for a working UI, or set
`VITE_API_BASE_URL` to the backend's URL and add the frontend origin to
`ARCHLENS_CORS_ORIGINS`.

### Configuration

| Where | File | Notes |
|---|---|---|
| Backend | `backend/.env` (copy `backend/.env.example`) | Storage dir, upload limits, CORS, optional LLM. Git-ignored and loaded at runtime |
| Frontend | `frontend/.env.local` (see `frontend/.env.example`) | `VITE_API_BASE_URL` (default `/api`), `VITE_DEMO_MODE`. **Embedded in the bundle — never put secrets here** |

**Demo mode.** With `VITE_DEMO_MODE=true` the frontend makes no backend calls
and shows the bundled sample repository, labelled "demo". In the default
backend mode, failures are shown as errors and sample data is never used as
a fallback. The landing page (`/`) always shows the sample repository as
illustration.

## Tests

```bash
cd backend && python -m pytest                 # full backend suite (incl. /v1 API integration tests)
cd frontend && bun run typecheck && bun run build
```

## Docker Compose

```bash
cp backend/.env.example backend/.env   # optional; every value has a default
docker compose up --build -d
open http://localhost:8080             # ARCHLENS_HTTP_PORT overrides 8080
docker compose ps                      # all three services should be "healthy"
curl http://localhost:8080/api/health
```

| Service | Role | Published |
|---|---|---|
| `nginx` | `/api/*` → backend (prefix stripped), everything else → frontend | `8080` |
| `frontend` | SSR + static assets (srvx, Node 22) | internal `3000` |
| `backend` | FastAPI + pipeline (uvicorn) | internal `8000` |

- Analyses are stored in the `archlens-data` named volume
  (`docker compose down -v` deletes them).
- `backend/.env` is optional and read **at runtime**. `.dockerignore` keeps it
  (and every `.env*`) out of the images.
- Health checks: the backend's `/health` returns 503 unless analysis storage
  is writable. The frontend check fetches `/`. nginx waits for both to be
  healthy before starting.
- Upload size is enforced twice: nginx `client_max_body_size 55m` and the
  backend's `ARCHLENS_MAX_UPLOAD_MB` (default 50). Change both together.
- nginx mounts `nginx/nginx.conf` as a single file. After editing it, run
  `docker compose up -d --force-recreate nginx` (a plain reload can miss the
  change on some filesystems).

### Production TLS

The stack serves plain HTTP and ships **no certificates**. For a real
deployment, terminate TLS in front of nginx with a load balancer, an ingress,
or a separate proxy such as Caddy or Traefik with Let's Encrypt. Publish only
443 there, and put no keys in this repository (`*.key`/`*.pem` are
git-ignored). Also add authentication before exposing the app: the API has
none, and anyone who can reach it can read every stored analysis.

## Known limitations

- **Python only.** Other files are counted but not analysed.
- **ZIP upload only.** Git URLs return `501`.
- **Synchronous analysis.** `POST /v1/analyses` blocks until the pipeline
  finishes (nginx allows 300 s). Concurrency is capped by
  `ARCHLENS_MAX_CONCURRENT_ANALYSES` (default 2), and extra requests get
  `429` with `Retry-After`. There is no progress streaming, so the UI shows an
  indeterminate progress state.
- **Storage.** Each analysis is a directory on local disk. There is no database,
  retention policy, access control or multi-instance sharing, so run one
  backend replica per volume.
- **Copilot.** Answers are not streamed to the browser. `/llm/conversations`
  are in memory and lost on restart; the web Copilot is single-turn. Rate limits
  are per process and reset on restart. Real NVIDIA compatibility is verified
  only by the smoke test (`python -m app.llm.smoke`), not by `pytest`.
- **No access control.** Analysis ids are unguessable (uuid4), but listing is on
  by default and any id holder can read an analysis and use the Copilot on it.
  Set `ARCHLENS_ANALYSIS_LISTING=false` publicly; it is still not authorization.
- **Session state in the browser** is in memory. Reopen a stored analysis via
  `/architecture?id=<analysisId>` or the list on `/architecture`.
- **Large graphs.** Repositories with more than 24 components are grouped by
  package directory in the graph. The diff's mini-graphs get crowded above
  ~12 components; the change list is the precise view.
- **Source viewer** shows a ≤14-line excerpt per component, not whole files.

### External drives (FAT32/exFAT on macOS)

macOS writes a `._<name>` AppleDouble file next to every file it creates on
FAT/exFAT volumes, including inside `.git`. These break git
(`non-monotonic index` errors) and Docker builds
(`failed to xattr ... ._*`). Run `scripts/clean-appledouble.sh` before
`docker compose build` and if git starts printing index errors. It deletes
only files with the AppleDouble signature. Moving the repository to an APFS
volume avoids the problem entirely.

## Architecture Copilot (optional LLM layer)

The copilot explains, summarizes, and reasons over the five deterministic artifacts. It is **entirely optional and env-gated** — the deterministic pipeline above runs with no LLM configuration. **Full guide: [docs/LLM.md](docs/LLM.md)** (NVIDIA setup, thinking/streaming, structured answers, errors, data sent to the provider, quotas, smoke test).

### Configuration

All config is via environment variables in `backend/.env` (backend only — never a `VITE_*` variable):

```bash
ARCHLENS_LLM_PROVIDER=nvidia          # or "openai", or "mock" for offline use
ARCHLENS_LLM_API_KEY=                 # never commit or log this
ARCHLENS_LLM_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b
ARCHLENS_LLM_BASE_URL=https://integrate.api.nvidia.com/v1
ARCHLENS_LLM_MAX_TOKENS=2048
ARCHLENS_LLM_THINKING=false
ARCHLENS_LLM_STREAMING=false
```

Check the endpoint with `cd backend && python -m app.llm.smoke` (real, quota-counted
calls; exits `2` = pending when no key is set).

`is_configured()` requires both a provider name and an API key. Without them,
all copilot operations return a clear structured error — never a traceback.

### Quick start — offline mock provider

```bash
cd backend
export ARCHLENS_LLM_PROVIDER=mock
export ARCHLENS_LLM_API_KEY=test-key
python -m archlens ask "What is the architecture?" -o output
```

The mock provider needs no network and is what the test suite uses: **the
normal test suite never makes a real OpenAI request.**

### CLI

```bash
cd backend
python -m archlens explain architecture -o output
python -m archlens explain summary -o output
python -m archlens explain component module:app.main -o output
python -m archlens explain dependency module:app.main module:app -o output
python -m archlens explain risk <risk_id> -o output
python -m archlens explain recommendation <recommendation_id> -o output
python -m archlens explain impact module:app.main -o output
python -m archlens explain refactor-plan <recommendation_id> -o output
python -m archlens ask "Why is this component central?" -o output
```

Failures exit with code 1 and print a structured error plus suggestions.

### API

Run with FastAPI (e.g. `uvicorn app.api:app`), pointing
`ARCHLENS_ARTIFACTS_DIR` at the analysis output directory:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Readiness: 503 unless analysis storage is writable; reports `llm_configured` |
| * | `/v1/analyses…` | Upload & results API — see [docs/API.md](docs/API.md) |
| GET | `/llm/status` | Provider config status (never leaks the API key) |
| POST | `/llm/explain` | Explain architecture |
| POST | `/llm/ask` | Ask an architecture question |
| POST | `/llm/component` | Explain a component |
| POST | `/llm/dependency` | Explain a dependency |
| POST | `/llm/risk` | Explain a risk |
| POST | `/llm/recommendation` | Explain a recommendation |
| POST | `/llm/impact` | Impact reasoning |
| POST | `/llm/refactor-plan` | Refactoring plan |
| POST | `/llm/summary` | Repository summary |
| POST | `/llm/conversations` | Create a conversation |
| POST | `/v1/analyses/{id}/copilot` | Copilot over an uploaded analysis — see [docs/API.md](docs/API.md) |
| GET | `/llm/conversations/{id}` | Read a conversation (multi-turn history) |

### How it works

- **VerifiedContextBuilder** (`app/llm/context.py`) builds prompt context only
  from the five artifact files — the LLM is never given unverified facts about
  the repository.
- **GroundingGuardrails** (`app/llm/guardrails.py`) validate the LLM output
  against the artifacts, flagging invented components/files/roles/dependencies,
  secrets/PII, and malformed responses. Violations surface as a
  `validation_warning` on the response.
- **LLMService** (`app/llm/service.py`) orchestrates nine operations, in-memory
  conversations, and structured error handling
  (`configuration_error` / `invalid_operation` / `invalid_target` /
  `execution_error` / `validation_warning`, plus provider errors such as
  `rate_limited`, `timeout`, `invalid_model_output`). A failed provider call is
  always reported as a failure, never as an empty success.
- Every prompt carries the citable fact sheet from
  `VerifiedContextBuilder.verified_facts()`; in structured mode (`/v1`) the
  answer must be a `CopilotAnswer` JSON object whose citations are checked.

See `../PHASE_6_REPORT.md` for the full phase report.

---

## CLI

```
usage: python -m archlens analyze PATH [--output DIR]

  PATH     repository root directory to analyze (Python only for now)
  --output directory to write analysis.json (default: output/)
```

---

## The `analysis.json` schema (version 1.0)

Top-level layout:

```json
{
  "schema_version": "1.0",
  "repository": { },
  "files": [],
  "modules": [],
  "classes": [],
  "functions": [],
  "routes": [],
  "dependencies": [],
  "relationships": [],
  "statistics": {}
}
```

### Design principles

1. **Facts only.** Every field is extracted deterministically from the AST or
   from dependency files. There is deliberately **no confidence field** in this
   phase — inference and confidence arrive with the architecture layer later.
2. **Stable IDs.** Every code entity has an ID you can reference across phases:
   - `module:<dotted.path>` — a module/package
   - `file:<relative/path>:<name>` — a class or function
   - `route:<method_lower>:<path>` — an API endpoint
   These are the keys the dependency graph (Phase 2) and architecture graph
   (Phase 3) will build on.
3. **Relative paths only.** No absolute paths leave the machine; `repository.root_path`
   is recorded as metadata only.
4. **Line numbers preserved.** Where the AST gives a line, it is kept — this is
   the evidence trail for later reasoning.
5. **Classification is kept separate from facts.** An import is tagged
   `internal` / `external` / `standard_library` by the classifier, but the raw
   imported module string is always preserved alongside it.

### Key entities

| Entity | Fields | Notes |
|---|---|---|
| `repository` | name, root_path, analyzed_at, python_version, total_size_bytes | Top-level metadata |
| `file` | path, size_bytes, lines, module_name, package, is_init | One per `.py` file |
| `module` | id, path, package, imports, classes, functions | Module-level view + imports |
| `class` | id, name, file, line, end_line, bases, decorators, methods, is_dataclass, is_pydantic_model | `bases` from actual AST, not parsing names |
| `function` | id, name, qualified_name, file, line, end_line, is_async, parameters, return_annotation, decorators, class_id | Methods link to their class via `class_id` |
| `route` | method, path, function_id, function_name, file, line, framework, router_name | FastAPI + Flask decorator detection |
| `dependency` | name, version_constraint, source_file, category | From requirements.txt / pyproject.toml / setup.py |
| `relationship` | source, target, type, file, line | `IMPORTS`, `CONTAINS`, `EXPOSES` |

### Relationship types emitted

| Type | Meaning |
|---|---|
| `IMPORTS` | module → module (resolved to the **exact** internal target) |
| `CONTAINS` | module → class / module → function |
| `EXPOSES` | function → route |

`CALLS` and `INHERITS` are reserved for the graph phase where call/inheritance
edges can be established without guessing.

---

## Repository structure

```
backend/
├── app/                        # package root
│   ├── analyzer.py             # orchestrates scan → parse → classify → JSON
│   ├── cli.py                  # `python -m archlens` CLI (click) + `explain`/`ask`
│   ├── api.py                  # FastAPI app: `/health`, `/llm/*`, mounts `/v1`
│   ├── pipeline.py             # Phase 1–5 pipeline shared by CLI and API
│   ├── analyses/               # `/v1/analyses`: safe ZIP ingest, storage, view adapter

│   ├── analyzers/
│   │   ├── scanner.py          # file discovery + exclusions + binary detection
│   │   ├── python/
│   │   │   ├── ast_parser.py   # AST extraction (imports/classes/functions/routes)
│   │   │   └── import_classifier.py  # internal/external/stdlib + categories
│   │   └── config/
│   │       └── requirements_parser.py  # requirements/pyproject/setup.py
│   ├── graph/                  # (Phase 2) dependency graph
│   ├── architecture/           # (Phase 3) component/role/pattern inference
│   ├── health/                 # (Phase 4) health/risk inference
│   ├── evolution/              # (Phase 5) refactoring opportunities + impact
│   ├── llm/                    # (Phase 6) Architecture Copilot
│   │   ├── context.py          # VerifiedContextBuilder (artifact-grounded)
│   │   ├── prompts.py          # PromptManager (per-operation prompts)
│   │   ├── guardrails.py       # GroundingGuardrails (facts/secrets/structure)
│   │   ├── service.py          # LLMService (operations, conversations, errors)
│   │   ├── factory.py          # env-driven provider factory
│   │   └── providers/          # openai_provider.py + mock_provider.py
│   ├── models/
│   │   └── schemas.py          # pydantic models = the analysis.json schema
│   └── utils/
├── archlens/                   # thin wrapper enabling `python -m archlens`
│   └── __main__.py
├── tests/                      # backend test suite (all phases + /v1 API)
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

Example target projects live in `../examples/` (the First Milestone's
`fastapi_project/` is a realistic FastAPI app with routes, services, models,
utils, and a requirements.txt).

---

## License

Apache 2.0
