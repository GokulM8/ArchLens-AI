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

export type AnalysisResponse = AnalysisMetadata & AnalysisResult;

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
  rememberResult(result);
  return result;
}

/** Load a stored analysis (e.g. from a shared /architecture?id= link). */
export async function getAnalysis(analysisId: string): Promise<AnalysisResponse> {
  const result = await request<AnalysisResponse>(`/v1/analyses/${encodeURIComponent(analysisId)}`);
  if (result.status === "completed") rememberResult(result);
  return result;
}

export async function listAnalyses(limit = 50): Promise<AnalysisMetadata[]> {
  if (DEMO_MODE) return [];
  const body = await request<{ items: AnalysisMetadata[] }>(`/v1/analyses?limit=${limit}`);
  return body.items;
}

export async function getArchitectureGraph(analysisId: string): Promise<ArchitectureGraphData> {
  if (DEMO_MODE) return mockGraph;
  return request(`/v1/analyses/${encodeURIComponent(analysisId)}/graph`);
}

export async function getArchitectureHealth(analysisId: string): Promise<ArchitectureHealth> {
  if (DEMO_MODE) return mockHealth;
  return request(`/v1/analyses/${encodeURIComponent(analysisId)}/health`);
}

/** Structural diff from `baselineId` (version A) to `analysisId` (version B). */
export async function getArchitectureDiff(
  analysisId: string,
  baselineId: string,
): Promise<ArchitectureDiffData> {
  if (DEMO_MODE) return mockDiff;
  const params = new URLSearchParams({ baseline: baselineId });
  return request(`/v1/analyses/${encodeURIComponent(analysisId)}/diff?${params}`);
}

function rememberResult(result: AnalysisResponse) {
  setRepoSession({
    repository: result.summary.repository,
    result,
    analyzedAt: new Date(result.completedAt ?? result.createdAt).toLocaleString(),
  });
}
