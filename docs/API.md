# ArchLens HTTP API — `/v1/analyses`

This is the contract between the web frontend (`frontend/src/services/api.ts`)
and the FastAPI backend (`backend/app/analyses/router.py`). Field names are
camelCase because they map 1:1 onto `frontend/src/types/architecture.ts`.

Every response is produced by the existing deterministic pipeline
(Phases 1–5: `analysis.json` → `graph.json` → `architecture.json` →
`health.json` → `evolution.json`). The `/v1` layer only stores those artifacts
and adapts them into the view models the UI renders. No LLM is called by these
endpoints.

## Supported input

| Input | Status |
|---|---|
| ZIP archive upload (`multipart/form-data`) | **Supported** |
| Git / GitHub URL | **Not supported** — returns `501 git_not_supported` |
| Server-side local path | Not exposed over HTTP (CLI only) |

Only Python sources are analysed (the Phase 1 analyzer is Python-only).

### Upload safety

- The upload is streamed to disk and aborted once it exceeds
  `ARCHLENS_MAX_UPLOAD_MB` (default 50).
- Archive members are rejected if they are absolute, contain `..`, drive
  letters or NUL bytes, or are symlinks.
- Extraction enforces `ARCHLENS_MAX_ARCHIVE_FILES` (default 20000) and
  `ARCHLENS_MAX_UNCOMPRESSED_MB` (default 500), counting bytes actually
  written, not the sizes the ZIP headers claim.
- Each analysis is extracted into its own `tempfile.mkdtemp()` directory,
  which is deleted when the analysis finishes. Nothing in the archive is
  executed.
- `ARCHLENS_MAX_CONCURRENT_ANALYSES` (default 2) limits concurrent analyses.
  When the limit is reached, requests get a `429` response with a
  `Retry-After` header.

## Storage

Each analysis is a directory under `ARCHLENS_ANALYSES_DIR` (default
`output/analyses`):

```
output/analyses/<analysisId>/
  metadata.json        # id, status, repository, timestamps, error
  analysis.json graph.json architecture.json health.json evolution.json
  view.json            # the adapted AnalysisResult served to the UI
```

The data lives on disk, so it survives a backend restart as long as the
directory persists (it is a mounted volume in Docker Compose). There is no
retention policy and no authentication: anyone who can reach the API can list
and read every stored analysis. See *Known limitations* in the README.

`analysisId` is a 32-character lowercase hex string (UUID4). Any other value
gets `404`, and it is never used to build a path until it passes that check.

## Error format

Every `/v1` error response has this body:

```json
{ "detail": "Human readable message", "code": "machine_code" }
```

