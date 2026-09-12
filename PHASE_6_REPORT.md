# ArchLens AI — Phase 6: LLM Architecture Intelligence & Copilot — Final Report

**Date**: 2026-09-12  
**Status**: ✅ Complete  
**Test Results**: 414 tests passing (100% pass rate maintained)

---

## Executive Summary

Phase 6 is the **Architecture Copilot**: an optional LLM layer that produces
explanations, summaries, risk analysis, reasoning, and refactoring plans over
the deterministic ArchLens artifacts (Phases 1–5). It is a pure enhancement to
the pipeline — **the deterministic ArchLens engine remains the source of truth,
and the LLM is an explanation, synthesis, and reasoning layer.**

The Phase 6 layer comes with:

1. **LLM Provider Abstraction (6.1)** — a clean provider interface with an
   OpenAI provider and a fully deterministic `MockLLMProvider`.
2. **LLM Schemas (6.2)** — typed Pydantic v2 models for operations, responses,
   grounding sources, errors, metadata, and conversations.
3. **Verified Context Builder (6.3)** — a context layer that is built **only**
   from verified artifact facts (no hallucinated repository content).
4. **Prompt Manager (6.4)** — operation-specific system prompts with grounding
   instructions and bounded health/opportunity findings.
5. **Grounding Guardrails (6.5)** — validates LLM output against the verified
   artifacts, flags invented components/files/roles/dependencies, detects
   secrets and PII, and validates response structure.
6. **LLM Service (6.6)** — orchestrates all operations, conversation history,
   structured error handling, and validation warnings.
7. **API (6.15)** — FastAPI endpooints under `/llm/*` plus `/health`.
8. **CLI (6.16)** — `archlens explain …` group and `archlens ask` commands.
9. **Conversation Support (6.17)** — in-memory multi-turn conversations.
10. **Complete Testing (6.17)** — 153 new tests across context, prompts,
    guardrails, service, API, and CLI layers (414 total).

---

## Security & Design Requirements Met

| Requirement | Status |
|-------------|--------|
| Config via environment variables only (`ARCHLENS_LLM_*`) | ✅ |
| No hard-coded model names (e.g. `gpt-4o`) anywhere | ✅ |
| No hard-coded credentials; credentials never logged | ✅ |
| Request timeout enforced on all LLM calls | ✅ |
| Safe filesystem handling (paths from CLI/API args, directory-scoped) | ✅ |
| No arbitrary code execution | ✅ |
| No automatic modification / commit / deployment | ✅ |
| No unrestricted repository access | ✅ |
| Complete repository contents never logged by default | ✅ |
| API credentials never stored in JSON artifacts | ✅ |
| Normal test suite never requires a real OpenAI request | ✅ |
| LLM ops without config return a clear structured error | ✅ |
| Deterministic analysis always works (no LLM configuration needed) | ✅ |
| Context budget respected (`DEFAULT_MAX_TOKENS = 100_000` ceiling) | ✅ |

The model name is sourced **exclusively** from `ARCHLENS_LLM_MODEL`; it is never
defaulted to a specific vendor model name in code. The provider factory, the
OpenAI provider, the service, and the `.env.example` all follow this rule.

---

## Architecture

### LLM Package

```
backend/app/llm/
├── __init__.py              # Package exports
├── provider.py              # Abstract LLMProvider interface
├── factory.py               # LLMProviderFactory (env-driven, no hard-coded model)
├── schemas.py               # Pydantic v2 schemas (operations, responses, conversations)
├── context.py               # VerifiedContextBuilder (artifact-grounded context only)
├── prompts.py               # PromptManager (per-operation system prompts)
├── guardrails.py            # GroundingGuardrails (fact validation, secrets, structure)
├── service.py               # LLMService (operation orchestration, conversations, errors)
└── providers/
    ├── openai_provider.py   # Real OpenAI provider (with retries + timeout)
    └── mock_provider.py     # Deterministic mock provider for offline/test use
```

### The Nine Public Operations

| Operation | Enum | Purpose |
|-----------|------|---------|
| Architecture explanation | `ARCHITECTURE_EXPLANATION` | Explain the repository architecture |
| Architecture QA | `ARCHITECTURE_QA` | Answer free-form architecture questions |
| Component explanation | `COMPONENT_EXPLANATION` | Explain one component by its id |
| Dependency explanation | `DEPENDENCY_EXPLANATION` | Explain source→target relationship |
| Risk explanation | `RISK_EXPLANATION` | Explain an architectural risk |
| Recommendation explanation | `RECOMMENDATION_EXPLANATION` | Explain an evolution recommendation |
| Impact reasoning | `IMPACT_REASONING` | Analyze impact of changing a component |
| Refactoring plan | `REFACTORING_PLAN` | Generate a plan for a recommendation |
| Repository summary | `REPOSITORY_SUMMARY` | Summarize repository architecture/patterns |

Every operation produces a structured `LLMOperationResponse` with content,
grounding evidence, provider metadata, and structured errors on failure.

### Verified Context Builder (6.3)

The context builder loads the five deterministic artifacts
(`analysis.json`, `graph.json`, `architecture.json`, `health.json`,
`evolution.json`) and builds **verified** context:

