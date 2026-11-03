# ArchLens HTTP API — `/v1/analyses`

This is the contract between the web frontend (`frontend/src/services/api.ts`)
and the FastAPI backend (`backend/app/analyses/router.py`). Field names are
camelCase because they map 1:1 onto `frontend/src/types/architecture.ts`.

Every response is produced by the existing deterministic pipeline
(Phases 1–5: `analysis.json` → `graph.json` → `architecture.json` →
`health.json` → `evolution.json`). The `/v1` layer only stores those artifacts
and adapts them into the view models the UI renders. The only endpoint that
calls an LLM is the optional `POST /v1/analyses/{id}/copilot` (see
[LLM.md](LLM.md)); it never changes the stored results.

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
- In the Compose deployment nginx also limits POSTs to the API to 20 per
  minute per client IP (burst 10), returning `429`.

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
directory persists (it is a mounted volume in Docker Compose). The uploaded
archive and extracted source are deleted as soon as the analysis finishes;
what remains are the five artifacts and `view.json`, which include short
source excerpts (`metadata.snippet`).

`analysisId` is a 32-character lowercase hex string (UUID4). Any other value
gets `404`, and it is never used to build a path until it passes that check.

## Access control (no accounts)

There are no user accounts. Instead, each analysis has its own **access
token**:

- `POST /v1/analyses` returns `accessToken` (43 random URL-safe characters,
  256 bits) **once**. The server stores only its SHA-256 hash.
- Every other request for that analysis must send it as the
  `X-ArchLens-Token` header. A diff also needs the baseline's token in
  `X-ArchLens-Baseline-Token`.
- A missing or wrong token gets the same `404 analysis_not_found` as an
  unknown id, so ids cannot be probed. The id alone grants nothing, and one
  analysis's token does not open another.
- There is **no listing endpoint**; `GET /v1/analyses` is `405`. The web UI
  keeps the ids and tokens of the analyses it uploaded in the browser's
  `localStorage` and lists those. An analysis can therefore only be opened
  from the browser that uploaded it (or by anyone that browser's user gives
  the token to). Clearing site data loses access; the analysis then simply
  expires.
- Analyses stored before tokens were introduced have no hash and are
  inaccessible; the retention sweep deletes them.

Tokens are bearer secrets: anyone holding one can read that analysis. Serve
the deployment over HTTPS (README, *Production TLS*) so they are not sent in
clear text.

## Retention and deletion

- `ARCHLENS_RETENTION_HOURS` (default `72`; `0` keeps analyses forever).
  Older analyses are deleted when accessed and by a sweep that runs on every
  upload. Incomplete directories left by a crash are swept the same way.
- `DELETE /v1/analyses/{id}` (with the token) deletes an analysis and all of
  its artifacts immediately.

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
| 404 | `analysis_not_found` | unknown / malformed / expired id, or missing / wrong token |
| 409 | `analysis_not_completed` | results requested for a failed analysis |
| 409 | `analysis_empty` | Copilot question about an analysis with no Python modules |
| 413 | `upload_too_large` | upload exceeds `ARCHLENS_MAX_UPLOAD_MB` (also enforced while a chunked body streams in) |
| 415 | `unsupported_media_type` | POST that is neither multipart nor JSON |
| 422 | `validation_error` | missing/invalid fields |
| 422 | `analysis_failed` | the pipeline raised; body also has `analysisId` and `accessToken`. The message never contains server paths |
| 422 | `analysis_timeout` | the pipeline exceeded `ARCHLENS_ANALYSIS_TIMEOUT_SECONDS`; body also has `analysisId` and `accessToken` |
| 422 | `question_too_long` | Copilot question over `ARCHLENS_COPILOT_MAX_QUESTION_CHARS` |
| 429 | `too_many_analyses` | concurrency limit reached (`Retry-After` header) |
| 429 | `upload_rate_limited` / `server_upload_limit` | per-client / server-wide hourly upload limit (`Retry-After` header) |
| 500 | `internal_error` | unexpected server error; details are only logged |
| 429 | `llm_rate_limited` / `llm_quota_exceeded` / `llm_busy` | Copilot limits (`Retry-After` header) |
| 501 | `git_not_supported` | `kind: "git"` |
| 502 | `llm_provider_error` | the LLM provider rejected the call or returned a malformed or empty answer; body has `providerError` and `retryable` |
| 503 | `llm_not_configured` | Copilot disabled or misconfigured on this server |
| 503 | `llm_provider_busy` / `llm_provider_unavailable` | provider rate-limited, down or unreachable |
| 504 | `llm_timeout` | provider did not answer within `ARCHLENS_LLM_TIMEOUT` |

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
  "aiSummary":   string[],
  "accessToken": "Zk3…"              // only in this response; see Access control
}
```

The request blocks until the pipeline finishes. Analysis runs in a worker
thread and is synchronous from the client's point of view, so `status` is
always terminal. A successful analysis of an archive with no Python files is
**not** an error: it returns `201` with `"empty": true`, empty graph nodes, and
an `explanation` of `null`.

All endpoints below require `X-ArchLens-Token`.

### `GET /v1/analyses/{id}`

Returns the same `AnalysisResponse` as `POST`, without `accessToken`. For a
failed analysis it returns the metadata (`analysisId, status, createdAt,
completedAt, repository, source, empty, error`) with `status: "failed"` and
the result fields set to `null`. `error` is `null` or `{ "code", "message" }`.

### `DELETE /v1/analyses/{id}` → `204`

### `GET /v1/analyses/{id}/graph` → `ArchitectureGraphData`
### `GET /v1/analyses/{id}/health` → `ArchitectureHealth`

`409 analysis_not_completed` if the analysis failed.

### `GET /v1/analyses/{id}/diff?baseline={otherId}` → `ArchitectureDiffData`

Requires `X-ArchLens-Baseline-Token` for `baseline` as well. Compares
`baseline` (version A) with `{id}` (version B) using the Phase 5
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

### `POST /v1/analyses/{id}/copilot`

Optional; needs an LLM provider configured on the server (see
[LLM.md](LLM.md)). Single-turn: no conversation is kept.

```json
{ "question": "Which modules depend on the database layer?" }
```

**`200`**:

```jsonc
{
  "analysisId": "3f2c…",
  "question": "Which modules depend on the database layer?",
  "answer": "…",                       // model output, not a deterministic finding
  "grounded": true,                    // false: guardrails flagged claims not found in the analysis
  "groundingWarning": null,            // the guardrail message when grounded is false
  "provider": "nvidia",
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "usage": { "promptTokens": 250, "completionTokens": 180, "totalTokens": 430 },
  "latencyMs": 2140,
  "disclosure": "Answers are generated by an external language model …"
}
```

The context is built only from this analysis's own stored artifacts, after
its token has been checked. A provider failure is always an error status
(502/503/504), never an answer. The token check, question validation and the
`analysis_empty` / `llm_not_configured` checks happen before any rate-limit or
quota is counted.

### `GET /v1/copilot/status`

No token needed. Never includes the API key or base URL.

```jsonc
{
  "enabled": true,
  "provider": "nvidia",                // null when unset
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "configurationError": null,          // e.g. "ARCHLENS_LLM_API_KEY is not set."
  "maxQuestionChars": 2000,
  "disclosure": "…"
}
```

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
