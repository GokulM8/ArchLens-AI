/**
 * Access tokens for the analyses this browser uploaded.
 *
 * The backend returns an analysis's access token once, when it is created, and
 * requires it for every later read (docs/API.md). There is no server-side list
 * of analyses, so this browser-local record is also what "your analyses" shows.
 * Storage can be unavailable (private windows, blocked site data); every access
 * is guarded and the app still works for the current session without it.
 */

export interface AnalysisAccess {
  analysisId: string;
  token: string;
  repository: string | null;
  filename: string;
  createdAt: string;
  empty: boolean;
}

const KEY = "archlens.analyses.v1";
const MAX_ENTRIES = 50;

// Fallback for the current page when localStorage is unavailable.
let memory: AnalysisAccess[] = [];

function read(): AnalysisAccess[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return memory;
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as AnalysisAccess[]) : memory;
  } catch {
    return memory;
  }
}

function write(entries: AnalysisAccess[]) {
  memory = entries;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(entries));
  } catch {
    // Kept in memory only.
  }
}

export function rememberAccess(entry: AnalysisAccess) {
  const rest = read().filter((e) => e.analysisId !== entry.analysisId);
  write([entry, ...rest].slice(0, MAX_ENTRIES));
}

export function getAccessToken(analysisId: string): string | null {
  return read().find((e) => e.analysisId === analysisId)?.token ?? null;
}

export function listAccess(): AnalysisAccess[] {
  return [...read()].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function forgetAccess(analysisId: string) {
  write(read().filter((e) => e.analysisId !== analysisId));
}
