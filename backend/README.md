# ArchLens AI — Python Repository Analyzer + Architecture Copilot

ArchLens AI is a deterministic Python repository analysis engine that
reconstructs architecture from source code, plus an **optional** LLM-powered
Architecture Copilot that explains and reasons over the results.

The deterministic pipeline (Phases 1–5) produces five fact-only artifacts —
`analysis.json`, `graph.json`, `architecture.json`, `health.json`,
`evolution.json` — with **no AI and no configuration required**. The
Architecture Copilot (Phase 6) adds explanations, summaries, risk analysis,
and refactoring plans over those artifacts via an optional, env-gated LLM
layer. **The deterministic engine is the source of truth; the LLM is an
explanation, synthesis, and reasoning layer.**

Deterministic static analysis engine that reconstructs a Python repository's
structure from source code. This is the **first milestone**: it produces
`analysis.json` — a complete, versioned, fact-only representation of what the
code contains.

> **Phase 1 scope:** repository scanning + Python AST analysis + dependency
> extraction + relationship graph. No architecture inference, no LLM, no
> frontend yet — those come in later phases.

---

## Quick start

```bash
cd backend
pip install -r requirements.txt          # runtime deps
pip install -r requirements-dev.txt      # pytest (for tests)

# Analyze the example FastAPI project (produces all five artifacts)
python -m archlens analyze ../examples/fastapi_project -o output

# Run the test suite
python -m pytest
```

Output:

```
output/
├── analysis.json
├── graph.json
├── architecture.json
├── health.json
└── evolution.json
```

---

## Architecture Copilot (optional LLM layer)

The copilot explains, summarizes, and reasons over the five deterministic
artifacts. It is **entirely optional and env-gated** — the deterministic
pipeline above runs with no LLM configuration.

### Configuration

All config is via environment variables — no hard-coded credentials or
model names anywhere:

```bash
export ARCHLENS_LLM_PROVIDER=openai   # or "mock" for offline use
export ARCHLENS_LLM_MODEL=            # your choice of OpenAI model
export ARCHLENS_LLM_API_KEY=          # never commit or log this
export ARCHLENS_LLM_BASE_URL=https://api.openai.com/v1
export ARCHLENS_LLM_TIMEOUT=30
```

`is_configured()` requires both a provider name and an API key. Without them,
all copilot operations return a clear structured error — never a traceback.

### Quick start — offline mock provider

```bash
export ARCHLENS_LLM_PROVIDER=mock
export ARCHLENS_LLM_API_KEY=test-key
python -m archlens ask "What is the architecture?" -o output
```

The mock provider needs no network and is what the test suite uses: **the
normal test suite never makes a real OpenAI request.**

### CLI

```bash
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
| GET | `/health` | Liveness + `llm_configured` |
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
  `execution_error` / `validation_warning`).

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
│   ├── api.py                  # FastAPI app + `/health` + `/llm/*` endpoints
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
├── tests/                      # 414 tests across all six phases
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

Example target projects live in `../examples/` (the First Milestone's
`fastapi_project/` is a realistic FastAPI app with routes, services, models,
utils, and a requirements.txt).

---

## What the analyzer does NOT do (yet)

- ❌ JavaScript/TypeScript support
- ❌ GitHub / ZIP input
- ❌ Web frontend
- ❌ Persistent conversation storage (in-memory only, per server process)

Phase 1–5 analysis is deterministic and off by default for the LLM layer; the
LLM copilot is an optional, env-gated enhancement (see above), never a
dependency of the core analysis.