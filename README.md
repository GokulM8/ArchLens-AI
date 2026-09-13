# ArchLens AI — Python Repository Analyzer + Architecture Copilot

ArchLens AI is a deterministic Python repository analysis engine that reconstructs architecture from source code, plus an **optional** LLM-powered Architecture Copilot that explains and reasons over the results.

The deterministic pipeline (Phases 1–5) produces five fact-only artifacts — `analysis.json`, `graph.json`, `architecture.json`, `health.json`, `evolution.json` — with **no AI and no configuration required**. The Architecture Copilot (Phase 6) adds explanations, summaries, risk analysis, and refactoring plans over those artifacts via an optional, env-gated LLM layer. **The deterministic engine is the source of truth; the LLM is an explanation, synthesis, and reasoning layer.**

## Quick start

### Prerequisites

```bash
# Clone the repository
git clone <repo-url>
cd ArchLens-AI

# Navigate to backend directory
cd backend

# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies  
pip install -r requirements-dev.txt
```

### Docker Deployment (Recommended)

#### Using Docker Compose

```bash
# Build and start all services
cd /path/to/ArchLens-AI
docker-compose up --build -d

# Or build just the backend service
docker-compose build archlens-backend
docker-compose up archlens-backend -d
```

#### Using Dockerfile directly

```bash
# Build the backend image
cd backend
docker build -t archlens-backend .

# Run with environment variables
docker run -p 8000:8000 \
  -e ARCHLENS_ARTIFACTS_DIR=/app/output \
  -e ARCHLENS_LLM_PROVIDER=mock \
  -e ARCHLENS_LLM_API_KEY=test-key \
  archlens-backend
```

#### Environment Configuration

Create a `.env` file in the backend directory:

```bash
# Required
ARCHLENS_ARTIFACTS_DIR=/app/output
ARCHLENS_LLM_PROVIDER=mock
ARCHLENS_LLM_API_KEY=test-key

# Optional (uncomment and configure for production)
# ARCHLENS_LLM_PROVIDER=openai
# ARCHLENS_LLM_MODEL=gpt-4
# ARCHLENS_LLM_API_KEY=your-openai-api-key
# ARCHLENS_LLM_BASE_URL=https://api.openai.com/v1
# ARCHLENS_LLM_TIMEOUT=30
```

### Local Development

```bash
# Analyze the example FastAPI project (produces all five artifacts)
cd backend
python -m archlens analyze ../examples/fastapi_project -o output

# Run the test suite
python -m pytest

# Run a specific test
python -m pytest tests/test_phase6_integration.py -v
```

### API Testing

```bash
# Start the FastAPI server
cd backend
uvicorn app.api:app --host 0.0.0.0 --port 8000

# Test with curl
# Health check
curl -X GET http://localhost:8000/health

# Ask architecture question
curl -X POST http://localhost:8000/llm/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the architecture?"}'
```

## Architecture Copilot (optional LLM layer)

The copilot explains, summarizes, and reasons over the five deterministic artifacts. It is **entirely optional and env-gated** — the deterministic pipeline above runs with no LLM configuration.

### Configuration

All config is via environment variables — no hard-coded credentials or model names anywhere:

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

---

## Production Deployment Checklist

### Docker Compose Setup

1. **Copy .env.example to .env**
2. **Set required environment variables**:
   - `ARCHLENS_ARTIFACTS_DIR`: Path to output directory
   - `ARCHLENS_LLM_PROVIDER`: "mock" (development) or "openai" (production)
   - `ARCHLENS_LLM_API_KEY`: Your LLM API key
3. **Mount persistent volumes** for:
   - Application code (optional, for development)
   - Output directory (essential for data persistence)
4. **Configure networking**:
   - Expose port 8000
   - Configure domain and SSL (if using nginx)

### Docker Swarm/Kubernetes Deployment

```yaml
# Example Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: archlens-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: archlens-backend
  template:
    metadata:
      labels:
        app: archlens-backend
    spec:
      containers:
      - name: archlens-backend
        image: archlens-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: ARCHLENS_ARTIFACTS_DIR
          value: "/app/output"
        - name: ARCHLENS_LLM_PROVIDER
          value: "mock"
        - name: ARCHLENS_LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: archlens-secrets
              key: api-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        volumeMounts:
        - name: output-volume
          mountPath: /app/output
      volumes:
      - name: output-volume
        persistentVolumeClaim:
          claimName: archlens-output-pvc
```

### Monitoring and Logging

1. **Health checks**: All services include health endpoints
2. **Application logging**: Structured logs to stdout/stderr
3. **Infrastructure monitoring**:
   - Prometheus metrics (implement if required)
   - Grafana dashboards
4. **Log aggregation**: ELK stack or similar

### Backup and Recovery

1. **Backup strategies**:
   - Container image snapshots
   - Database backups (if applicable)
   - Configuration file backups
2. **Disaster recovery**:
   - Multi-zone deployment
   - Automated failover
   - Backup and restore procedures

### Security Hardening

1. **Network security**:
   - Firewall rules
   - TLS/SSL encryption
   - VPN access if needed
2. **Application security**:
   - Environment variable security
   - Container security
   - API authentication (if applicable)
3. **Regular updates**:
   - Base image updates
   - Application updates
   - Security patches

## FAQ

### What are the system requirements?

- **Docker**: Required for containerized deployment
- **Memory**: 512MB RAM minimum, 1GB RAM recommended
- **Storage**: 1GB free space for application and output

### Can I run ArchLens AI without Docker?

Yes, but Docker is recommended for production. For development:

```bash
cd backend
pip install -r requirements.txt
python -m archlens analyze /path/to/repo -o output
```

### What ports does ArchLens AI use?

- **Backend API**: 8000 (configurable via docker-compose)
- **Nginx (optional)**: 80, 443
- **Redis (optional)**: 6379

### How do I configure LLM providers?

See the Configuration section above. The system supports:
- **Mock provider**: For development and testing
- **OpenAI provider**: For production use

### What are the performance characteristics?

- **Memory usage**: ~100MB for the application
- **CPU usage**: Minimal for analysis operations
- **Network usage**: Depends on LLM provider
- **Storage**: Depends on repository size being analyzed

### How do I scale ArchLens AI?

1. **Horizontal scaling**: Multiple container instances
2. **Load balancing**: Nginx or Kubernetes Ingress
3. **Caching**: Redis for session data
4. **Queueing**: Celery for long-running analyses

## License

Apache 2.0

## Contributing

See CONTRIBUTING.md for contribution guidelines.

---

*This README was last updated on 2026-09-13*

---

## Resources

- [Project Documentation](/documentation/)
- [API Reference](https://docs.archlens.ai/api)
- [Docker Hub Repository](https://hub.docker.com/r/archlens/backend)
- [Slack Community](https://archlens.ai/slack)
- [GitHub Issues](https://github.com/archlens-ai/ArchLens-AI/issues)