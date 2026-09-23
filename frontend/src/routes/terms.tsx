import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/terms")({
  head: () => ({
    meta: [
      { title: "Terms — ArchLens AI" },
      {
        name: "description",
        content: "Terms covering preview access to ArchLens AI architecture analysis.",
      },
      { property: "og:title", content: "Terms — ArchLens AI" },
      {
        property: "og:description",
        content: "Terms covering preview access to ArchLens AI architecture analysis.",
      },
    ],
  }),
  component: TermsPage,
});

const sections = [
  {
    title: "Preview access",
    body: "ArchLens is in preview. Analysis output is illustrative and should be reviewed by an engineer before acting on it.",
  },
  {
    title: "Acceptable use",
    body: "Analyze repositories you own or have permission to inspect. Do not use ArchLens to reverse engineer code you are not licensed to read.",
  },
  {
    title: "Availability",
    body: "Preview environments may change or reset without notice while the analysis engine evolves.",
  },
];

function TermsPage() {
  return (
    <section className="mx-auto max-w-3xl px-5 pt-32 pb-24 sm:px-8 sm:pt-40">
      <p className="label-mono">Legal</p>
      <h1 className="mt-6 text-[clamp(2.2rem,6vw,3.6rem)] text-display text-foreground">TERMS</h1>
      <div className="mt-12 space-y-10">
        {sections.map((s) => (
          <div key={s.title} className="border-t border-border pt-6">
            <h2 className="font-display text-[1.4rem] tracking-[-0.02em] text-foreground">
              {s.title}
            </h2>
            <p className="mt-3 text-[0.95rem] leading-relaxed text-muted-foreground">{s.body}</p>
          </div>
        ))}
      </div>
      <p className="mt-14 font-mono text-[0.72rem] text-subtle">
        Preview document · not legal advice · last updated 2026
      </p>
    </section>
  );
}
