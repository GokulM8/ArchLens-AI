import { useMemo } from "react";
import type { AIExplanation as Explanation, ArchitectureGraphData } from "@/types/architecture";
import { useInViewOnce, useTypewriter } from "@/hooks/useCountUp";
import { ArchitectureGraph } from "./graph/ArchitectureGraph";
import { SectionHeading } from "./SectionHeading";

/** The explained node plus its direct neighbours. */
function focusGraphOf(graph: ArchitectureGraphData, nodeId: string): ArchitectureGraphData {
  const edges = graph.edges.filter((e) => e.source === nodeId || e.target === nodeId);
  const ids = new Set([nodeId, ...edges.flatMap((e) => [e.source, e.target])]);
  return { nodes: graph.nodes.filter((n) => ids.has(n.id)), edges };
}

export function AIExplanation({
  explanation,
  graph,
  eyebrow = "Architecture reasoning",
}: {
  explanation: Explanation;
  graph: ArchitectureGraphData;
  eyebrow?: string;
}) {
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const pct = Math.round(explanation.confidence * 100);
  const { shown, done } = useTypewriter(explanation.verdict, inView);
  const focusGraph = useMemo(
    () => focusGraphOf(graph, explanation.nodeId),
    [graph, explanation.nodeId],
  );

  return (
    <section className="border-t border-border py-24 sm:py-32">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <SectionHeading
          index="04"
          eyebrow={eyebrow}
          title={
            <>
              EVERY CONCLUSION
              <br />
              CITES ITS EVIDENCE.
            </>
          }
          copy="No hand-waving. Each classification lists the paths, imports and structures it was derived from."
        />

        <div ref={ref} className="mt-14 grid gap-5 lg:grid-cols-2">
          <div className="panel h-[360px] overflow-hidden sm:h-[440px]">
            <ArchitectureGraph
              data={focusGraph}
              selectedId={explanation.nodeId}
              interactive={false}
            />
          </div>

          <div className="panel flex flex-col p-6 sm:p-8">
            <p className="label-mono flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
              archlens reasoning
            </p>
            <h3 className="mt-5 font-display text-[1.9rem] tracking-[-0.03em] text-foreground uppercase">
              {explanation.question}
            </h3>
            <p
              className="mt-4 min-h-[4.5rem] text-sm leading-relaxed text-muted-foreground"
              aria-label={explanation.verdict}
            >
              <span aria-hidden>{shown}</span>
              {!done && (
                <span
                  className="ml-0.5 inline-block h-[1em] w-[0.5ch] translate-y-[0.12em] animate-pulse bg-accent align-middle"
                  aria-hidden
                />
              )}
            </p>

            <ul className="mt-7 space-y-3">
              {explanation.evidence.map((item, i) => (
                <li
                  key={item}
                  className="flex gap-3 border-b border-border pb-3 font-mono text-[0.78rem] leading-relaxed text-foreground/85"
                  style={{
                    opacity: done ? 1 : 0,
                    transform: done ? "none" : "translateX(-8px)",
                    transition: `all 500ms cubic-bezier(0.22,1,0.36,1) ${i * 120}ms`,
                  }}
                >
                  <span className="text-accent" aria-hidden>
                    →
                  </span>
                  {item}
                </li>
              ))}
            </ul>

            <div className="mt-auto pt-8">
              <div className="flex items-end justify-between">
                <p className="label-mono">Confidence</p>
                <p className="font-mono text-[2rem] leading-none text-accent tabular-nums">
                  {pct}%
                </p>
              </div>
              <div className="mt-3 h-[3px] w-full bg-border">
                <div
                  className="h-full bg-accent transition-[width] duration-1000 ease-out"
                  style={{ width: inView ? `${pct}%` : "0%" }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
