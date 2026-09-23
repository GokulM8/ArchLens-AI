import { useSyncExternalStore } from "react";
import type { RepoIndex } from "@/lib/repoAnalysis";
import type { AnalysisResult } from "@/services/api";

/**
 * Holds the currently analyzed repository for the session so the document page,
 * code explorer and source view all read the same real files.
 */

export interface RepoSession {
  repository: string;
  result: AnalysisResult;
  /** Per-file index from in-browser analysis; null when the backend produced the result. */
  index: RepoIndex | null;
  /** true when the payload came from an uploaded archive, false for the sample. */
  real: boolean;
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

/** Real file content for a path, when a repository has been uploaded. */
export function getFileContent(path?: string): string | null {
  if (!path || !session || !session.index) return null;
  return session.index.files[path]?.content ?? null;
}
