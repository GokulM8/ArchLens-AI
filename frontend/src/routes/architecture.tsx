import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import { ArchitectureExplorer } from "@/components/ArchitectureExplorer";
import { AIExplanation } from "@/components/AIExplanation";
import { HealthDashboard } from "@/components/HealthDashboard";
import { ArchitectureDiff } from "@/components/ArchitectureDiff";
import { FinalCTA } from "@/components/FinalCTA";
import {
  mockDiff,
  mockExplanation,
  mockGraph,
  mockHealth,
  mockSummary,
} from "@/data/mockArchitecture";
import { DEMO_MODE } from "@/lib/config";
import { useRepoSession } from "@/lib/repoStore";
import {
  getAnalysis,
  getArchitectureDiff,
  listAnalyses,
  type AnalysisMetadata,
  type AnalysisResponse,
  type AnalysisResult,
} from "@/services/api";
import type { ArchitectureDiffData } from "@/types/architecture";

export const Route = createFileRoute("/architecture")({
  validateSearch: (search: Record<string, unknown>): { id?: string } => {
    const id = search["id"];
    return typeof id === "string" && id ? { id } : {};
  },
  head: () => ({
    meta: [
      { title: "Architecture explorer — ArchLens AI" },
      {
        name: "description",
        content:
          "Explore an analysed repository: inferred components, dependency edges, node inspection, health scoring and structural diffs between analyses.",
      },
      { property: "og:title", content: "Architecture explorer — ArchLens AI" },
      {
        property: "og:description",
        content: "Components, edges, confidence, architecture health and diffs.",
      },
    ],
  }),
  component: ArchitecturePage,
});

type Load<T> =
  { state: "loading" } | { state: "error"; message: string } | { state: "ready"; data: T };

function ArchitecturePage() {
  const { id } = Route.useSearch();
  if (DEMO_MODE) return <DemoArchitecture />;
  return <BackendArchitecture id={id} />;
}