Validation errors also include `"errors": [...]` (Pydantic's error list).

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_archive` | not a ZIP, corrupt, unsafe member, too many files, too large uncompressed |
| 400 | `missing_baseline` | diff without `baseline` |
| 400 | `same_analysis` | diff of an analysis against itself |
| 404 | `analysis_not_found` | unknown / malformed id |
| 409 | `analysis_not_completed` | results requested for a failed analysis |
| 413 | `upload_too_large` | upload exceeds `ARCHLENS_MAX_UPLOAD_MB` |
| 415 | `unsupported_media_type` | POST that is neither multipart nor JSON |
| 422 | `validation_error` | missing/invalid fields |
| 422 | `analysis_failed` | the pipeline raised; body also has `analysisId` |
| 429 | `too_many_analyses` | concurrency limit reached (`Retry-After` header) |
| 501 | `git_not_supported` | `kind: "git"` |

## Endpoints

### `POST /v1/analyses`

ZIP upload (`multipart/form-data`):

| field | type | notes |
|---|---|---|
| `file` | file | required, `.zip` |
| `kind` | string | optional, must be `"zip"` if present |

Git (JSON) — always `501` today:

```json
{ "kind": "git", "source": "https://github.com/org/repo" }
```

**`201 Created`** → `AnalysisResponse`:

```jsonc
{
  "analysisId": "3f2c…",
  "status": "completed",              // completed | failed
  "createdAt": "2026-10-28T08:16:37Z",
  "completedAt": "2026-10-28T08:16:38Z",
  "repository": "fastapi_project",
  "source": { "kind": "zip", "filename": "fastapi_project.zip" },
  "empty": false,                     // true when no Python modules were found
  "summary":     AnalysisSummary,
  "graph":       ArchitectureGraphData,
  "health":      ArchitectureHealth,
  "explanation": AIExplanation | null,
  "aiSummary":   string[]
}
```

The request blocks until the pipeline finishes. Analysis runs in a worker
thread and is synchronous from the client's point of view, so `status` is
always terminal. A successful analysis of an archive with no Python files is
**not** an error: it returns `201` with `"empty": true`, empty graph nodes, and
an `explanation` of `null`.

### `GET /v1/analyses`

Newest first. `?limit=` (1–200, default 50).

```json
{ "items": [ AnalysisMetadata, … ] }
```

`AnalysisMetadata` = `analysisId, status, createdAt, completedAt, repository,
source, empty, error`. `error` is `null` or `{ "code", "message" }`.

### `GET /v1/analyses/{id}`

Returns the same `AnalysisResponse` as `POST`. For a failed analysis it
returns `AnalysisMetadata` with `status: "failed"` and the result fields set
to `null`.

### `GET /v1/analyses/{id}/graph` → `ArchitectureGraphData`
### `GET /v1/analyses/{id}/health` → `ArchitectureHealth`

`409 analysis_not_completed` if the analysis failed.

### `GET /v1/analyses/{id}/diff?baseline={otherId}` → `ArchitectureDiffData`

Compares `baseline` (version A) with `{id}` (version B) using the Phase 5
`ArchitectureDiffer`. It needs two completed analyses. There is no git
history, so "versions" are two uploads, for example two snapshots of the same
project.

```jsonc
{
  "versionA": { "label": "fastapi_project · 2026-10-28 08:16", "graph": ArchitectureGraphData },
  "versionB": { "label": "fastapi_project · 2026-10-28 09:02", "graph": ArchitectureGraphData },
  "changes": [
    { "kind": "added" | "modified" | "removed", "label": "…", "detail": "…" }
  ]
}
```

Mapping: component `added`/`removed` stay as they are; `role_changed` and
`layer_changed` become `modified`; dependency and pattern changes become
`added`/`removed`.

## View-model mapping

### `AnalysisSummary`

| field | source |
|---|---|
| `repository` | `analysis.repository.name` (archive root folder, else ZIP filename) |
| `branch` | always `"archive upload"` (a ZIP carries no branch information) |
| `filesScanned` | `analysis.statistics.total_files` |
| `modules` | `analysis.statistics.total_python_files` |
| `apiRoutes` | `analysis.statistics.total_routes` |
| `externalServices` | `analysis.statistics.external_dependencies` |
| `circularDependencies` | `health.dependency_metrics.circular_dependency_count` |
| `languages` | `[{"name": "Python", "share": 1}]` when Python files exist, else `[]` |

### `ArchitectureGraphData`

- Nodes are the Phase 3 architecture components. When there are more than 24,
  they are grouped by package directory (shallowest depth that fits; past
  that, the top 23 groups plus `other`). Grouped nodes carry
  `metadata.groupPath` and `metadata.fileCount`.
- `type` comes from the component's role: `route`/`middleware` → `gateway`;
  `service`/`authentication`/`ml` → `service`; `model` → `model`;
  `database`/`repository` → `datastore`; `external_service` → `external`;
  everything else → `module`.
- `layer` is the column index of the architectural layer (Presentation=0 …
  Unknown=8). `position` is a normalized 0..1 layout (columns = occupied
  layers, rows spread evenly).
- `confidence` is the Phase 3 classification confidence.
- `metadata.snippet` is a real excerpt (≤14 lines) of the component's source,
  read before the temporary directory is deleted. `snippetSignals` are the
  classification evidence descriptions.
- Edges are the Phase 3 component relationships, aggregated per
  (source, target) pair. `type` is `imports`, except `queries` when the target
  is a datastore. `label` is `"N imports"`.

### `ArchitectureHealth`

- `score` = `round(overall_health.score × 100)`.
- `grade` = the Phase 4 rating, title-cased (`Excellent`, `Good`, `Fair`,
  `Concerning`, `Critical`).
- `metrics` = the five Phase 4 dimensions (`value`/`score` = dimension score
  × 100, `unit` `/100`, `hint` = first issue or `weight N%`).
- `warnings` = Phase 4 risk titles plus layer-violation and cycle counts.
  `strengths` = dimensions scoring ≥ 80 with no issues.

### `AIExplanation` and `aiSummary`

These are **deterministic** text built from the artifacts (the
highest-degree component's classification evidence, and facts from the
statistics, patterns, health and risks). The field names come from the UI.
No model is called. LLM explanations are still available separately through
the `/llm/*` endpoints.
