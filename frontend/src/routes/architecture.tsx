import { createFileRoute } from "@tanstack/react-router";
import { ArchitectureExplorer } from "@/components/ArchitectureExplorer";
import { AIExplanation } from "@/components/AIExplanation";
import { HealthDashboard } from "@/components/HealthDashboard";
import { ArchitectureDiff } from "@/components/ArchitectureDiff";
import { FinalCTA } from "@/components/FinalCTA";
import { mockSummary } from "@/data/mockArchitecture";

export const Route = createFileRoute("/architecture")({
  head: () => ({
    meta: [
      { title: "Architecture explorer — ArchLens AI" },
      {
        name: "description",
        content:
          "Explore a live sample architecture graph: inferred components, dependency edges, node inspection, health scoring and structural diffs.",
      },
      { property: "og:title", content: "Architecture explorer — ArchLens AI" },
      {
        property: "og:description",
        content: "A sample system map: components, edges, confidence and architecture health.",
      },
    ],
  }),
  component: ArchitecturePage,
});

function ArchitecturePage() {
  return (
    <>
      <section className="noise-texture relative pt-28 pb-4 sm:pt-36">
        <div className="grid-texture pointer-events-none absolute inset-0 [mask-image:radial-gradient(70%_50%_at_50%_0%,black,transparent)]" />
        <div className="relative mx-auto max-w-[1400px] px-5 sm:px-8">
          <p className="label-mono">Demo · sample repository</p>
          <h1 className="mt-6 max-w-3xl text-[clamp(2.4rem,7vw,5rem)] text-display text-foreground">
            A SYSTEM MAP OF
            <br />
            {mockSummary.repository.toUpperCase()}
          </h1>
          <p className="mt-6 max-w-xl text-[0.98rem] leading-relaxed text-muted-foreground">
            {mockSummary.filesScanned.toLocaleString()} files · {mockSummary.modules} modules ·{" "}
            {mockSummary.apiRoutes} API routes, reduced to the nine components that actually define
            this system.
          </p>
        </div>
      </section>

      <ArchitectureExplorer withHeading={false} />
      <AIExplanation />
      <HealthDashboard />
      <ArchitectureDiff />
      <FinalCTA />
    </>
  );
}
