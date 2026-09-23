import type {
  AIExplanation,
  AnalysisStage,
  AnalysisSummary,
  ArchitectureDiffData,
  ArchitectureGraphData,
  ArchitectureHealth,
} from "@/types/architecture";

/**
 * Mock payloads shaped exactly like the future backend responses
 * (analysis.json / graph.json / health.json / diff.json).
 * Replace with API results via src/services/api.ts — no UI changes required.
 */

export const mockGraph: ArchitectureGraphData = {
  nodes: [
    {
      id: "web",
      type: "client",
      label: "React App",
      description: "Browser client. Renders dashboards and issues authenticated API calls.",
      confidence: 0.99,
      position: { x: 0, y: 250 },
      metadata: {
        dependencies: ["src/api/client.ts", "src/hooks/useSession.ts"],
        consumers: ["—"],
        sourcePath: "web/src/main.tsx",
        lines: [1, 64],
        dependencyCount: 21,
        consumerCount: 0,
        snippetLanguage: "tsx",
        snippetStart: 12,
        snippet: [
          'import { apiClient } from "./api/client";',
          'import { useSession } from "./hooks/useSession";',
          "",
          "export function App() {",
          "  const { token } = useSession();",
          "  const { data } = useQuery({",
          '    queryKey: ["predictions"],',
          '    queryFn: () => apiClient.get("/v1/predictions", token),',
          "  });",
          "  return <Dashboard predictions={data} />;",
          "}",
        ].join("\n"),
        snippetSignals: [
          "Renders UI and holds no persistence logic → client",
          "Only outbound calls go through apiClient → depends on the gateway",
        ],
      },
    },
    {
      id: "gateway",
      type: "gateway",
      label: "API Gateway",
      description: "Edge router. Terminates TLS, applies rate limits and forwards to FastAPI.",
      confidence: 0.96,
      position: { x: 200, y: 250 },
      metadata: {
        dependencies: ["gateway/routes.yaml"],
        consumers: ["GET /v1/*", "POST /v1/*"],
        sourcePath: "infra/gateway/config.yaml",
        lines: [1, 118],
        dependencyCount: 4,
        consumerCount: 1,
        snippetLanguage: "yaml",
        snippetStart: 22,
        snippet: [
          "routes:",
          "  - match: /v1/*",
          "    upstream: http://fastapi-core:8000",
          "    rate_limit: 100r/m",
          "    tls:",
          "      terminate: true",
          "  - match: /health",
          "    upstream: http://fastapi-core:8000/health",
        ].join("\n"),
        snippetSignals: [
          "TLS termination + rate limits at the edge → gateway",
          "Single upstream target → forwards everything to FastAPI Core",
        ],
      },
    },
    {
      id: "api",
      type: "service",
      label: "FastAPI Core",
      description: "HTTP layer. Owns request validation, routing and dependency injection.",
      confidence: 0.97,
      position: { x: 400, y: 250 },
      metadata: {
        dependencies: ["routers/predict.py", "routers/auth.py", "deps.py"],
        consumers: ["POST /predict", "POST /batch-predict", "POST /login"],
        sourcePath: "app/main.py",
        lines: [1, 212],
        dependencyCount: 18,
        consumerCount: 3,
        snippetLanguage: "python",
        snippetStart: 34,
        snippet: [
          "app = FastAPI(title='ArchLens Demo API')",
          "",
          "from .routers import auth, predict",
          "",
          'app.include_router(auth.router, prefix="/login", tags=["auth"])',
          'app.include_router(predict.router, prefix="/predict", tags=["ml"])',
          "",
          '@app.post("/predict")',
          "async def predict(payload: PredictIn, user = Depends(current_user)):",
          "    return await prediction_service.run(payload, user)",
        ].join("\n"),
        snippetSignals: [
          "Declares routers and request validation only → HTTP layer",
          "Delegates work to prediction_service → imports the service layer",
        ],
      },
    },
    {
      id: "auth",
      type: "service",
      label: "Auth Service",
      description: "Issues and verifies JWTs, manages sessions and permission checks.",
      confidence: 0.92,
      position: { x: 600, y: 80 },
      metadata: {
        dependencies: ["tokens.py", "database.py"],
        consumers: ["POST /login", "POST /refresh"],
        sourcePath: "services/auth.py",
        lines: [14, 161],
        dependencyCount: 9,
        consumerCount: 2,
        snippetLanguage: "python",
        snippetStart: 41,
        snippet: [
          "def issue_token(user: User) -> str:",
          '    claims = {"sub": str(user.id), "exp": expiry(minutes=30)}',
          "    return jwt.encode(claims, settings.secret, algorithm='HS256')",
          "",
          "async def load_session(token: str) -> Session | None:",
          '    cached = await redis.get(f"session:{token}")',
          "    if cached:",
          "        return Session.parse_raw(cached)",
          "    return await db.fetch_session(token)",
        ].join("\n"),
        snippetSignals: [
          "Signs and verifies JWTs → authentication responsibility",
          "Reads redis before db → cache-aside session lookup",
        ],
      },
    },
    {
      id: "prediction",
      type: "service",
      label: "Prediction Service",
      description: "Handles model inference and prediction requests.",
      confidence: 0.94,
      position: { x: 600, y: 410 },
      metadata: {
        dependencies: ["model.py", "preprocessing.py", "database.py"],
        consumers: ["POST /predict", "POST /batch-predict"],
        sourcePath: "services/prediction.py",
        lines: [21, 184],
        dependencyCount: 14,
        consumerCount: 3,
        snippetLanguage: "python",
        snippetStart: 88,
        snippet: [
          "async def run(payload: PredictIn, user: User) -> PredictOut:",
          "    features = preprocessing.normalize(payload.features)",
          "    score = model.predict(features)          # line 88",
          "    await redis.setex(cache_key(payload), 300, score)",
          "    await db.insert_prediction(user.id, score)",
          "    return PredictOut(score=score)",
        ].join("\n"),
        snippetSignals: [
          "model.predict called at line 88 → owns inference",
          "Writes to both redis and db → cache + datastore dependency",
        ],
      },
    },
    {
      id: "preprocessing",
      type: "module",
      label: "Preprocessing",
      description: "Feature engineering and input normalization shared by inference paths.",
      confidence: 0.88,
      position: { x: 800, y: 470 },
      metadata: {
        dependencies: ["schemas.py"],
        consumers: ["services/prediction.py"],
        sourcePath: "ml/preprocessing.py",
        lines: [1, 96],
        dependencyCount: 3,
        consumerCount: 2,
        snippetLanguage: "python",
        snippetStart: 18,
        snippet: [
          "def normalize(features: dict) -> np.ndarray:",
          "    frame = pd.DataFrame([features])",
          "    frame = frame.fillna(COLUMN_DEFAULTS)",
          "    scaled = (frame[NUMERIC] - MEANS) / STDS",
          "    return np.hstack([scaled.values, one_hot(frame[CATEGORICAL])])",
        ].join("\n"),
        snippetSignals: [
          "Pure transforms, no I/O → shared module, not a service",
          "Imported by prediction only → single consumer",
        ],
      },
    },
    {
      id: "model",
      type: "model",
      label: "ML Model",
      description: "Serialized gradient-boosted model loaded once per worker process.",
      confidence: 0.91,
      position: { x: 800, y: 330 },
      metadata: {
        dependencies: ["artifacts/model.pkl"],
        consumers: ["services/prediction.py"],
        sourcePath: "ml/model.py",
        lines: [8, 74],
        dependencyCount: 2,
        consumerCount: 1,
        snippetLanguage: "python",
        snippetStart: 8,
        snippet: [
          "@lru_cache(maxsize=1)",
          "def load_model() -> GradientBoostingClassifier:",
          '    with open(ARTIFACT_PATH, "rb") as handle:',
          "        return pickle.load(handle)",
          "",
          "def predict(features: np.ndarray) -> float:",
          "    return float(load_model().predict_proba(features)[0][1])",
        ].join("\n"),
        snippetSignals: [
          "Loads a serialized artifact once per process → model",
          "No network or db access → leaf of the dependency graph",
        ],
      },
    },
    {
      id: "cache",
      type: "cache",
      label: "Redis",
      description: "Caches inference results and session lookups.",
      confidence: 0.86,
      position: { x: 800, y: 30 },
      metadata: {
        dependencies: [],
        consumers: ["services/auth.py", "services/prediction.py"],
        sourcePath: "infra/redis.py",
        lines: [1, 42],
        dependencyCount: 1,
        consumerCount: 2,
        snippetLanguage: "python",
        snippetStart: 6,
        snippet: [
          "redis = Redis.from_url(settings.redis_url, decode_responses=True)",
          "",
          "async def get(key: str) -> str | None:",
          "    return await redis.get(key)",
          "",
          "async def setex(key: str, ttl: int, value: float) -> None:",
          "    await redis.set(key, value, ex=ttl)",
        ].join("\n"),
        snippetSignals: [
          "Key/value access with TTLs → cache, not a datastore",
          "Used by auth and prediction → shared latency layer",
        ],
      },
    },
    {
      id: "postgres",
      type: "datastore",
      label: "PostgreSQL",
      description: "Primary relational store for users, predictions and audit history.",
      confidence: 0.98,
      position: { x: 1000, y: 250 },
      metadata: {
        dependencies: ["migrations/"],
        consumers: ["services/auth.py", "services/prediction.py"],
        sourcePath: "db/session.py",
        lines: [1, 58],
        dependencyCount: 1,
        consumerCount: 4,
        snippetLanguage: "python",
        snippetStart: 11,
        snippet: [
          "engine = create_async_engine(settings.database_url, pool_size=10)",
          "SessionLocal = async_sessionmaker(engine, expire_on_commit=False)",
          "",
          "async def insert_prediction(user_id: UUID, score: float) -> None:",
          "    async with SessionLocal() as session:",
          "        session.add(Prediction(user_id=user_id, score=score))",
          "        await session.commit()",
        ].join("\n"),
        snippetSignals: [
          "Owns the SQLAlchemy engine and schema → system of record",
          "Written by prediction, queried by auth → 4 consumers",
        ],
      },
    },
  ],
  edges: [
    { id: "e1", source: "web", target: "gateway", type: "calls", confidence: 0.99 },
    { id: "e2", source: "gateway", target: "api", type: "calls", confidence: 0.97 },
    { id: "e3", source: "api", target: "auth", type: "imports", confidence: 0.95 },
    { id: "e4", source: "api", target: "prediction", type: "imports", confidence: 0.96 },
    { id: "e5", source: "prediction", target: "model", type: "imports", confidence: 0.93 },
    { id: "e6", source: "prediction", target: "preprocessing", type: "imports", confidence: 0.9 },
    { id: "e7", source: "auth", target: "cache", type: "reads", confidence: 0.84 },
    { id: "e8", source: "auth", target: "postgres", type: "queries", confidence: 0.94 },
    { id: "e9", source: "prediction", target: "postgres", type: "writes", confidence: 0.92 },
    { id: "e10", source: "prediction", target: "cache", type: "writes", confidence: 0.81 },
  ],
};