- Repository-level metrics and inventory
- Component roles, layers, patterns
- Dependency edges and cycle boundaries
- Risks, hotspots, layer violations
- Refactoring opportunities with impact analysis

All context references real artifact IDs (`module:app.main`,
`high_coupling:module:app.main`, `reduce_coupling:module:app.main`,
`source||target` dependency pairs). Unknown targets raise a structured
`invalid_target` error with suggested valid ids.

### Prompt Manager (6.4)

- 9 operation-specific system prompts, all grounding-flavored
- `build_operation_prompt` composes request, verified context, and target
- Health findings are limited to the top 3 to respect the context budget
- Distinct completion instructions per operation
- Unknown/empty requests fall back to a safe default prompt

### Grounding Guardrails (6.5)

- **Repository-fact validation**: flags unknown components, files, roles,
  and dependency pairs that are not in the verified artifacts
- **Secrets/PII detection**: flags `sk-…` keys, `AKIA…` AWS keys, PEM private
  keys, and email addresses
- **Response-structure validation**: requires non-empty content and metadata
- **Suggestion on failure**: every rejection carries a `suggested_fix`

### LLM Service (6.6)

- Operation registry + uniform handler dispatch
- Provider creation from env per request; clear `configuration_error` when
  unset (never a traceback, never a hard-coded model suggestion)
- Unknown operations → `invalid_operation`; missing targets → `invalid_target`;
  handler exceptions → `execution_error`
- Guardrail violations → `validation_warning` (operation still succeeds)
- **Conversations**: create/get/list/filter/delete/append, multi-turn
  user+assistant recording, `max_history_turns` trimming, and history
  injection into the provider prompt

### Error Taxonomy

| Error type | Meaning |
|------------|---------|
| `configuration_error` | LLM not configured (no provider/key) |
| `invalid_operation` | Unknown operation requested |
| `invalid_target` | Unknown component/risk/recommendation/dependency |
| `validation_warning` | Output failed guardrails (still returned) |
| `execution_error` | Exception during handling |

---

## CLI Integration (§31)

```bash
# Deterministic pipeline — works with NO LLM configuration
python -m archlens analyze ../examples/fastapi_project -o output

# LLM operations — require ARCHLENS_LLM_PROVIDER + ARCHLENS_LLM_API_KEY
python -m archlens explain architecture -o output
python -m archlens explain summary -o output
python -m archlens explain component module:app.main -o output
python -m archlens explain dependency module:app.main module:app -o output
python -m archlens explain risk high_coupling:module:app.main -o output
python -m archlens explain recommendation reduce_coupling:module:app.main -o output
python -m archlens explain impact module:app.main -o output
python -m archlens explain refactor-plan reduce_coupling:module:app.main -o output
python -m archlens ask "Why is this component central?" -o output
```

Failures exit with code 1 and print a structured error plus suggestions.

---

## API Integration (§30)

FastAPI app (see `backend/app/api.py`). The deterministic artifacts directory
is resolved from `ARCHLENS_ARTIFACTS_DIR`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + `llm_configured` probe |
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
| GET | `/llm/conversations/{id}` | Read a conversation |

The service is cached per artifacts-directory so in-memory conversations persist
across HTTP requests.

---

## Configuration

All LLM configuration is via environment variables:

```bash
ARCHLENS_LLM_PROVIDER=openai   # or "mock" for offline/deterministic use
ARCHLENS_LLM_MODEL=            # e.g. your choice of OpenAI model
ARCHLENS_LLM_API_KEY=          # 1234... (never committed or logged)
ARCHLENS_LLM_BASE_URL=https://api.openai.com/v1
ARCHLENS_LLM_TIMEOUT=30
```

- `is_configured()` requires **both** a provider name **and** an API key.
- The **mock provider** needs no real request; set `ARCHLENS_LLM_PROVIDER=mock`
  and any non-empty `ARCHLENS_LLM_API_KEY` for local development and tests.
- **No model name is hard-coded.** If `ARCHLENS_LLM_MODEL` is unset the
  OpenAI provider returns a clear configuration error; nothing silently falls
  back to a specific vendor model.

---

## Mock Provider (offline development)

`MockLLMProvider` returns deterministic, clearly-labeled content with real
usage/latency metadata. It is what every test uses — **the normal test suite
never makes a real OpenAI request.** Use it locally:

```bash
export ARCHLENS_LLM_PROVIDER=mock
export ARCHLENS_LLM_API_KEY=test-key
python -m archlens ask "What is the architecture?" -o output
```

---

## Files Added/Modified

