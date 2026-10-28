import { createFileRoute } from "@tanstack/react-router";
import { Hero } from "@/components/hero/Hero";
import { Pipeline } from "@/components/Pipeline";
import { AnalysisConsole } from "@/components/AnalysisConsole";
import { ArchitectureExplorer } from "@/components/ArchitectureExplorer";
import { AIExplanation } from "@/components/AIExplanation";
import { HealthDashboard } from "@/components/HealthDashboard";
import { ArchitectureDiff } from "@/components/ArchitectureDiff";
import { Technologies } from "@/components/Technologies";
import { FinalCTA } from "@/components/FinalCTA";
import { mockDiff, mockExplanation, mockGraph, mockHealth } from "@/data/mockArchitecture";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ArchLens AI — Understand your codebase before you touch a file" },
      {
        name: "description",
        content:
          "ArchLens AI analyzes repositories and turns source code into an interactive architecture map with AI explanations, health scoring and structural diffs.",
      },
      {
        property: "og:title",
        content: "ArchLens AI — Understand your codebase",
      },
      {
        property: "og:description",
        content:
          "Visual codebase intelligence: dependency graphs, architecture inference, health scoring and structural diffs.",
      },
    ],
  }),
  component: Home,
});

function Home() {
  return (
    <>
      <Hero />

      <Pipeline />
      <AnalysisConsole />
      {/* Landing sections illustrate the product with the bundled sample repository. */}
      <ArchitectureExplorer
        data={mockGraph}
        initialSelected="prediction"
        sourceLabel="sample repository"
      />
      <AIExplanation
        explanation={mockExplanation}
        graph={mockGraph}
        eyebrow="Architecture reasoning · sample"
      />
      <HealthDashboard health={mockHealth} />
      <ArchitectureDiff diff={mockDiff} />
      <Technologies />
      <FinalCTA />
    </>
  );
}
