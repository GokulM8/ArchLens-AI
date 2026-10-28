import { useMemo } from "react";
import type { AnalysisResult } from "@/services/api";
import { useRepoSession } from "@/lib/repoStore";

export interface CurrentAnalysis {
  /** null when nothing has been analysed in this session. */
  result: AnalysisResult | null;
  repository: string | null;
  analyzedAt: string | null;
}

/** The analysis the app is currently showing, if any. Never falls back to samples. */
export function useAnalysis(): CurrentAnalysis {
  const session = useRepoSession();

  return useMemo(
    () => ({
      result: session?.result ?? null,
      repository: session?.repository ?? null,
      analyzedAt: session?.analyzedAt ?? null,
    }),
    [session],
  );
}
