import { AlertTriangle, Check } from "lucide-react";
import { mockHealth } from "@/data/mockArchitecture";
import type { ArchitectureHealth } from "@/types/architecture";
import { useCountUp, useInViewOnce } from "@/hooks/useCountUp";
import { SectionHeading } from "./SectionHeading";

export function HealthDashboard({
  compact = false,
  health = mockHealth,
}: {
  compact?: boolean;
  health?: ArchitectureHealth;
}) {
  const { ref, inView } = useInViewOnce<HTMLDivElement>();
  const score = useCountUp(health.score, inView, 1400);
  const circumference = 2 * Math.PI * 68;

  return (
    <section className={compact ? "" : "border-t border-border py-24 sm:py-32"}>
      <div className={compact ? "" : "mx-auto max-w-[1400px] px-5 sm:px-8"}>
        {!compact && (
          <SectionHeading
            index="05"
            eyebrow="Architecture health"
            title={
              <>
                KNOW WHEN
                <br />
                ARCHITECTURE BREAKS.
              </>
            }
            copy="Coupling, dependency depth, complexity and cycles — scored continuously so drift is visible before it becomes debt."
          />
        )}

        <div
          ref={ref}
          className={`grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)] ${compact ? "" : "mt-14"}`}
        >
          <div className="panel flex flex-col items-center justify-center p-8">
            <p className="label-mono self-start">Architecture health</p>
            <div className="relative mt-6 h-[180px] w-[180px]">
              <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90">
                <circle cx="80" cy="80" r="68" className="fill-none stroke-border" strokeWidth="3" />
                <circle
                  cx="80"
                  cy="80"
                  r="68"
                  className="fill-none stroke-accent"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={circumference * (1 - (inView ? health.score : 0) / 100)}
                  style={{ transition: "stroke-dashoffset 1.4s cubic-bezier(0.22,1,0.36,1)" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <p className="font-display text-[3.4rem] leading-none text-foreground tabular-nums">
                  {Math.round(score)}
                </p>
                <p className="label-mono mt-1">/100</p>
              </div>
            </div>
            <p className="mt-6 rounded-md border border-accent/40 bg-accent/10 px-3 py-1 font-mono text-[0.7rem] tracking-[0.2em] text-accent">
              {health.grade}
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="panel p-6">
              <p className="label-mono">Signals</p>
              <ul className="mt-4 space-y-3">
                {health.strengths.map((s) => (
                  <li key={s} className="flex items-start gap-2.5 text-[0.84rem] text-foreground/90">
                    <Check size={14} className="mt-0.5 shrink-0 text-accent" aria-hidden />
                    {s}
                  </li>
                ))}
                {health.warnings.map((w) => (
                  <li key={w} className="flex items-start gap-2.5 text-[0.84rem] text-muted-foreground">
                    <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warning" aria-hidden />
                    {w}
                  </li>
                ))}
              </ul>
            </div>

            <div className="panel p-6">
              <p className="label-mono">Metrics</p>
              <ul className="mt-4 space-y-5">
                {health.metrics.map((m, i) => (
                  <li key={m.key}>
                    <div className="flex items-baseline justify-between gap-4">
                      <p className="text-[0.84rem] text-foreground">{m.label}</p>
                      <p className="font-mono text-[0.8rem] text-foreground tabular-nums">
                        {m.value}
                        {m.unit ?? ""}
                      </p>
                    </div>
                    <div className="mt-2 h-[2px] w-full bg-border">
                      <div
                        className={m.score < 60 ? "h-full bg-warning" : "h-full bg-accent"}
                        style={{
                          width: inView ? `${m.score}%` : "0%",
                          transition: `width 1s cubic-bezier(0.22,1,0.36,1) ${i * 120}ms`,
                        }}
                      />
                    </div>
                    {m.hint && <p className="label-mono mt-1.5">{m.hint}</p>}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
