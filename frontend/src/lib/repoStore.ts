import { useSyncExternalStore } from "react";
import type { AnalysisResult } from "@/services/api";

/**
 * Holds the currently open analysis for the session so the dashboard,
 * architecture explorer and document page all read the same result.
 * In-memory only; stored analyses can be reopened from the backend by id.
 */

export interface RepoSession {
  repository: string;
  result: AnalysisResult;
  analyzedAt: string;
}

let session: RepoSession | null = null;
const listeners = new Set<() => void>();

export function setRepoSession(next: RepoSession | null) {
  session = next;
  listeners.forEach((l) => l());
}

export function getRepoSession(): RepoSession | null {
  return session;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useRepoSession(): RepoSession | null {
  return useSyncExternalStore(
    subscribe,
    () => session,
    () => null,
  );
}
