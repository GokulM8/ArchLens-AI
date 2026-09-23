import { pipelineStages } from "@/data/mockArchitecture";
import { useInViewOnce } from "@/hooks/useCountUp";
import { SectionHeading } from "./SectionHeading";

export function Pipeline() {
  const { ref, inView } = useInViewOnce<HTMLOListElement>();

  return (
    <section id="pipeline" className="relative border-t border-border py-24 sm:py-32">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="grid gap-14 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-20">
          <SectionHeading
            index="01"
            eyebrow="From code to architecture"
            title={
              <>
                FROM SOURCE CODE
                <br />
                TO SYSTEM MAP.
              </>
            }
            copy="ArchLens combines deterministic code analysis with AI-assisted reasoning to reconstruct how your software actually works."
          />

          <ol ref={ref} className="relative">
            <span
              aria-hidden
              className="absolute top-6 bottom-6 left-[21px] w-px bg-gradient-to-b from-accent/60 via-border-strong to-transparent"
            />
            {pipelineStages.map((stage, i) => (
              <li
                key={stage.id}
                className="group relative flex gap-5 pb-4 last:pb-0 sm:gap-7"
                style={{
                  opacity: inView ? 1 : 0,
                  transform: inView ? "none" : "translateY(14px)",
                  transition: `opacity 700ms ease ${i * 110}ms, transform 700ms cubic-bezier(0.22,1,0.36,1) ${i * 110}ms`,
                }}
              >
                <span
                  className="relative z-10 mt-4 flex h-[43px] w-[43px] shrink-0 items-center justify-center rounded-full border border-border-strong bg-surface font-mono text-[0.7rem] text-subtle transition-all duration-300 group-hover:border-accent group-hover:text-accent group-hover:shadow-glow"
                  aria-hidden
                >
                  {String(i + 1).padStart(2, "0")}
                </span>

                <div className="flex-1 rounded-xl border border-border bg-gradient-to-b from-surface-raised/70 to-surface/40 px-5 py-5 transition-all duration-300 group-hover:border-accent/40 group-hover:from-surface-raised sm:px-6">
                  <div className="flex items-baseline justify-between gap-4">
                    <p className="font-display text-[1.4rem] leading-tight tracking-[-0.03em] text-foreground transition-colors group-hover:text-accent sm:text-[1.55rem]">
                      {stage.label}
                    </p>
                    <span
                      className="font-mono text-[0.62rem] tracking-[0.14em] text-subtle uppercase opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                      aria-hidden
                    >
                      step {i + 1}/{pipelineStages.length}
                    </span>
                  </div>
                  <p className="mt-2 font-mono text-[0.74rem] leading-relaxed text-muted-foreground">
                    {stage.detail}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
