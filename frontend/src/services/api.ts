import {
  analysisStages,
  mockAISummary,
  mockDiff,
  mockExplanation,
  mockGraph,
  mockHealth,
  mockSummary,
} from "@/data/mockArchitecture";
import type {
  AIExplanation,
  AnalysisStage,
  AnalysisSummary,
  ArchitectureDiffData,
  ArchitectureGraphData,
  ArchitectureHealth,
} from "@/types/architecture";
import { ingestArchive } from "@/lib/repoIngest";
import { analyzeRepository as analyzeFiles } from "@/lib/repoAnalysis";
import { setRepoSession } from "@/lib/repoStore";

/**
 * Service layer — the single integration seam between the UI and the ArchLens
 * backend (see FRONTEND_SPEC.md §2).
 *
 * Priority: call the FastAPI backend (POST /v1/analyses for a ZIP upload,
 * GET /v1/analyses/:id/graph|health|diff). If the backend is unreachable the
 * previous in-browser behavior takes over so the app still works standalone.
 * The returned shapes are identical either way, so components never change.
 */

/** Relative path through the Vite dev proxy, or a full base URL override
 *  (VITE_API_BASE_URL) for a backend on a different origin. */
const API_BASE =
  (import.meta.env['VITE_API_BASE_URL'] as string | undefined) ?? "/api";

/** Latest analysis id returned by the backend, needed by graph/health/diff fetches. */
let lastAnalysisId: string | null = null;

class NetworkError extends Error {}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Parse a fetch response as JSON, throwing the backend's `detail` on errors. */
async function readJson<T>(response: Response): Promise<T> {
  let body: any = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const message =
      body && typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`;
    const retryAfter = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
    throw new ApiError(message, response.status, Number.isFinite(retryAfter) ? retryAfter : undefined);
  }
  return body as T;
}

export interface AnalysisRequest {
  /** GitHub URL or uploaded archive name. */
  source: string;
  kind: "git" | "zip";
  /** The actual archive, when the user uploaded one. */
  file?: File | null;
}

export interface AnalysisResult {
  summary: AnalysisSummary;
  graph: ArchitectureGraphData;
  health: ArchitectureHealth;
  explanation: AIExplanation;
  aiSummary: string[];
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Repository / analysis id the backend stored (used by the sub-resource calls). */
export function getLastAnalysisId(): string | null {
  return lastAnalysisId;
}

export async function getArchitectureGraph(): Promise<ArchitectureGraphData> {
  if (lastAnalysisId) {
    try {
      const response = await fetch(`${API_BASE}/v1/analyses/${lastAnalysisId}/graph`);
      return await readJson<ArchitectureGraphData>(response);
    } catch {
      // Backend unreachable — fall back to the sample graph.
    }
  }
  return mockGraph;
}

export async function getArchitectureHealth(): Promise<ArchitectureHealth> {
  if (lastAnalysisId) {
    try {
      const response = await fetch(`${API_BASE}/v1/analyses/${lastAnalysisId}/health`);
      return await readJson<ArchitectureHealth>(response);
    } catch {
      // Backend unreachable — fall back to the sample health.
    }
  }
  return mockHealth;
}

export async function getArchitectureDiff(
  from?: string,
  to?: string,
): Promise<ArchitectureDiffData> {
  const fromId = from ?? lastAnalysisId;
  const toId = to ?? lastAnalysisId;
  if (fromId && toId && fromId !== toId) {
    try {
      const params = new URLSearchParams({ from_analysis: fromId, to_analysis: toId });
      const response = await fetch(
        `${API_BASE}/v1/analyses/${lastAnalysisId ?? toId}/diff?${params}`,
      );
      return await readJson<ArchitectureDiffData>(response);
    } catch {
      // Backend unreachable — fall back to the sample diff.
    }
  }
  return mockDiff;
}

export function getAnalysisStages(): AnalysisStage[] {
  return analysisStages;
}

export async function analyzeRepository(request: AnalysisRequest): Promise<AnalysisResult> {
  // Backend path (preferred): upload the archive, let the server analyse it.
  if (request.kind === "zip" && request.file) {
    try {
      return await analyzeViaBackend(request);
    } catch (error) {
      if (!(error instanceof NetworkError)) throw error; // real server error — surface it
      // Backend unreachable → analyse in the browser, as before.
    }
  } else if (request.kind === "git") {
    // The backend intentionally rejects GitHub URLs (no cloning/auth yet). Try it
    // anyway so a future backend lights up, but keep the sample fallback for 501/offline.
    try {
      return await analyzeViaBackend(request);
    } catch (error) {
      if (error instanceof NetworkError) {
        // offline → sample fallback below
      } else if (error instanceof Error && /not enabled|501/i.test(error.message)) {
        // backend says git is unsupported → sample fallback below
      } else {
        throw error;
      }
    }
  }

  // Fallback: in-browser analysis for archives, mock payload for git URLs.
  if (request.kind === "zip" && request.file) {
    const { repository, files } = await ingestArchive(request.file);
    const { result, index } = analyzeFiles(repository, files);
    setRepoSession({
      repository,
      result,
      index,
      real: true,
      analyzedAt: new Date().toLocaleString(),
    });
    return result;
  }

  await delay(300);
  const name =
    request.kind === "git"
      ? (request.source.replace(/\/+$/, "").split("/").pop() ?? "repository").replace(/\.git$/, "")
      : request.source.replace(/\.zip$/i, "");

  const result: AnalysisResult = {
    summary: { ...mockSummary, repository: name || "my-project" },
    graph: mockGraph,
    health: mockHealth,
    explanation: mockExplanation,
    aiSummary: mockAISummary,
  };

  setRepoSession(null);
  return result;
}

/** POST the archive (or git URL) to the backend and adapt its payload. */
async function analyzeViaBackend(request: AnalysisRequest): Promise<AnalysisResult> {
  let response: Response;
  if (request.kind === "zip" && request.file) {
    const form = new FormData();
    form.append("kind", "zip");
    form.append("file", request.file);
    try {
      response = await fetch(`${API_BASE}/v1/analyses`, { method: "POST", body: form });
    } catch {
      throw new NetworkError("Backend unreachable");
    }
  } else {
    try {
      response = await fetch(`${API_BASE}/v1/analyses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "git", source: request.source }),
      });
    } catch {
      throw new NetworkError("Backend unreachable");
    }
  }

  const body = await readJson<{
    analysisId: string;
    summary: AnalysisSummary;
    graph: ArchitectureGraphData;
    health: ArchitectureHealth;
    explanation: AIExplanation;
    aiSummary: string[];
  }>(response);

  lastAnalysisId = body.analysisId;
  const result: AnalysisResult = {
    summary: body.summary,
    graph: body.graph,
    health: body.health,
    explanation: body.explanation,
    aiSummary: body.aiSummary,
  };

  // A backend result has no per-file index in the session (the server does not
  // return raw sources); the source viewer just disables "whole file" mode.
  setRepoSession({
    repository: result.summary.repository,
    result,
    index: null,
    real: true,
    analyzedAt: new Date().toLocaleString(),
  });
  return result;
}