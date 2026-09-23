import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/privacy")({
  head: () => ({
    meta: [
      { title: "Privacy — ArchLens AI" },
      {
        name: "description",
        content: "How ArchLens AI handles repository data, source code and analysis artifacts.",
      },
      { property: "og:title", content: "Privacy — ArchLens AI" },
      {
        property: "og:description",
        content: "How ArchLens AI handles repository data and analysis artifacts.",
      },
    ],
  }),
  component: PrivacyPage,
});

const sections = [
  {
    title: "What we analyze",
    body: "ArchLens reads source files to build an abstract syntax tree, import graph and route map. Code is never executed.",
  },
  {
    title: "What we store",
    body: "Structural artifacts only: component graphs, health metrics and generated explanations. Raw source is discarded after analysis.",
  },
  {
    title: "Secrets",
    body: "Environment files and credential-shaped values are skipped during scanning and are never sent to a model.",
  },
];

function PrivacyPage() {
  return (
    <section className="mx-auto max-w-3xl px-5 pt-32 pb-24 sm:px-8 sm:pt-40">
      <p className="label-mono">Legal</p>
      <h1 className="mt-6 text-[clamp(2.2rem,6vw,3.6rem)] text-display text-foreground">PRIVACY</h1>
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
