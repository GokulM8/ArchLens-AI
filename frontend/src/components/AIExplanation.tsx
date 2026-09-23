import { mockExplanation, mockGraph } from "@/data/mockArchitecture";
import { useInViewOnce, useTypewriter } from "@/hooks/useCountUp";
import { ArchitectureGraph } from "./graph/ArchitectureGraph";
import { SectionHeading } from "./SectionHeading";

const focusGraph = {
  nodes: mockGraph.nodes.filter((n) =>
    ["api", "prediction", "preprocessing", "model", "postgres"].includes(n.id),
  ),
  edges: mockGraph.edges.filter((e) =>
    ["e4", "e5", "e6", "e9"].includes(e.id),
  ),
};

export function AIExplanation() {
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const pct = Math.round(mockExplanation.confidence * 100);
  const { shown, done } = useTypewriter(mockExplanation.verdict, inView);

  return (
    <section className="border-t border-border py-24 sm:py-32">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <SectionHeading
          index="04"
          eyebrow="AI understanding"
          title={
            <>
              AI THAT EXPLAINS
              <br />
              THE ARCHITECTURE.
            </>
          }
          copy="No hand-waving. Each conclusion cites the import, route or call site it was derived from."
        />

        <div ref={ref} className="mt-14 grid gap-5 lg:grid-cols-2">
          <div className="panel h-[360px] overflow-hidden sm:h-[440px]">
            <ArchitectureGraph data={focusGraph} selectedId="prediction" interactive={false} />
          </div>

          <div className="panel flex flex-col p-6 sm:p-8">
            <p className="label-mono flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
              archlens reasoning
            </p>
            <h3 className="mt-5 font-display text-[1.9rem] tracking-[-0.03em] text-foreground uppercase">
              {mockExplanation.question}
            </h3>
            <p
              className="mt-4 min-h-[4.5rem] text-sm leading-relaxed text-muted-foreground"
              aria-label={mockExplanation.verdict}
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
              {mockExplanation.evidence.map((item, i) => (
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
                <p className="font-mono text-[2rem] leading-none text-accent tabular-nums">{pct}%</p>
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
