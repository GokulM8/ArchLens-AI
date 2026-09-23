import { Link } from "@tanstack/react-router";
import { heroGraph } from "@/data/mockArchitecture";
import { MiniGraph } from "./graph/MiniGraph";

export function FinalCTA() {
  return (
    <section className="noise-texture relative overflow-hidden border-t border-border py-28 sm:py-40">
      <div className="pointer-events-none absolute inset-0 opacity-[0.16]">
        <div className="mx-auto h-full max-w-[900px] px-10">
          <MiniGraph data={heroGraph} animate={false} />
        </div>
      </div>
      <div
        className="pointer-events-none absolute inset-x-0 bottom-[-30%] mx-auto h-[420px] w-[720px] rounded-full opacity-[0.09] blur-[120px]"
        style={{ background: "var(--accent)" }}
      />

      <div className="relative mx-auto max-w-[1400px] px-5 text-center sm:px-8">
        <h2 className="mx-auto max-w-4xl text-[clamp(2.2rem,7vw,5.4rem)] text-display text-foreground">
          YOUR CODEBASE
          <br />
          ALREADY HAS A MAP.
          <span className="mt-4 block text-subtle">YOU JUST CAN&apos;T SEE IT YET.</span>
        </h2>

        <div className="mt-12 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/analyze"
            className="inline-flex items-center gap-2 rounded-md bg-accent px-7 py-4 font-mono text-[0.76rem] tracking-[0.14em] text-accent-foreground uppercase transition-transform duration-200 hover:-translate-y-px"
          >
            Analyze Your Repository <span aria-hidden>→</span>
          </Link>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-2 rounded-md border border-border-strong px-7 py-4 font-mono text-[0.76rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
          >
            View on GitHub
          </a>
        </div>
      </div>
    </section>
  );
}
