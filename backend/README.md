# ArchLens AI — Phase 1: Python Repository Analyzer

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

# Analyze the example FastAPI project
python -m archlens analyze ../examples/fastapi_project -o output

# Run the test suite
python -m pytest
```

Output:

```
output/
└── analysis.json
```

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
│   ├── cli.py                  # `python -m archlens` CLI (click)
│   ├── analyzers/
│   │   ├── scanner.py          # file discovery + exclusions + binary detection
│   │   ├── python/
│   │   │   ├── ast_parser.py   # AST extraction (imports/classes/functions/routes)
│   │   │   └── import_classifier.py  # internal/external/stdlib + categories
│   │   └── config/
│   │       └── requirements_parser.py  # requirements/pyproject/setup.py
│   ├── graph/                  # (Phase 2) dependency graph
│   ├── models/
│   │   └── schemas.py          # pydantic models = the analysis.json schema
│   └── utils/
├── archlens/                   # thin wrapper enabling `python -m archlens`
│   └── __main__.py
├── tests/                      # 127 tests (scanner, parser, classifier, analyzer)
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

Example target projects live in `../examples/` (the First Milestone's
`fastapi_project/` is a realistic FastAPI app with routes, services, models,
utils, and a requirements.txt).

---

## What the analyzer does NOT do (yet)

- ❌ Architecture inference or component classification
- ❌ Architecture health / metrics / cycle detection
- ❌ LLM integration of any kind
- ❌ JavaScript/TypeScript support
- ❌ GitHub / ZIP input
- ❌ Frontend

These are deliberately excluded so the foundation (correct, faithful code
facts) is reliable first. See the project spec for the phased roadmap.