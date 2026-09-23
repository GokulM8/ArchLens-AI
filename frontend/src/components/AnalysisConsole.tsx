import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { mockSummary } from "@/data/mockArchitecture";
import { useCountUp, useInViewOnce } from "@/hooks/useCountUp";
import { SectionHeading } from "./SectionHeading";

const steps = [
  "Scanning files",
  "Parsing Python modules",
  "Detecting imports",
  "Finding API routes",
  "Building dependency graph",
  "Detecting architecture",
];

function Stat({ value, label, active }: { value: number; label: string; active: boolean }) {
  const n = useCountUp(value, active);
  return (
    <div className="border-t border-border pt-4">
      <p className="font-mono text-[1.6rem] tracking-tight text-foreground tabular-nums">
        {Math.round(n).toLocaleString()}
      </p>
      <p className="label-mono mt-1">{label}</p>
    </div>
  );
}

export function AnalysisConsole() {
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const [done, setDone] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const timers = steps.map((_, i) => window.setTimeout(() => setDone(i + 1), 320 + i * 340));
    return () => timers.forEach(window.clearTimeout);
  }, [inView]);

  return (
    <section id="product" className="border-t border-border py-24 sm:py-32">
      <div ref={ref} className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <SectionHeading
          index="02"
          eyebrow="Repository analysis"
          title={
            <>
              DETERMINISTIC FIRST.
              <br />
              AI SECOND.
            </>
          }
          copy="Every insight starts as a parsed fact: files, imports, routes, call edges. The AI layer only reasons over evidence that already exists in your repository."
        />

        <div className="panel noise-texture relative mt-14 overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
            <p className="font-mono text-[0.7rem] tracking-[0.16em] text-subtle uppercase">
              archlens analyze — my-project/
            </p>
            <span className="flex items-center gap-1.5 font-mono text-[0.68rem] text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
              {done < steps.length ? "running" : "complete"}
            </span>
          </div>

          <div className="grid gap-10 p-5 sm:p-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)] lg:gap-16">
            <div>
              <p className="font-mono text-[0.7rem] tracking-[0.2em] text-subtle uppercase">
                Analyzing repository
              </p>
              <p className="mt-2 font-mono text-sm text-foreground">my-project/</p>

              <ul className="mt-6 space-y-3" aria-live="polite">
                {steps.map((step, i) => {
                  const state = i < done ? "done" : i === done ? "active" : "pending";
                  return (
                    <li
                      key={step}
                      className={`flex items-center gap-3 font-mono text-[0.82rem] transition-colors duration-500 ${
                        state === "done"
                          ? "text-foreground"
                          : state === "active"
                            ? "text-accent"
                            : "text-subtle/70"
                      }`}
                    >
                      <span className="flex h-4 w-4 items-center justify-center" aria-hidden>
                        {state === "done" ? (
                          <Check size={13} className="text-accent" />
                        ) : state === "active" ? (
                          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                        ) : (
                          <span className="h-1.5 w-1.5 rounded-full border border-border-strong" />
                        )}
                      </span>
                      {step}
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="grid grid-cols-2 gap-x-8 gap-y-6 self-start sm:grid-cols-3 lg:grid-cols-2">
              <Stat value={mockSummary.filesScanned} label="files scanned" active={inView} />
              <Stat value={mockSummary.modules} label="modules detected" active={inView} />
              <Stat value={mockSummary.apiRoutes} label="api routes" active={inView} />
              <Stat value={mockSummary.externalServices} label="external services" active={inView} />
              <Stat
                value={mockSummary.circularDependencies}
                label="circular dependencies"
                active={inView}
              />
              <div className="border-t border-border pt-4">
                <p className="font-mono text-[1.6rem] tracking-tight text-accent tabular-nums">
                  {mockSummary.languages[0]?.name ?? "TypeScript"}
                </p>
                <p className="label-mono mt-1">primary language</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