/** Compact graph used for the hero and background ambience. */
export const heroGraph: ArchitectureGraphData = {
  nodes: [
    { id: "frontend", type: "client", label: "FRONTEND", position: { x: 0.12, y: 0.5 } },
    { id: "api", type: "gateway", label: "API SERVICE", position: { x: 0.37, y: 0.5 } },
    { id: "auth", type: "service", label: "AUTH", position: { x: 0.64, y: 0.19 } },
    { id: "users", type: "service", label: "USERS", position: { x: 0.64, y: 0.5 } },
    { id: "ml", type: "service", label: "PREDICTION", position: { x: 0.64, y: 0.81 } },
    { id: "db", type: "datastore", label: "DATABASE", position: { x: 0.88, y: 0.5 } },
  ],
  edges: [
    { id: "h1", source: "frontend", target: "api", type: "calls" },
    { id: "h2", source: "api", target: "auth", type: "imports" },
    { id: "h3", source: "api", target: "users", type: "imports" },
    { id: "h4", source: "api", target: "ml", type: "imports" },
    { id: "h5", source: "ml", target: "db", type: "queries" },
    { id: "h6", source: "users", target: "db", type: "queries" },
    { id: "h7", source: "auth", target: "db", type: "queries" },
  ],
};

export const heroNodeFacts: Record<
  string,
  { type: string; dependencies: number; consumers: number; confidence: number }
