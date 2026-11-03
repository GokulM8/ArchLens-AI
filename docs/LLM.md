# ArchLens Architecture Copilot (optional LLM)

The deterministic pipeline (Phases 1–5) never needs an LLM. The Copilot is an
optional layer that answers questions about an analysis using a language
model, grounded in that analysis's artifacts. With no LLM configured,
everything else works and the Copilot reports itself as disabled.

## Status

| Piece | Status |
|---|---|
| Provider abstraction, mock provider, OpenAI-compatible provider | Implemented, offline-tested |
| NVIDIA provider (`integrate.api.nvidia.com`, OpenAI-compatible) | Implemented, offline-tested with a fake HTTP client. **Not yet called against the real API** (no key yet). See *Smoke test*. |
| `POST /v1/analyses/{id}/copilot` and the web panel | Implemented, tested with the mock provider and the faked NVIDIA API |
| `/llm/*` endpoints and `archlens` CLI copilot commands | Unchanged; they read the CLI output folder (`ARCHLENS_ARTIFACTS_DIR`), not uploaded analyses |
| Streaming, thinking mode, structured JSON output | **Not enabled.** See *Compatibility* |

## How it fits together

```
app/llm/provider.py            LLMProvider interface, LLMRequest / LLMResponse
app/llm/providers/
  openai_provider.py           OpenAI-compatible /chat/completions client (retries, error classes)
  nvidia_provider.py           NVIDIAProvider(OpenAIProvider): NVIDIA defaults and checks
  mock_provider.py             deterministic offline provider (tests, development)
app/llm/factory.py             picks the provider from ARCHLENS_LLM_* (no network at import or startup)
app/llm/context.py             VerifiedContextBuilder: context from the five artifacts only
app/llm/service.py             prompts, guardrails, operations (ask, explain, …)
app/llm/redaction.py           strips keys from every error before it leaves the provider
app/analyses/copilot.py        /v1 Copilot over one stored analysis
app/analyses/safeguards.py     rate limit, daily quota, concurrency for LLM calls
app/llm/smoke.py               manual real-API check (python -m app.llm.smoke)
```

The NVIDIA provider reuses the OpenAI-compatible client. It adds the NVIDIA
base URL, a default output cap of 2048 tokens, rejects options that are not
supported yet, and strips an inline `<think>…</think>` trace if a model
returns one in the answer text.

## Configuration

Set these in `backend/.env` (git-ignored; Docker Compose reads it at runtime
and never copies it into an image) or in the environment. Start from
`backend/.env.example`.

| Variable | Default | Notes |
|---|---|---|
| `ARCHLENS_LLM_PROVIDER` | *(unset = Copilot disabled)* | `nvidia`, `openai` or `mock` |
| `ARCHLENS_LLM_API_KEY` | — | required for every provider, including `mock` (any value) |
| `ARCHLENS_LLM_MODEL` | — | required for `nvidia` and `openai` |
| `ARCHLENS_LLM_BASE_URL` | NVIDIA: `https://integrate.api.nvidia.com/v1`, OpenAI: `https://api.openai.com/v1` | |
| `ARCHLENS_LLM_TIMEOUT` | NVIDIA `60`, OpenAI `30` | seconds per attempt |
| `ARCHLENS_LLM_MAX_RETRIES` | NVIDIA `2` | retries on timeouts, connection errors, 429 and 5xx |
| `ARCHLENS_LLM_MAX_TOKENS` | NVIDIA `2048`; OpenAI unset | output-token cap per answer |
| `ARCHLENS_LLM_THINKING` | unset | only `false`/unset is accepted for NVIDIA; `true` is a configuration error |
| `ARCHLENS_LLM_STREAMING` | unset | only `false`/unset is accepted; `true` is a configuration error |
| `ARCHLENS_COPILOT_MAX_QUESTION_CHARS` | `2000` | longer questions get `422 question_too_long` |
| `ARCHLENS_LLM_RATE_PER_MINUTE` | `6` | per client IP |
| `ARCHLENS_LLM_DAILY_QUOTA` | `200` | calls per UTC day, whole server |
| `ARCHLENS_LLM_MAX_CONCURRENT` | `2` | simultaneous provider calls |

### NVIDIA Nemotron

