import type { ReactNode } from "react";
import type { ArchitectureDiffData } from "@/types/architecture";
import { useInViewOnce } from "@/hooks/useCountUp";
import { MiniGraph } from "./graph/MiniGraph";
import { SectionHeading } from "./SectionHeading";

const kindMark = { added: "+", modified: "~", removed: "−" } as const;
const kindClass = {
  added: "text-accent",
  modified: "text-warning",
  removed: "text-destructive",
} as const;

export function ArchitectureDiff({
  diff,
  controls,
}: {
  /** null renders only the heading and controls (nothing compared yet). */
  diff: ArchitectureDiffData | null;
  /** e.g. a baseline picker, rendered above the comparison. */
  controls?: ReactNode;
}) {
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const before = new Set(diff?.versionA.graph.nodes.map((n) => n.id) ?? []);
  const emphasis =
    diff?.versionB.graph.nodes.filter((n) => !before.has(n.id)).map((n) => n.id) ?? [];

  return (
    <section className="border-t border-border py-24 sm:py-32">
      <div ref={ref} className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <SectionHeading
          index="06"
          eyebrow="Architecture diff"
          title={
            <>
              SEE HOW YOUR
              <br />
              ARCHITECTURE EVOLVES.
            </>
          }
          copy="Compare two analyses structurally. Added components, rerouted dependencies and changed roles surface as a diff — not a wall of changed lines."
        />

        {controls && <div className="mt-10">{controls}</div>}

        {diff && (
          <div className="mt-14 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_300px]">
            {[diff.versionA, diff.versionB].map((version, idx) => (
              <div key={version.label} className="panel overflow-hidden">
                <div className="flex items-center justify-between border-b border-border px-4 py-3">
                  <p className="font-mono text-[0.7rem] tracking-[0.18em] text-subtle uppercase">
                    {version.label}
                  </p>
                  <p className="font-mono text-[0.68rem] text-subtle">
                    {version.graph.nodes.length} components
                  </p>
                </div>
                <div
                  className="h-[320px] p-8 sm:h-[380px]"
                  style={{
                    opacity: inView ? 1 : 0,
                    transition: `opacity 800ms ease ${idx * 260}ms`,
                  }}
                >
                  <MiniGraph
                    data={version.graph}
                    emphasis={idx === 1 ? emphasis : []}
                    animate={inView}
                  />
                </div>
              </div>
            ))}

            <div className="panel p-6">
              <p className="label-mono">Structural changes</p>
              {diff.changes.length === 0 && (
                <p className="mt-4 text-[0.84rem] text-muted-foreground">
                  No structural changes between these analyses.
                </p>
              )}
              <ul className="mt-4 max-h-[420px] space-y-4 overflow-y-auto">
                {diff.changes.map((change, i) => (
                  <li
                    key={`${change.kind}:${change.label}`}
                    className="border-b border-border pb-4 last:border-0"
                    style={{
                      opacity: inView ? 1 : 0,
                      transform: inView ? "none" : "translateY(8px)",
                      transition: `all 600ms cubic-bezier(0.22,1,0.36,1) ${400 + Math.min(i, 8) * 130}ms`,
                    }}
                  >
                    <p className="font-mono text-[0.82rem] text-foreground">
                      <span className={`mr-2 ${kindClass[change.kind]}`} aria-hidden>
                        {kindMark[change.kind]}
                      </span>
                      <span className="sr-only">{change.kind}: </span>
                      {change.label}
                    </p>
                    <p className="label-mono mt-1.5 normal-case">{change.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
