import { useEffect, useState } from "react";

interface AnalysisProgressProps {
  repository: string;
}

/** What the backend runs for one upload (docs/API.md). The request is a single
 *  blocking call, so these are shown as one indeterminate step, not fake timings. */
const pipelineSteps = [
  { id: "upload", label: "Upload & safe extraction", detail: "size, path and symlink checks" },
  {
    id: "phase1",
    label: "Static analysis",
    detail: "Python AST: modules, classes, routes, imports",
  },
  { id: "phase2", label: "Dependency graph", detail: "graph.json" },
  {
    id: "phase3",
    label: "Architecture inference",
    detail: "roles, layers, patterns, entry points",
  },
  {
    id: "phase4",
    label: "Architecture health",
    detail: "coupling, cycles, layer violations, risks",
  },
  { id: "phase5", label: "Evolution analysis", detail: "refactoring opportunities and impact" },
];

export function AnalysisProgress({ repository }: AnalysisProgressProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="panel mx-auto max-w-2xl p-6 sm:p-8" role="status" aria-live="polite">
      <div className="flex items-baseline justify-between gap-4">
        <p className="label-mono">Analyzing repository</p>
        <p className="font-mono text-[0.68rem] text-subtle tabular-nums">{elapsed}s</p>
      </div>
      <p className="mt-2 font-mono text-sm text-foreground">{repository}</p>

      <ol className="mt-7 space-y-4">
        {pipelineSteps.map((step) => (
          <li key={step.id} className="flex gap-3">
            <span className="mt-1.5 flex h-4 w-4 items-center justify-center" aria-hidden>
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            </span>
            <div>
              <p className="font-mono text-[0.84rem] text-foreground">{step.label}</p>
              <p className="label-mono mt-1 normal-case">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-8 h-[2px] w-full overflow-hidden bg-border">
        <div className="h-full w-1/3 animate-pulse bg-accent" />
      </div>
      <p className="mt-4 font-mono text-[0.68rem] text-subtle">
        The server runs the whole pipeline in one request; results appear when it finishes.
      </p>
    </div>
  );
}