```env
ARCHLENS_LLM_PROVIDER=nvidia
ARCHLENS_LLM_API_KEY=<your nvapi-… key — never commit>
ARCHLENS_LLM_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b
ARCHLENS_LLM_BASE_URL=https://integrate.api.nvidia.com/v1
ARCHLENS_LLM_MAX_TOKENS=2048
ARCHLENS_LLM_THINKING=false
ARCHLENS_LLM_STREAMING=false
```

The model is only a setting. Any chat model your key can use on
`integrate.api.nvidia.com` works the same way (`python -m app.llm.smoke
--list-models nemotron` lists them).

### Running without a key

- **Nothing set:** the Copilot is disabled. The web panel says so, and
  `POST …/copilot` returns `503 llm_not_configured`. All analysis features work.
- **Offline development:** `ARCHLENS_LLM_PROVIDER=mock` and
  `ARCHLENS_LLM_API_KEY=anything`. Answers are canned text from
  `MockLLMProvider`, which is useful only to exercise the UI and API.

A real provider that fails is reported as an error. ArchLens never falls back
to the mock or invents an answer.

## API

`POST /v1/analyses/{id}/copilot` (needs the analysis's `X-ArchLens-Token`)
and `GET /v1/copilot/status`. Request/response shapes and error codes are in
[API.md](API.md#post-v1analysesidcopilot).

- Single-turn: each question is answered on its own; no conversation history
  is kept for uploaded analyses.
- `answer` is model output. `grounded: false` means the guardrails found
  claims they could not match to the analysis; the UI marks those answers.
- Provider failures map to `502 llm_provider_error` (auth, unknown model, bad
  request, malformed or empty answer), `503 llm_provider_busy` /
  `llm_provider_unavailable`, and `504 llm_timeout`. The body's `providerError`
  gives the exact class.

## What is sent to the provider

- The question, the system prompt, and a **fact sheet** built only from the
  requested analysis's deterministic artifacts
  (`VerifiedContextBuilder.verified_facts()`). Each line is a citable
  `[id] statement`, covering:
  - repository statistics;
  - health score and dimensions;
  - layers and patterns;
  - components (id, path, role, layer, confidence);
  - component dependencies, entry points, risks, recommendations and
    external packages.
- **Raw source code is not sent.**
- Lists are capped (60 components, 80 dependencies, 15 risks, …) and the sheet
  is cut at 16,000 characters, with a note naming what was left out. A whole
  prompt is roughly 12,000–15,500 characters (~3,000–4,000 tokens) for 18–71
  module repositories.
- The provider (NVIDIA or OpenAI) receives that data under its own terms and
  retention policy. The web panel shows this disclosure before every question.
- The API key stays on the server. It is never returned by any endpoint
  (including `/v1/copilot/status` and `/llm/status`), never in the frontend
  bundle, and is removed from provider error text (`app/llm/redaction.py`)
  before errors are logged or returned.

Because the context is structural metadata, answers can discuss components,
layers, dependencies and risks, but not the code inside a function. For large
repositories, components past the cap are invisible to the model.

## Limits and timeouts

- Per call: `ARCHLENS_LLM_TIMEOUT` × (1 + `ARCHLENS_LLM_MAX_RETRIES`) seconds
  at most (NVIDIA defaults: 60 s × 3). nginx allows 300 s.
- Output: `ARCHLENS_LLM_MAX_TOKENS`. Input: bounded by the question limit
  plus the capped fact sheet above (≈4,000 tokens at most).
- Rate limit, daily quota and concurrency (table above) are counted only for
  requests that pass the token check and validation and actually reach the
  provider. They are kept in process memory: per replica, reset on restart.
- nginx additionally limits API POSTs to 20/minute per client IP.

## Tests (offline)

```bash
cd backend
python -m pytest tests/test_llm_nvidia_provider.py tests/test_v1_access_and_copilot.py
```

No key or network is needed. HTTP is replaced by a fake client that checks
the exact request (URL, auth header, model, `max_tokens`, no streaming or
thinking fields) and simulates 401/403/404/429/5xx, timeouts, connection
errors, malformed and empty answers, and key echoes.

## Smoke test against the real NVIDIA API

Do this once you have a key. Keep streaming and thinking off.

1. **Add the key.** Edit `backend/.env` (copy `backend/.env.example` if it does
   not exist) with the NVIDIA block above. Do not paste the key anywhere else.

2. **Restart the backend.** `docker compose restart` does **not** re-read
   `env_file`; recreate the container instead:

   ```bash
   docker compose up -d --force-recreate backend
   ```

   Local development: stop and start `uvicorn app.api:app` from `backend/`
   (it loads `backend/.env`).

3. **Check the configuration without printing the key:**

   ```bash
   curl -s http://localhost:8080/api/v1/copilot/status | python3 -m json.tool
   # expect "enabled": true, "provider": "nvidia", "configurationError": null
   ```

4. **Send one minimal text request** (prints provider, model, key length,
   latency and the answer; never the key):

   ```bash
   docker compose exec backend python -m app.llm.smoke
   # local: cd backend && python -m app.llm.smoke
   ```

   If the model id is wrong, list what your key can use:

   ```bash
   docker compose exec backend python -m app.llm.smoke --list-models nemotron
   ```

5. **Ask about a real uploaded analysis.** Easiest: upload a ZIP in the UI
   (http://localhost:8080/analyze) and use the Copilot panel under the
   results. From a shell:

   ```bash
   RESP=$(curl -s -F kind=zip -F file=@my-repo.zip http://localhost:8080/api/v1/analyses)
   ID=$(printf '%s' "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["analysisId"])')
   TOKEN=$(printf '%s' "$RESP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["accessToken"])')
   curl -s -X POST "http://localhost:8080/api/v1/analyses/$ID/copilot" \
     -H "X-ArchLens-Token: $TOKEN" -H 'Content-Type: application/json' \
     -d '{"question": "Summarize the architecture and its main risks."}' | python3 -m json.tool
   ```

### Troubleshooting

| Symptom (`providerError` / smoke output) | Likely cause | What to do |
|---|---|---|
| `llm_not_configured` / `configuration error` | variable missing, or `THINKING`/`STREAMING` set to `true` | fix `backend/.env`, recreate the container |
| `provider_auth_error` (401/403) | wrong, expired or revoked key; key not enabled for this model | create a new key on build.nvidia.com; check that the model is available to your account |
| `provider_model_not_found` (404) | model id typo, or model not served at this base URL | `python -m app.llm.smoke --list-models nemotron` and copy the exact id |
| `provider_bad_request` (400/422) | the model rejects a parameter (e.g. `max_tokens` too high) | lower `ARCHLENS_LLM_MAX_TOKENS`; the error text says which field |
| `provider_rate_limited` (429) | NVIDIA account limits | wait; reduce `ARCHLENS_LLM_RATE_PER_MINUTE` / `DAILY_QUOTA` |
| `provider_timeout` / `llm_timeout` | slow model or long reasoning | raise `ARCHLENS_LLM_TIMEOUT` (and check nginx's 300 s) |
| `provider_unreachable` | no outbound network from the container, DNS, proxy | `docker compose exec backend python -c "import socket; print(socket.gethostbyname('integrate.api.nvidia.com'))"` |
| `provider_empty_response` / `provider_malformed_response` | the model spent its budget reasoning, or returned a non-chat format | raise `ARCHLENS_LLM_MAX_TOKENS`; try another model |

## Compatibility

- **Only plain, non-streaming `/chat/completions` requests are sent:** `model`,
  `messages` (system + user), `temperature` and `max_tokens`. NVIDIA
  documents these for its OpenAI-compatible endpoint.
- **Thinking mode:** NVIDIA documents
  `chat_template_kwargs: {"enable_thinking": …}` for Nemotron 3 Super. It has
  not been verified for `nemotron-3.5-super-vl-120b-a12b`, so ArchLens does not
  send it.
  - With `THINKING` unset or `false`, the model uses its default. If that
    default is to reason, answers take longer and use part of `MAX_TOKENS`.
  - A `<think>` block in the answer text is removed.
  - Enable an explicit switch only after confirming it in the model's API
    reference and with the smoke test.
- **Streaming and structured JSON output (`response_format`)** are not used.
  `LLMService(structured_output=True)` exists in code and can check cited
  fact-sheet ids, but nothing enables it yet. It needs the model to return
  strict JSON, which has not been verified with a real provider.
- **The model is a vision-language model** ("VL"). ArchLens sends text only.
