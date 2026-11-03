# Deploying ArchLens AI on Render (free plan)

ArchLens runs on Render as **two separate Docker web services**:

| Service | Dockerfile | Docker context | Health check |
|---|---|---|---|
| `archlens-backend` (FastAPI) | `backend/Dockerfile` | `backend` | `/health` |
| `archlens-frontend` (TanStack Start SSR) | `frontend/Dockerfile` | `frontend` | `/` |

Render does not run the three-service `docker-compose.yml` (nginx + frontend +
backend) as one service, and there is no nginx on Render. Instead, the browser
calls the backend's public URL directly, and the backend allows that one
frontend origin through CORS. The local Compose deployment is unchanged.

```
browser ──▶ https://archlens-frontend.onrender.com   (SSR pages, assets)
   │
   └─────▶ https://archlens-backend.onrender.com     (/v1/analyses, /health)
            CORS: FRONTEND_ORIGIN only, no credentials
```

---

## 1. How configuration reaches each service

**Backend.** Everything is read from runtime environment variables. Changing a
variable needs a restart, not a rebuild. Uvicorn listens on `0.0.0.0:$PORT`
(`python -m app.serve`; it defaults to 8000 outside Render) with one worker.

**Frontend: the API URL is a build-time setting.** TanStack Start uses Vite.
Vite replaces `import.meta.env.VITE_*` while building, so `VITE_API_BASE_URL`
is baked into both the browser bundle and the SSR bundle. Render passes a
service's environment variables to `docker build` as build arguments, and
`frontend/Dockerfile` declares `ARG VITE_API_BASE_URL`, so setting it in the
dashboard is enough. **After changing it you must rebuild:** use *Manual
Deploy → Deploy latest commit*, or the *Save, rebuild, and deploy* option,
not a plain restart.

`ARCHLENS_REQUIRE_ABSOLUTE_API_URL=true` makes the frontend build **fail** if
`VITE_API_BASE_URL` is missing, relative (`/api`) or malformed. This stops you
from deploying a frontend that sends API calls to itself. srvx serves the
frontend on `0.0.0.0:$PORT` (default 3000).

Nothing secret is ever given to the frontend. The LLM key exists only as a
backend environment variable. It is never returned by any endpoint
(`/health`, `/v1/copilot/status` and error messages are redacted) and is not
logged.

---

## 2. Option A: Blueprint (`render.yaml`)

1. Push the branch you want to deploy to GitHub. The Blueprint uses the
   repository's default branch unless you pick another one in the dashboard.
2. Render Dashboard → **New → Blueprint** → connect
   `https://github.com/GokulM8/ArchLens-AI` → select the branch.
3. Render reads `render.yaml` and asks for the `sync: false` values:
   - `FRONTEND_ORIGIN` = `https://archlens-frontend.onrender.com`
   - `VITE_API_BASE_URL` = `https://archlens-backend.onrender.com`
   - `ARCHLENS_LLM_PROVIDER`: `nvidia`, or leave empty to disable the Copilot
   - `ARCHLENS_LLM_API_KEY`: your `nvapi-…` key, or leave empty

   These URLs are a guess. Render uses `<service-name>.onrender.com` unless
   that name is taken, in which case it adds a suffix.
4. **Apply.** When both services are live, open each one and compare its URL
   (top of the service page) with what you entered. If either is different:
   - Backend → *Environment* → fix `FRONTEND_ORIGIN` → save. A restart is enough.
   - Frontend → *Environment* → fix `VITE_API_BASE_URL` → **Save, rebuild, and
     deploy**.
