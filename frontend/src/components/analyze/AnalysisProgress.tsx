import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { analysisStages, mockGraph } from "@/data/mockArchitecture";
import { useReducedMotion } from "@/hooks/useCountUp";
import { ArchitectureGraph } from "@/components/graph/ArchitectureGraph";

interface AnalysisProgressProps {
  repository: string;
  onComplete: () => void;
}

export function AnalysisProgress({ repository, onComplete }: AnalysisProgressProps) {
  const [step, setStep] = useState(0);
  const reduced = useReducedMotion();

  useEffect(() => {
    const perStep = reduced ? 220 : 760;
    const timers = analysisStages.map((_, i) =>
      window.setTimeout(() => setStep(i + 1), perStep * (i + 1)),
    );
    const finish = window.setTimeout(onComplete, perStep * (analysisStages.length + 1));
    return () => {
      timers.forEach(window.clearTimeout);
      window.clearTimeout(finish);
    };
  }, [onComplete, reduced]);

  const revealed = Math.max(3, Math.ceil((step / analysisStages.length) * mockGraph.nodes.length));
  const partialGraph = {
    nodes: mockGraph.nodes.slice(0, revealed),
    edges: mockGraph.edges.filter(
      (e) =>
        mockGraph.nodes.slice(0, revealed).some((n) => n.id === e.source) &&
        mockGraph.nodes.slice(0, revealed).some((n) => n.id === e.target),
    ),
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
      <div className="panel p-6 sm:p-8">
        <p className="label-mono">Analyzing repository</p>
        <p className="mt-2 font-mono text-sm text-foreground">{repository}</p>

        <ol className="mt-7 space-y-4" aria-live="polite">
          {analysisStages.map((stage, i) => {
            const state = i < step ? "done" : i === step ? "active" : "pending";
            return (
              <li key={stage.id} className="flex gap-3">
                <span className="mt-1 flex h-4 w-4 items-center justify-center" aria-hidden>
                  {state === "done" ? (
                    <Check size={13} className="text-accent" />
                  ) : state === "active" ? (
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full border border-border-strong" />
                  )}
                </span>
                <div>
                  <p
                    className={`font-mono text-[0.84rem] transition-colors duration-500 ${
                      state === "done"
                        ? "text-foreground"
                        : state === "active"
                          ? "text-accent"
                          : "text-subtle/70"
                    }`}
                  >
                    {stage.label}
                  </p>
                  {state !== "pending" && stage.detail && (
                    <p className="label-mono mt-1 normal-case">{stage.detail}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>

        <div className="mt-8 h-[2px] w-full bg-border">
          <div
            className="h-full bg-accent transition-[width] duration-700 ease-out"
            style={{ width: `${(step / analysisStages.length) * 100}%` }}
          />
        </div>
      </div>

      <div className="panel h-[420px] overflow-hidden sm:h-[520px]">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="label-mono">Graph reconstruction</p>
          <p className="font-mono text-[0.68rem] text-accent tabular-nums">
            {partialGraph.nodes.length}/{mockGraph.nodes.length} components
          </p>
        </div>
        <div className="h-[calc(100%-2.75rem)]">
          <ArchitectureGraph data={partialGraph} interactive={false} />
        </div>
      </div>
    </div>
  );
}