> = {
  frontend: { type: "Client", dependencies: 21, consumers: 0, confidence: 0.99 },
  api: { type: "Gateway", dependencies: 18, consumers: 1, confidence: 0.97 },
  auth: { type: "Service", dependencies: 9, consumers: 2, confidence: 0.92 },
  users: { type: "Service", dependencies: 11, consumers: 4, confidence: 0.89 },
  ml: { type: "Service", dependencies: 14, consumers: 3, confidence: 0.94 },
  db: { type: "Datastore", dependencies: 1, consumers: 4, confidence: 0.98 },
};

export const mockSummary: AnalysisSummary = {
  repository: "my-project",
  branch: "main",
  filesScanned: 1284,
  modules: 43,
  apiRoutes: 18,
  externalServices: 7,
  circularDependencies: 2,
  languages: [
    { name: "Python", share: 0.58 },
    { name: "TypeScript", share: 0.31 },
    { name: "SQL", share: 0.07 },
    { name: "Docker", share: 0.04 },
  ],
};

export const analysisStages: AnalysisStage[] = [
  { id: "load", label: "Repository loaded", detail: "my-project @ main · 4.2 MB" },
  { id: "scan", label: "Scanning files", detail: "1,284 files · 43 packages" },
  { id: "parse", label: "Parsing source code", detail: "AST built for 812 Python modules" },
  { id: "imports", label: "Detecting imports", detail: "3,940 import edges resolved" },
  { id: "routes", label: "Finding API routes", detail: "18 routes across 4 routers" },
  { id: "graph", label: "Building dependency graph", detail: "9 architectural components" },
  { id: "infer", label: "Inferring architecture", detail: "layer classification + confidence" },
  { id: "health", label: "Calculating architecture health", detail: "coupling · depth · cycles" },
];

