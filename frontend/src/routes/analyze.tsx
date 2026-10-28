import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { RepositoryInput } from "@/components/analyze/RepositoryInput";
import { AnalysisProgress } from "@/components/analyze/AnalysisProgress";
import { ResultDashboard } from "@/components/analyze/ResultDashboard";
import { analyzeRepository, ApiError, type AnalysisResult } from "@/services/api";

export const Route = createFileRoute("/analyze")({
  head: () => ({
    meta: [
      { title: "Analyze a repository — ArchLens AI" },
      {
        name: "description",
        content:
          "Upload a ZIP of a Python repository and ArchLens reconstructs its architecture graph, health score and summary.",
      },
      { property: "og:title", content: "Analyze a repository — ArchLens AI" },
      {
        property: "og:description",
        content: "Repository in, architecture map out: dependency graph, health score and summary.",
      },
    ],
  }),
  component: AnalyzePage,
});

type Phase = "input" | "progress" | "result";

function AnalyzePage() {
  const [phase, setPhase] = useState<Phase>("input");
  const [repository, setRepository] = useState("my-project");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);
  const [lastRequest, setLastRequest] = useState<{
    source: string;
    kind: "git" | "zip";
    file?: File | null;
  } | null>(null);

  const start = useCallback(async (source: string, kind: "git" | "zip", file?: File | null) => {
    setError(null);
    setRetryAfter(null);
    setLastRequest({ source, kind, file: file ?? null });
    setRepository(source.replace(/^https?:\/\//, ""));
    setPhase("progress");
    try {
      const analysis = await analyzeRepository({ source, kind, file: file ?? null });
      setRepository(analysis.summary.repository);
      setResult(analysis);
      setPhase("result");
    } catch (e) {
      setError(e instanceof Error ? e.message : "The analysis request failed.");
      setRetryAfter(e instanceof ApiError && e.status === 429 ? (e.retryAfter ?? 60) : null);
      setPhase("input");
    }
  }, []);

  useEffect(() => {
    if (retryAfter === null || retryAfter <= 0) return;
    const timer = window.setInterval(() => {
      setRetryAfter((current) => (current && current > 1 ? current - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [retryAfter]);

  return (
    <section className="noise-texture relative min-h-screen pt-28 pb-24 sm:pt-36">
      <div className="grid-texture pointer-events-none absolute inset-0 [mask-image:radial-gradient(70%_50%_at_50%_0%,black,transparent)]" />
      <div className="relative mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {(["Input", "Analysis", "Architecture"] as const).map((label, i) => {
            const index = phase === "input" ? 0 : phase === "progress" ? 1 : 2;
            return (
              <span key={label} className="flex items-center gap-6">
                <span
                  className={`font-mono text-[0.68rem] tracking-[0.2em] uppercase ${
                    i <= index ? "text-accent" : "text-subtle"
                  }`}
                >
                  {String(i + 1).padStart(2, "0")} {label}
                </span>
                {i < 2 && (
                  <span aria-hidden className="font-mono text-[0.68rem] text-border-strong">
                    →
                  </span>
                )}
              </span>
            );
          })}
        </div>

        <div className="mt-10">
          {phase === "input" && (
            <>
              {error && (
                <p
                  role="alert"
                  className="mx-auto mb-4 max-w-2xl rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 font-mono text-[0.75rem] text-destructive"
                >
                  {error}
                  {retryAfter !== null && lastRequest && (
                    <button
                      type="button"
                      disabled={retryAfter > 0}
                      onClick={() =>
                        void start(lastRequest.source, lastRequest.kind, lastRequest.file)
                      }
                      className="mt-3 block underline underline-offset-4 disabled:no-underline disabled:opacity-60"
                    >
                      {retryAfter > 0 ? `Retry in ${retryAfter}s` : "Retry analysis"}
                    </button>
                  )}
                </p>
              )}
              <RepositoryInput onSubmit={start} />
            </>
          )}
          {phase === "progress" && <AnalysisProgress repository={repository} />}
          {phase === "result" && result && (
            <ResultDashboard
              result={result}
              onReset={() => {
                setResult(null);
                setPhase("input");
              }}
            />
          )}
        </div>
      </div>
    </section>
  );
}
