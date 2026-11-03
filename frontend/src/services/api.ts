import {
  mockAISummary,
  mockDiff,
  mockExplanation,
  mockGraph,
  mockHealth,
  mockSummary,
} from "@/data/mockArchitecture";
import type {
  AIExplanation,
  AnalysisSummary,
  ArchitectureDiffData,
  ArchitectureGraphData,
  ArchitectureHealth,
} from "@/types/architecture";
import { API_BASE, DEMO_MODE } from "@/lib/config";
import { setRepoSession } from "@/lib/repoStore";
import { forgetAccess, getAccessToken, listAccess, rememberAccess } from "@/lib/analysisAccess";

/**
 * Service layer — the single integration seam between the UI and the ArchLens
 * backend. Contract: docs/API.md (`/v1/analyses`).
 *
 * Two explicit modes, chosen at build time:
 *  - backend (default): every call goes to the FastAPI backend; failures are
 *    thrown as ApiError so the UI can show them. Nothing is faked.
 *  - demo (VITE_DEMO_MODE=true): no backend; returns the bundled sample
 *    payloads, flagged with `demo: true` so the UI labels them.
 */

export class ApiError extends Error {
  constructor(
    message: string,
    /** HTTP status, or 0 when the backend could not be reached. */
    readonly status: number,
    readonly code?: string,
    readonly retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface AnalysisRequest {
  /** GitHub URL or uploaded archive name. */
  source: string;
  kind: "git" | "zip";
  /** The actual archive, when the user uploaded one. */
  file?: File | null;
}

export type AnalysisStatus = "running" | "completed" | "failed";

export interface AnalysisMetadata {
  analysisId: string;
  status: AnalysisStatus;
  createdAt: string;
  completedAt: string | null;
  repository: string | null;
  source: { kind: "zip"; filename: string };
  /** true when the analysis succeeded but found no Python modules. */
  empty: boolean;
  error: { code: string; message: string } | null;
}

export interface AnalysisResult {
  analysisId: string;
  summary: AnalysisSummary;
  graph: ArchitectureGraphData;
  health: ArchitectureHealth;
  /** null when there is nothing to explain (empty analysis). */
  explanation: AIExplanation | null;
  /** Deterministic overview paragraphs derived from the artifacts. */
  aiSummary: string[];
  empty: boolean;
  /** true only for bundled sample data in demo mode. */
  demo?: boolean;
}

export type AnalysisResponse = AnalysisMetadata &
  AnalysisResult & {
    /** Returned only by the upload; required for every later read. */
    accessToken?: string;
  };

export interface CopilotStatus {
  enabled: boolean;
  provider: string | null;
  model: string | null;
  configurationError: string | null;
  maxQuestionChars: number;
  disclosure: string;
}

export interface CopilotAnswer {
  analysisId: string;
  question: string;
  answer: string;
  /** false when the guardrails flagged claims they could not match to the analysis. */
  grounded: boolean;
  groundingWarning: string | null;
  provider: string;
  model: string;
  usage: { promptTokens: number; completionTokens: number; totalTokens: number };
  latencyMs: number;
  disclosure: string;
}

const TOKEN_HEADER = "X-ArchLens-Token";
const BASELINE_TOKEN_HEADER = "X-ArchLens-Baseline-Token";

/** Headers proving access to an analysis; throws if this browser has no token for it. */
function accessHeaders(analysisId: string): Record<string, string> {
  const token = getAccessToken(analysisId);
  if (!token)
    throw new ApiError(
      "This analysis is not available in this browser. Analyses can only be opened from the browser that uploaded them.",
      404,
      "analysis_not_found",
    );
  return { [TOKEN_HEADER]: token };
}

/** Forget the local token when the server no longer has the analysis (expired or deleted). */
async function withAccess<T>(analysisId: string, call: () => Promise<T>): Promise<T> {
  try {
    return await call();
  } catch (e) {
    if (e instanceof ApiError && e.status === 404 && e.code === "analysis_not_found") {
      forgetAccess(analysisId);
    }
    throw e;
  }
}

/** The /v1 error shape: `{ detail, code }` (docs/API.md). */
interface ErrorBody {
  detail?: unknown;
  code?: string;
}

/** Fetch JSON, mapping network and HTTP failures onto ApiError. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      `Cannot reach the ArchLens backend (${API_BASE}). Check that it is running.`,
      0,
      "network_error",
    );
  }

  if (response.status === 204) return undefined as T;

  let body: ErrorBody | null = null;
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    body = null;
  }
  if (!response.ok) {
    const gatewayDown = [502, 503, 504].includes(response.status);
    const message =
      typeof body?.detail === "string"
        ? body.detail
        : gatewayDown
          ? `The ArchLens backend is unavailable (HTTP ${response.status}). Check that it is running.`
          : `Request failed (${response.status})`;
    const retryAfter = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
    throw new ApiError(
      message,
      response.status,
      body?.code,
      Number.isFinite(retryAfter) ? retryAfter : undefined,
    );
  }
  if (body === null) {
    throw new ApiError(
      "The backend returned an unreadable response.",
      response.status,
      "bad_response",
    );
  }
  return body as T;
}

function demoResult(repository: string): AnalysisResult {
  return {
    analysisId: "demo",
    summary: { ...mockSummary, repository },
    graph: mockGraph,
    health: mockHealth,
    explanation: mockExplanation,
    aiSummary: mockAISummary,
    empty: false,
    demo: true,
  };
}

export async function analyzeRepository(req: AnalysisRequest): Promise<AnalysisResult> {
  if (DEMO_MODE) {
    const name =
      req.kind === "git"
        ? (req.source.replace(/\/+$/, "").split("/").pop() ?? "repository").replace(/\.git$/, "")
        : req.source.replace(/\.zip$/i, "");
    const result = demoResult(name || "my-project");
    setRepoSession({
      repository: result.summary.repository,
      result,
      analyzedAt: new Date().toLocaleString(),
    });
    return result;
  }

  let init: RequestInit;
  if (req.kind === "zip") {
    if (!req.file) throw new ApiError("Choose a .zip archive to upload.", 400, "validation_error");
    const form = new FormData();
    form.append("kind", "zip");
    form.append("file", req.file);
    init = { method: "POST", body: form };
  } else {
    // The backend answers 501 git_not_supported; surface that message as-is.
    init = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: "git", source: req.source }),
    };
  }

  const result = await request<AnalysisResponse>("/v1/analyses", init);
  if (result.accessToken) {
    rememberAccess({
      analysisId: result.analysisId,
      token: result.accessToken,
      repository: result.repository,
      filename: result.source.filename,
      createdAt: result.createdAt,
      empty: result.empty,
    });
  }
  rememberResult(result);
  return result;
}

/** Load a stored analysis this browser uploaded (e.g. from /architecture?id=). */
export async function getAnalysis(analysisId: string): Promise<AnalysisResponse> {
  const result = await withAccess(analysisId, () =>
    request<AnalysisResponse>(`/v1/analyses/${encodeURIComponent(analysisId)}`, {
      headers: accessHeaders(analysisId),
    }),
  );
  if (result.status === "completed") rememberResult(result);
  return result;
}

/**
 * The analyses uploaded from this browser, newest first. The server has no
 * listing endpoint; entries the server has since expired disappear when opened.
 */
export async function listAnalyses(): Promise<AnalysisMetadata[]> {
  if (DEMO_MODE) return [];
  return listAccess().map((a) => ({
    analysisId: a.analysisId,
    status: "completed",
    createdAt: a.createdAt,
    completedAt: a.createdAt,
    repository: a.repository,
    source: { kind: "zip", filename: a.filename },
    empty: a.empty,
    error: null,
  }));
}

/** Permanently delete an analysis and its stored artifacts from the server. */
export async function deleteAnalysis(analysisId: string): Promise<void> {
  try {
    await request<unknown>(`/v1/analyses/${encodeURIComponent(analysisId)}`, {
      method: "DELETE",
      headers: accessHeaders(analysisId),
    });
  } catch (e) {
    // Already gone on the server: nothing left to delete.
    if (!(e instanceof ApiError && e.status === 404)) throw e;
  }
  forgetAccess(analysisId);
}

export async function getArchitectureGraph(analysisId: string): Promise<ArchitectureGraphData> {
  if (DEMO_MODE) return mockGraph;
  return withAccess(analysisId, () =>
    request(`/v1/analyses/${encodeURIComponent(analysisId)}/graph`, {
      headers: accessHeaders(analysisId),
    }),
  );
}

export async function getArchitectureHealth(analysisId: string): Promise<ArchitectureHealth> {
  if (DEMO_MODE) return mockHealth;
  return withAccess(analysisId, () =>
    request(`/v1/analyses/${encodeURIComponent(analysisId)}/health`, {
      headers: accessHeaders(analysisId),
    }),
  );
}

/** Structural diff from `baselineId` (version A) to `analysisId` (version B). */
export async function getArchitectureDiff(
  analysisId: string,
  baselineId: string,
): Promise<ArchitectureDiffData> {
  if (DEMO_MODE) return mockDiff;
  const params = new URLSearchParams({ baseline: baselineId });
  const baselineToken = accessHeaders(baselineId)[TOKEN_HEADER] ?? "";
  return request(`/v1/analyses/${encodeURIComponent(analysisId)}/diff?${params}`, {
    headers: { ...accessHeaders(analysisId), [BASELINE_TOKEN_HEADER]: baselineToken },
  });
}

export async function getCopilotStatus(): Promise<CopilotStatus> {
  return request("/v1/copilot/status");
}

/** Ask the Architecture Copilot about one analysis (sent to the configured LLM provider). */
export async function askCopilot(analysisId: string, question: string): Promise<CopilotAnswer> {
  return withAccess(analysisId, () =>
    request(`/v1/analyses/${encodeURIComponent(analysisId)}/copilot`, {
      method: "POST",
      headers: { ...accessHeaders(analysisId), "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
  );
}

function rememberResult(result: AnalysisResponse) {
  setRepoSession({
    repository: result.summary.repository,
    result,
    analyzedAt: new Date(result.completedAt ?? result.createdAt).toLocaleString(),
  });
}