export const mockHealth: ArchitectureHealth = {
  score: 82,
  grade: "GOOD",
  strengths: ["Clear API boundaries", "Low dependency depth", "Modular service layer"],
  warnings: ["Circular dependency: auth ↔ session", "High coupling in auth/"],
  metrics: [
    { key: "coupling", label: "Coupling", value: 34, score: 66, unit: "%", hint: "cross-module edges" },
    { key: "depth", label: "Dependency depth", value: 4, score: 84, hint: "max import chain" },
    { key: "complexity", label: "Complexity", value: 21, score: 74, hint: "avg cyclomatic" },
    { key: "cycles", label: "Circular dependencies", value: 2, score: 58, hint: "detected cycles" },
  ],
};

export const mockExplanation: AIExplanation = {
  nodeId: "prediction",
  question: "Why is this a service?",
  verdict:
    "ArchLens identified Prediction Service as a service-layer component based on concrete code evidence.",
  evidence: [
    "Imported by 3 API routes in app/routers/predict.py",
    "Contains model inference logic (model.predict called at line 88)",
    "Depends on preprocessing for feature normalization",
    "Called by prediction endpoints, never by the data layer",
  ],
  confidence: 0.94,
};

export const mockAISummary = [
  "This repository is a Python service backend with a React client. Requests enter through an API gateway and terminate in a FastAPI application that delegates to two service-layer components: authentication and prediction.",
  "Machine-learning concerns are correctly isolated — inference lives behind Prediction Service and never leaks into routers. Redis is used for both session lookups and inference caching, which is the main coupling risk in the current design.",
];

const diffA: ArchitectureGraphData = {
  nodes: [
    { id: "fe", type: "client", label: "Frontend", position: { x: 0.12, y: 0.5 } },
    { id: "api", type: "service", label: "API", position: { x: 0.5, y: 0.5 } },
    { id: "pg", type: "datastore", label: "PostgreSQL", position: { x: 0.88, y: 0.5 } },
  ],
  edges: [
    { id: "a1", source: "fe", target: "api", type: "calls" },
    { id: "a2", source: "api", target: "pg", type: "queries" },
  ],
};

const diffB: ArchitectureGraphData = {
  nodes: [
    { id: "fe", type: "client", label: "Frontend", position: { x: 0.1, y: 0.5 } },
    { id: "api", type: "service", label: "API", position: { x: 0.37, y: 0.5 } },
    { id: "reco", type: "service", label: "Recommendation", position: { x: 0.66, y: 0.8 } },
    { id: "redis", type: "cache", label: "Redis", position: { x: 0.66, y: 0.2 } },
    { id: "pg", type: "datastore", label: "PostgreSQL", position: { x: 0.92, y: 0.5 } },
  ],
  edges: [
    { id: "b1", source: "fe", target: "api", type: "calls" },
    { id: "b2", source: "api", target: "redis", type: "reads" },
    { id: "b3", source: "api", target: "reco", type: "imports" },
    { id: "b4", source: "redis", target: "pg", type: "queries" },
    { id: "b5", source: "reco", target: "pg", type: "queries" },
  ],
};

export const mockDiff: ArchitectureDiffData = {
  versionA: { label: "VERSION A", graph: diffA },
  versionB: { label: "VERSION B", graph: diffB },
  changes: [
    { kind: "added", label: "Redis Cache", detail: "infra/redis.py · 1 new dependency edge" },
    { kind: "added", label: "Recommendation Service", detail: "services/reco.py · 2 routes" },
    { kind: "modified", label: "API Service", detail: "reads now routed through cache layer" },
    { kind: "removed", label: "Legacy Auth", detail: "services/auth_v1.py deleted" },
  ],
};

export const supportedTechnologies = [
  { name: "Python", note: "AST + import graph" },
  { name: "FastAPI", note: "route inference" },
  { name: "Flask", note: "blueprint mapping" },
  { name: "React", note: "component graph" },
  { name: "Next.js", note: "route conventions" },
  { name: "Node.js", note: "module resolution" },
  { name: "TypeScript", note: "type-aware edges" },
  { name: "PostgreSQL", note: "schema linkage" },
  { name: "Redis", note: "cache detection" },
  { name: "Docker", note: "service topology" },
];

export const pipelineStages = [
  { id: "repo", label: "Repository", detail: "Clone or ZIP upload" },
  { id: "ast", label: "AST Analysis", detail: "Deterministic parse per language" },
  { id: "deps", label: "Dependency Graph", detail: "Import + call resolution" },
  { id: "infer", label: "Architecture Inference", detail: "Layer + role classification" },
  { id: "ai", label: "AI Understanding", detail: "Grounded natural-language reasoning" },
];
