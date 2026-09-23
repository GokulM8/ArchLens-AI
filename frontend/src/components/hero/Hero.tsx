import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { HeroGraph } from "./HeroGraph";
import { useReducedMotion } from "@/hooks/useCountUp";

export function Hero() {
  const [offset, setOffset] = useState(0);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return;
    const onScroll = () => setOffset(Math.min(window.scrollY, 600));
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [reduced]);

  const progress = offset / 600;

  return (
    <section className="noise-texture relative overflow-hidden pt-32 pb-16 sm:pt-40 lg:pt-44">
      <div className="grid-texture pointer-events-none absolute inset-0 [mask-image:radial-gradient(80%_60%_at_50%_20%,black,transparent)]" />
      <div
        className="pointer-events-none absolute top-[-10%] left-1/2 h-[520px] w-[820px] -translate-x-1/2 rounded-full opacity-[0.1] blur-[110px]"
        style={{ background: "var(--accent)" }}
      />

      <div className="relative mx-auto max-w-[1400px] px-5 sm:px-8">
        <div
          className="max-w-4xl"
          style={{
            transform: `translateY(${-progress * 48}px)`,
            opacity: 1 - progress * 0.55,
          }}
        >
          <p className="label-mono flex items-center gap-3">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" aria-hidden />
            Codebase intelligence · v0.9 preview
          </p>

          <h1 className="mt-8 text-[clamp(3rem,11.5vw,9rem)] text-display text-foreground">
            UNDERSTAND
            <br />
            YOUR CODEBASE.
          </h1>

          <p className="mt-8 max-w-xl text-[1.02rem] leading-relaxed text-muted-foreground">
            ArchLens transforms source code into an intelligent, visual map of your software
            architecture — before you touch a single file.
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Link
              to="/analyze"
              className="inline-flex items-center gap-2 rounded-md bg-accent px-6 py-3.5 font-mono text-[0.76rem] tracking-[0.14em] text-accent-foreground uppercase transition-transform duration-200 hover:-translate-y-px"
            >
              Analyze Repository <span aria-hidden>→</span>
            </Link>
            <Link
              to="/architecture"
              className="inline-flex items-center gap-2 rounded-md border border-border-strong px-6 py-3.5 font-mono text-[0.76rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
            >
              Explore Demo
            </Link>
          </div>
        </div>

        <div
          className="relative mt-16 lg:mt-6"
          style={{
            transform: reduced ? undefined : `scale(${1 + progress * 0.08}) translateY(${-progress * 20}px)`,
            transformOrigin: "center top",
          }}
        >
          <div className="flex items-center justify-between gap-6 border-b border-border pb-4">
            <p className="label-mono">Live architecture inference · sample repository</p>
            <p className="hidden font-mono text-[0.68rem] text-subtle sm:block">
              hover a node to inspect
            </p>
          </div>
          <HeroGraph />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-border pt-6">
          {["CODE", "STRUCTURE", "DEPENDENCIES", "ARCHITECTURE"].map((step, i) => (
            <span key={step} className="flex items-center gap-6">
              <span
                className={`font-mono text-[0.68rem] tracking-[0.2em] ${i === 3 ? "text-accent" : "text-subtle"}`}
              >
                {step}
              </span>
              {i < 3 && (
                <span aria-hidden className="font-mono text-[0.68rem] text-border-strong">
                  →
                </span>
              )}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
