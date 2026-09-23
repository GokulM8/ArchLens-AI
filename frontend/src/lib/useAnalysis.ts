import { useMemo } from "react";
import {
  mockAISummary,
  mockExplanation,
  mockGraph,
  mockHealth,
  mockSummary,
} from "@/data/mockArchitecture";
import type { AnalysisResult } from "@/services/api";
import type { RepoIndex } from "@/lib/repoAnalysis";
import { useRepoSession } from "@/lib/repoStore";

export interface CurrentAnalysis {
  result: AnalysisResult;
  index: RepoIndex | null;
  /** true when an uploaded repository is being shown. */
  real: boolean;
  repository: string;
  analyzedAt: string | null;
}

/** The analysis the whole app reads: the uploaded repo, else the sample one. */
export function useAnalysis(): CurrentAnalysis {
  const session = useRepoSession();

  return useMemo(() => {
    if (session)
      return {
        result: session.result,
        index: session.index,
        real: true,
        repository: session.repository,
        analyzedAt: session.analyzedAt,
      };

    return {
      result: {
        summary: mockSummary,
        graph: mockGraph,
        health: mockHealth,
        explanation: mockExplanation,
        aiSummary: mockAISummary,
      },
      index: null,
      real: false,
      repository: mockSummary.repository,
      analyzedAt: null,
    };
  }, [session]);
}