### New Files
1. **`backend/app/llm/__init__.py`** — LLM package exports
2. **`backend/app/llm/provider.py`** — Abstract provider interface
3. **`backend/app/llm/factory.py`** — Env-driven provider factory
4. **`backend/app/llm/schemas.py`** — Pydantic v2 schemas
5. **`backend/app/llm/context.py`** — VerifiedContextBuilder
6. **`backend/app/llm/prompts.py`** — PromptManager
7. **`backend/app/llm/guardrails.py`** — GroundingGuardrails
8. **`backend/app/llm/service.py`** — LLMService
9. **`backend/app/llm/providers/__init__.py`**
10. **`backend/app/llm/providers/mock_provider.py`** — MockLLMProvider
11. **`backend/app/llm/providers/openai_provider.py`** — OpenAIProvider
12. **`backend/tests/test_phase6_1_provider.py`** — Provider/factory tests
13. **`backend/tests/test_phase6_2_schemas.py`** — Schema tests
14. **`backend/tests/test_phase6_context.py`** — Context builder tests
15. **`backend/tests/test_phase6_4_prompts.py`** — Prompt manager tests
16. **`backend/tests/test_phase6_5_guardrails.py`** — Guardrail tests
17. **`backend/tests/test_phase6_6_service.py`** — Service tests
18. **`backend/tests/test_phase6_integration.py`** — API + CLI integration tests
19. **`backend/tests/conftest.py`** — Shared deterministic artifact fixtures

### Modified Files
1. **`backend/app/cli.py`** — Added `explain` group + `ask` command + LLM service wiring
2. **`backend/app/api.py`** — Added FastAPI app + `/health` + `/llm/*` endpoints
3. **`backend/app/llm/factory.py`** — Model sourced from env only (no hard-coded default)
4. **`backend/app/llm/providers/openai_provider.py`** — Model sourced from env only
5. **`backend/requirements.txt`** — Added FastAPI runtime dependencies
6. **`backend/.env.example`** — Documented `ARCHLENS_LLM_*` variables
7. **`backend/README.md`** — Documented the Architecture Copilot

---

## Backward Compatibility

✅ **100% Backward Compatible**

- All 261 prior tests (Phases 1–5) continue to pass unchanged
- `archlens analyze` deterministic pipeline behavior identical
- All five artifact JSON files unchanged in shape
- The LLM layer is purely additive: optional, env-gated, and skippable
- `python -m archlens analyze` works with **no** LLM configuration

---

## Quality Assurance

### Determinism

- The deterministic pipeline (`analyze`) produces byte-identical artifacts
- With `MockLLMProvider`, the whole copilot pipeline is deterministic and
  fully testable offline

### Security

- API keys never logged, never written to artifacts, never exposed via
  `/llm/status`
- Complete repository contents never logged to the LLM by default
- No hard-coded credentials or model names
- Every LLM HTTP call enforced with a timeout and retry/back-off policy

### Testing (6.17)

153 new tests were added for Phase 6 (context 33, prompts 28, guardrails 29,
service 37, integration 26), all using the deterministic MockLLMProvider:

- ✅ Provider abstraction & factory config
- ✅ Schema validation
- ✅ Verified context construction (components, deps, risks, recommendations)
- ✅ Prompt generation for all 9 operations
- ✅ Guardrail rejection paths (unknown entities, secrets, structure)
- ✅ All 9 operations succeed with mock provider
- ✅ Configuration-error, invalid-target, invalid-operation, execution-error paths
- ✅ Conversation lifecycle incl. `max_history_turns` trimming and history injection
- ✅ API endpoints (health, status, all `/llm/*`, conversations)
- ✅ CLI commands (explain group, ask, no-LLM analyze backward compat)

**Full suite: 414 tests passing, exit 0.**

---

## Success Criteria Validation

| Criterion | Status |
|-----------|--------|
| LLM provider abstraction (interface + OpenAI + mock) | ✅ Yes |
| 9 LLM operations | ✅ Yes |
| Verified context (assertions grounded in artifacts) | ✅ Yes |
| Grounding guardrails (facts, secrets, structure) | ✅ Yes |
| Conversation support with history trimming | ✅ Yes |
| FastAPI endpoints under `/llm/*` | ✅ Yes |
| CLI `explain` / `ask` commands | ✅ Yes |
| Config via env only, no hard-coded model | ✅ Yes |
| Structured errors (never raw exceptions) | ✅ Yes |
| No-LLM deterministic pipeline still works | ✅ Yes |
| Test suite never requires a real OpenAI request | ✅ Yes |
| 100% backward compatible | ✅ Yes |
| All tests passing | ✅ 414/414 |

---

## Conclusion

✅ **Phase 6 is complete, stable, and production-ready.**

ArchLens AI now closes the loop: the deterministic engine (Phases 1–5)
remains the source of truth, and the Architecture Copilot (Phase 6) adds an
optional, guardrailed, conversation-aware LLM layer on top — grounded strictly
in verified facts, configured entirely through the environment, and fully
testable offline via the mock provider. No hard-coded credentials, no
hard-coded model names, no real requests in the normal test suite.

The complete ArchLens pipeline now provides:

1. **What exists?** → `analysis.json` (Phase 1)
2. **How is it connected?** → `graph.json` (Phase 2)
3. **What does it mean?** → `architecture.json` (Phase 3)
4. **Is it healthy?** → `health.json` (Phase 4)
5. **What should change?** → `evolution.json` (Phase 5)
6. **Ask it in plain language** → Architecture Copilot (Phase 6)

**ArchLens AI Phases 1–6 are now complete.**