function BackendArchitecture({ id }: { id: string | undefined }) {
  const session = useRepoSession();
  const sessionResult = session?.result ?? null;
  const [analyses, setAnalyses] = useState<Load<AnalysisMetadata[]>>({ state: "loading" });
  const [loaded, setLoaded] = useState<Load<AnalysisResponse> | null>(null);

  useEffect(() => {
    let cancelled = false;
    listAnalyses()
      .then((items) => !cancelled && setAnalyses({ state: "ready", data: items }))
      .catch((e: Error) => !cancelled && setAnalyses({ state: "error", message: e.message }));
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch the requested analysis unless it is already the one in the session.
  const fromSession =
    sessionResult && (!id || sessionResult.analysisId === id) ? sessionResult : null;
  useEffect(() => {
    if (!id || fromSession) {
      setLoaded(null);
      return;
    }
    let cancelled = false;
    setLoaded({ state: "loading" });
    getAnalysis(id)
      .then((data) => !cancelled && setLoaded({ state: "ready", data }))
      .catch((e: Error) => !cancelled && setLoaded({ state: "error", message: e.message }));
    return () => {
      cancelled = true;
    };
  }, [id, fromSession]);

  if (fromSession) return <Workspace result={fromSession} analyses={analyses} />;

  if (loaded?.state === "loading") return <Notice title="Loading analysis…" busy />;
  if (loaded?.state === "error")
    return (
      <Notice title="Could not load this analysis" tone="error">
        {loaded.message} <BackToList />
      </Notice>
    );
  if (loaded?.state === "ready") {
    const { data } = loaded;
    if (data.status !== "completed")
      return (
        <Notice title={`Analysis ${data.status}`} tone="error">
          {data.error?.message ?? "This analysis has no results."} <BackToList />
        </Notice>
      );
    return <Workspace result={data} analyses={analyses} />;
  }

  return <AnalysisList analyses={analyses} />;
}

// ---------------------------------------------------------------------------

function Workspace({
  result,
  analyses,
}: {
  result: AnalysisResult;
  analyses: Load<AnalysisMetadata[]>;
}) {
  const { summary } = result;
  return (
    <>
      <PageHeader
        eyebrow={`Analysis · ${result.analysisId.slice(0, 8)}`}
        title={summary.repository}
      >
        {summary.filesScanned.toLocaleString()} files · {summary.modules} Python modules ·{" "}
        {summary.apiRoutes} API routes · {result.graph.nodes.length} components.{" "}
        <Link to="/architecture" search={{}} className="text-accent hover:underline">
          All analyses
        </Link>
      </PageHeader>

      {result.empty ? (
        <Notice title="No Python modules found" inline>
          The analysis completed but found nothing to map. ArchLens analyses Python sources only.
        </Notice>
      ) : (
        <>
          <ArchitectureExplorer
            key={result.analysisId}
            data={result.graph}
            withHeading={false}
            initialSelected={result.explanation?.nodeId}
            sourceLabel={summary.repository}
          />
          {result.explanation && (
            <AIExplanation explanation={result.explanation} graph={result.graph} />
          )}
          <HealthDashboard health={result.health} />
          <DiffSection current={result} analyses={analyses} />
        </>
      )}
    </>
  );
}

function DiffSection({
  current,
  analyses,
}: {
  current: AnalysisResult;
  analyses: Load<AnalysisMetadata[]>;
}) {
  const [baseline, setBaseline] = useState("");
  const [diff, setDiff] = useState<Load<ArchitectureDiffData> | null>(null);

  useEffect(() => {
    if (!baseline) {
      setDiff(null);
      return;
    }
    let cancelled = false;
    setDiff({ state: "loading" });
    getArchitectureDiff(current.analysisId, baseline)
      .then((data) => !cancelled && setDiff({ state: "ready", data }))
      .catch((e: Error) => !cancelled && setDiff({ state: "error", message: e.message }));
    return () => {
      cancelled = true;
    };
  }, [baseline, current.analysisId]);

  let controls: ReactNode;
  if (analyses.state === "loading")
    controls = <p className="label-mono">Loading stored analyses…</p>;
  else if (analyses.state === "error")
    controls = (
      <p className="font-mono text-[0.75rem] text-destructive" role="alert">
        {analyses.message}
      </p>
    );
  else {
    const others = analyses.data.filter(
      (a) => a.status === "completed" && a.analysisId !== current.analysisId,
    );
    controls =
      others.length === 0 ? (
        <p className="max-w-2xl text-sm text-muted-foreground">
          A diff needs a second completed analysis. Upload another snapshot of this repository on
          the{" "}
          <Link to="/analyze" className="text-accent hover:underline">
            analyze page
          </Link>{" "}
          to compare them.
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="baseline" className="label-mono">
            Compare against (version A)
          </label>
          <select
            id="baseline"
            value={baseline}
            onChange={(e) => setBaseline(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 font-mono text-[0.78rem] text-foreground"
          >
            <option value="">Choose a baseline…</option>
            {others.map((a) => (
              <option key={a.analysisId} value={a.analysisId}>
                {a.repository} · {new Date(a.createdAt).toLocaleString()}
              </option>
            ))}
          </select>
          {diff?.state === "loading" && <span className="label-mono">Comparing…</span>}
          {diff?.state === "error" && (
            <span className="font-mono text-[0.75rem] text-destructive" role="alert">
              {diff.message}
            </span>
          )}
        </div>
      );
  }

  return <ArchitectureDiff diff={diff?.state === "ready" ? diff.data : null} controls={controls} />;
}

function AnalysisList({ analyses }: { analyses: Load<AnalysisMetadata[]> }) {
  if (analyses.state === "loading") return <Notice title="Loading analyses…" busy />;
  if (analyses.state === "error")
    return (
      <Notice title="Backend unavailable" tone="error">
        {analyses.message}
      </Notice>
    );
  if (analyses.data.length === 0)
    return (
      <Notice title="No analyses yet">
        Nothing has been analysed on this server.{" "}
        <Link to="/analyze" className="text-accent hover:underline">
          Upload a repository
        </Link>{" "}
        to get started.
      </Notice>
    );

  return (
    <>
      <PageHeader eyebrow="Stored analyses" title="Architecture explorer">
        Open an analysis to explore its graph and health, or compare two of them.
      </PageHeader>
      <section className="mx-auto max-w-[1400px] px-5 pb-24 sm:px-8">
        <ul className="panel divide-y divide-border">
          {analyses.data.map((a) => (
            <li
              key={a.analysisId}
              className="flex flex-wrap items-center justify-between gap-3 px-5 py-4"
            >
              <div>
                <p className="font-mono text-[0.86rem] text-foreground">
                  {a.repository ?? a.source.filename}
                </p>
                <p className="label-mono mt-1 normal-case">
                  {new Date(a.createdAt).toLocaleString()} · {a.status}
                  {a.empty && " · no Python modules"}
                </p>
              </div>
              {a.status === "completed" ? (
                <Link
                  to="/architecture"
                  search={{ id: a.analysisId }}
                  className="rounded-md border border-border-strong px-4 py-2 font-mono text-[0.7rem] tracking-[0.14em] text-foreground uppercase hover:border-accent/60 hover:text-accent"
                >
                  Open
                </Link>
              ) : (
                <span className="font-mono text-[0.72rem] text-destructive">
                  {a.error?.message ?? a.status}
                </span>
              )}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function DemoArchitecture() {
  return (
    <>
      <PageHeader
        eyebrow="Demo mode · sample repository"
        title={`A system map of ${mockSummary.repository}`}
      >
        Bundled sample data — no backend is called while VITE_DEMO_MODE is enabled.
      </PageHeader>
      <ArchitectureExplorer
        data={mockGraph}
        withHeading={false}
        initialSelected="prediction"
        sourceLabel="sample"
      />
      <AIExplanation
        explanation={mockExplanation}
        graph={mockGraph}
        eyebrow="Architecture reasoning · sample"
      />
      <HealthDashboard health={mockHealth} />
      <ArchitectureDiff diff={mockDiff} />
      <FinalCTA />
    </>
  );
}

// ---------------------------------------------------------------------------

function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="noise-texture relative pt-28 pb-4 sm:pt-36">
      <div className="grid-texture pointer-events-none absolute inset-0 [mask-image:radial-gradient(70%_50%_at_50%_0%,black,transparent)]" />
      <div className="relative mx-auto max-w-[1400px] px-5 sm:px-8">
        <p className="label-mono">{eyebrow}</p>
        <h1 className="mt-6 max-w-4xl text-[clamp(2.4rem,7vw,5rem)] break-words text-display text-foreground uppercase">
          {title}
        </h1>
        <p className="mt-6 max-w-xl text-[0.98rem] leading-relaxed text-muted-foreground">
          {children}
        </p>
      </div>
    </section>
  );
}

function Notice({
  title,
  children,
  tone = "neutral",
  busy = false,
  inline = false,
}: {
  title: string;
  children?: ReactNode;
  tone?: "neutral" | "error";
  busy?: boolean;
  inline?: boolean;
}) {
  return (
    <section
      className={
        inline
          ? "mx-auto max-w-[1400px] px-5 py-10 sm:px-8"
          : "mx-auto max-w-2xl px-5 pt-36 pb-24 sm:px-8"
      }
    >
      <div
        className={`panel p-6 sm:p-8 ${tone === "error" ? "border-destructive/50" : ""}`}
        role={tone === "error" ? "alert" : "status"}
        aria-busy={busy || undefined}
      >
        <p className={`label-mono ${tone === "error" ? "text-destructive" : ""}`}>
          {busy && (
            <span
              className="mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent"
              aria-hidden
            />
          )}
          {title}
        </p>
        {children && (
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{children}</p>
        )}
      </div>
    </section>
  );
}

function BackToList() {
  return (
    <Link to="/architecture" search={{}} className="text-accent hover:underline">
      Back to all analyses
    </Link>
  );
}