5. Run the checks in [§5](#5-verify).

`sync: false` values are only requested when the Blueprint is first created.
Later changes are made in each service's *Environment* tab.

---

## 3. Option B: manual dashboard setup

Create the backend first, because the frontend's build needs its URL.

### 3.1 `archlens-backend`

**New → Web Service** → connect the repository, then set:

| Setting | Value |
|---|---|
| Name | `archlens-backend` |
| Language / Runtime | **Docker** |
| Branch | the branch to deploy |
| Root Directory | *(leave empty)* |
| Dockerfile Path | `./backend/Dockerfile` |
| Docker Build Context Directory | `./backend` |
| Docker Command | *(leave empty: the image runs `python -m app.serve`)* |
| Instance Type | **Free** |
| Health Check Path (Advanced) | `/health` |
| Auto-Deploy | On Commit (default) |

**Environment variables**

| Key | Value | Notes |
|---|---|---|
| `FRONTEND_ORIGIN` | `https://archlens-frontend.onrender.com` | The frontend's exact origin: scheme + host, no path, no trailing slash. Comma-separate several (e.g. a custom domain). `*` is ignored. |
| `ARCHLENS_ANALYSES_DIR` | `/app/output/analyses` | Ephemeral |
| `ARCHLENS_RETENTION_HOURS` | `2` | |
| `ARCHLENS_MAX_STORED_ANALYSES` | `25` | Oldest are evicted first |
| `ARCHLENS_MAX_UPLOAD_MB` | `10` | Bodies over this (+1 MB) are refused while streaming |
| `ARCHLENS_MAX_UNCOMPRESSED_MB` | `100` | ZIP bomb guard |
| `ARCHLENS_MAX_ARCHIVE_FILES` | `5000` | |
| `ARCHLENS_MAX_CONCURRENT_ANALYSES` | `1` | Others get 429 + `Retry-After` |
| `ARCHLENS_ANALYSIS_TIMEOUT_SECONDS` | `180` | Runs the pipeline in a child process that is killed at the limit |
| `ARCHLENS_UPLOAD_RATE_PER_HOUR` | `10` | Per client IP |
| `ARCHLENS_UPLOAD_GLOBAL_PER_HOUR` | `60` | Whole server, applies even if IPs are spoofed |
| `ARCHLENS_TRUSTED_PROXY_HOPS` | `1` | Use the right-most `X-Forwarded-For` entry (added by Render), not the client-supplied left-most one |
| `ARCHLENS_ENABLE_LEGACY_LLM_API` | `false` | Turns off the global, non-visitor-scoped `/llm/*` endpoints |
| `ARCHLENS_LLM_PROVIDER` | `nvidia` *or empty* | Empty = Copilot disabled; analysis still works |
| `ARCHLENS_LLM_API_KEY` | `nvapi-…` *or empty* | **Secret.** Only ever set here |
| `ARCHLENS_LLM_MODEL` | `nvidia/nemotron-3.5-super-vl-120b-a12b` | |
| `ARCHLENS_LLM_RATE_PER_MINUTE` | `3` | Per client |
| `ARCHLENS_LLM_DAILY_QUOTA` | `50` | Whole server, per UTC day |
| `ARCHLENS_LLM_MAX_CONCURRENT` | `1` | |

Do **not** set `PORT`; Render provides it.

### 3.2 `archlens-frontend`

**New → Web Service** → same repository:

| Setting | Value |
|---|---|
| Name | `archlens-frontend` |
| Language / Runtime | **Docker** |
| Branch | the same branch |
| Root Directory | *(leave empty)* |
| Dockerfile Path | `./frontend/Dockerfile` |
| Docker Build Context Directory | `./frontend` |
| Docker Command | *(leave empty)* |
| Instance Type | **Free** |
| Health Check Path (Advanced) | `/` |

**Environment variables** (these are used at build time)

| Key | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://archlens-backend.onrender.com`: the backend's URL from its service page |
| `ARCHLENS_REQUIRE_ABSOLUTE_API_URL` | `true` |
| `VITE_DEMO_MODE` | `false` |

Never put `ARCHLENS_LLM_API_KEY` or any other secret here. Every `VITE_*`
value is public.

### 3.3 Close the loop

If the frontend's URL turned out different from what you put in
`FRONTEND_ORIGIN`, update it on the backend and save.

---

## 4. Environment variable reference

Backend variables not listed above keep the defaults in
`backend/.env.example`. Defaults that matter when the value is unset:

| Variable | Default (unset) | Render value |
|---|---|---|
| `FRONTEND_ORIGIN` / `ARCHLENS_CORS_ORIGINS` | CORS off (same-origin only) | frontend origin |
| `ARCHLENS_RETENTION_HOURS` | 72 | 2 |
| `ARCHLENS_MAX_STORED_ANALYSES` | 0 (unlimited) | 25 |
| `ARCHLENS_MAX_UPLOAD_MB` | 50 | 10 |
| `ARCHLENS_ANALYSIS_TIMEOUT_SECONDS` | 0 (no limit, in-process) | 180 |
| `ARCHLENS_UPLOAD_RATE_PER_HOUR` | 20 | 10 |
| `ARCHLENS_UPLOAD_GLOBAL_PER_HOUR` | 120 | 60 |
| `ARCHLENS_TRUSTED_PROXY_HOPS` | 0 (use the peer address) | 1 |
| `ARCHLENS_ENABLE_LEGACY_LLM_API` | true | false |

---

## 5. Verify

```bash
BACKEND=https://archlens-backend.onrender.com
FRONTEND=https://archlens-frontend.onrender.com

# Health (the first request after idle can take ~1 minute: cold start)
curl -s $BACKEND/health
# {"status":"ok","storage_writable":true,"llm_configured":false}

# CORS preflight from the frontend origin → 200 with allow-origin echoed
curl -si -X OPTIONS $BACKEND/v1/analyses \
  -H "Origin: $FRONTEND" -H "Access-Control-Request-Method: POST" | grep -i access-control

# Another origin → 400, no allow-origin header
curl -si -X OPTIONS $BACKEND/v1/analyses \
  -H "Origin: https://example.com" -H "Access-Control-Request-Method: POST" | head -1

# Legacy global endpoints are off
curl -s -o /dev/null -w "%{http_code}\n" $BACKEND/llm/status   # 404

# Copilot status (never contains the key)
curl -s $BACKEND/v1/copilot/status
```

Then open `$FRONTEND/analyze`, upload a small ZIP and open the result.

To check that the per-IP upload limit keys on the real client address,
upload until you get `429 upload_rate_limited` (11th upload within an hour),
then upload once from a different network, such as a phone hotspot. It
should succeed. If it is also refused with `upload_rate_limited`, every visitor
shares one bucket, which means Render put more than one proxy hop in front
of the app: raise `ARCHLENS_TRUSTED_PROXY_HOPS` to `2` and repeat. The global
hourly cap protects the server either way.

---

## 6. What the free plan means for this app

**Storage is ephemeral. Analyses do not persist.** The free plan has no
persistent disk. All uploaded analyses are lost when the service:

- spins down after ~15 minutes without traffic,
- restarts, is redeployed, or crashes.

The browser keeps each analysis's access token in `localStorage`. When the
server answers 404 for a lost analysis, the frontend forgets it. Users must
re-upload. Nothing here should be presented as saved.

**Cold starts.** A sleeping service takes about a minute to wake. The
frontend and backend sleep independently, so the first upload after a quiet
period can be slow.

**Resources.** 512 MB RAM and 0.1 CPU per service. Analysis is CPU-bound.
Even small repositories take noticeably longer than they do locally, and
large ones hit the 180 s limit (`analysis_timeout`). The upload limits above
keep memory in bounds; raising them risks the instance being killed for
running out of memory, which also wipes storage.

**Free instance hours** are shared across the workspace. Two always-busy
services can use up the monthly allowance. Idle spin-down normally keeps
usage well below it.

**Limits are in memory.** Rate limits, the Copilot quota and the
concurrency limits reset whenever the instance restarts, and are only correct
with one instance. Do not scale out without moving them to a shared store.

---

## 7. Security model for public uploads

- **Visitor isolation.** `POST /v1/analyses` returns a random access token
  once. The server stores only its SHA-256 hash. Every read, delete, diff
  and Copilot call needs that token in `X-ArchLens-Token`, and the diff
  baseline needs its own token. A wrong or missing token returns the same 404
  as an unknown id. There is no listing endpoint, and the global `/llm/*`
  endpoints are turned off (`ARCHLENS_ENABLE_LEGACY_LLM_API=false`).
- **Uploads are never executed.** ZIPs are extracted member by member with
  path-traversal, symlink, entry-count and uncompressed-size checks. Only
  static analysis runs, and the uploaded archive is deleted immediately.
- **Abuse limits.** Body size is capped while streaming, including chunked
  uploads. Uploads are rate-limited per IP and server-wide, with one
  analysis at a time and a hard time limit. Copilot calls have their own
  per-IP rate, daily quota and concurrency limits.
- **Errors.** API errors are `{detail, code}` and never contain server paths
  or stack traces. Unexpected exceptions return a generic
  `internal_error` 500 and are logged server-side only.
- **CORS.** Only the configured origin(s), no credentials, no wildcard.

### Not safe or reliable enough for public uploads on the free plan

- **Durability:** none (see §6). Do not promise users their analyses will
  still be there later.
- **Confidentiality of uploaded code.** Uploads cross the network over
  HTTPS and are stored unencrypted on the instance's disk until deleted.
  Stored analyses include short source excerpts. There is no user
  authentication: anyone who obtains an analysis's token (for example from the
  uploader's browser storage) can read it. Tell users not to upload private
  or proprietary code.
- **Copilot sends analysis data to NVIDIA.** When enabled, the deterministic
  results of the analysis, which include file and module names and may
  include excerpts, go to the external LLM provider. Each call also spends
  your API quota. The per-IP limit is best effort: IPs can be rotated, so
  the daily quota is the real cost cap. Leave the Copilot disabled for a
  public demo unless you accept both.
- **Capacity:** one analysis at a time on 0.1 CPU. A few concurrent users get
  `429 too_many_analyses`, and a determined client can use up the global
  hourly upload cap (denial of service for everyone else until the window
  rolls over).
- **In-memory limits** reset on every restart or spin-down.
- **Eviction:** when 25 analyses are stored, a new upload deletes the oldest
  one, even if it belongs to someone else and is within retention.

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Frontend build fails: `VITE_API_BASE_URL must be set to the backend's absolute URL` | Set `VITE_API_BASE_URL` on the frontend service to `https://…onrender.com` and redeploy. |
| Browser console: *blocked by CORS policy* | `FRONTEND_ORIGIN` on the backend doesn't match the page's origin exactly (`https://`, host, no trailing path). Fix and save. |
| UI: *Cannot reach the ArchLens backend (https://…)* | Backend asleep or crashed; open `$BACKEND/health`. Or `VITE_API_BASE_URL` points at the wrong host; fix it and rebuild the frontend. |
| UI shows HTML/"unreadable response" errors | `VITE_API_BASE_URL` is relative, so the frontend is calling itself. Keep `ARCHLENS_REQUIRE_ABSOLUTE_API_URL=true`. |
| Analyses disappear | Expected: spin-down/restart wipes storage, retention is 2 h, and capacity eviction removes the oldest. |
| `429 upload_rate_limited` / `server_upload_limit` | Upload limits; wait for `Retry-After`. |
| `422 analysis_timeout` | The repository is too large for 0.1 CPU within 180 s. |
| Copilot says *not configured* | Set both `ARCHLENS_LLM_PROVIDER` and `ARCHLENS_LLM_API_KEY` on the backend. |
