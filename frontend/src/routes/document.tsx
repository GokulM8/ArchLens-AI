import { createFileRoute, Link } from "@tanstack/react-router";
import { Upload } from "lucide-react";
import { ReportDocument } from "@/components/analyze/ReportDocument";
import { useAnalysis } from "@/lib/useAnalysis";
import { DEMO_MODE } from "@/lib/config";
import {
  mockAISummary,
  mockExplanation,
  mockGraph,
  mockHealth,
  mockSummary,
} from "@/data/mockArchitecture";
import type { AnalysisResult } from "@/services/api";

const sampleResult: AnalysisResult = {
  analysisId: "demo",
  summary: mockSummary,
  graph: mockGraph,
  health: mockHealth,
  explanation: mockExplanation,
  aiSummary: mockAISummary,
  empty: false,
  demo: true,
};

export const Route = createFileRoute("/document")({
  head: () => ({
    meta: [
      { title: "Architecture document — ArchLens AI" },
      {
        name: "description",
        content:
          "A full written architecture document for your repository: components, purpose, code locations, connections and health — ready to read or save as PDF.",
      },
      { property: "og:title", content: "Architecture document — ArchLens AI" },
      {
        property: "og:description",
        content: "Every component explained, with the code it was inferred from.",
      },
      { property: "og:type", content: "article" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DocumentPage,
});

function DocumentPage() {
  const current = useAnalysis().result;
  const result = current ?? (DEMO_MODE ? sampleResult : null);

  if (!result) {
    return (
      <main className="noise-texture relative min-h-screen">
        <div className="mx-auto max-w-[820px] px-4 pt-36 pb-24 sm:px-8">
          <div className="panel p-6 sm:p-8" role="status">
            <p className="label-mono">No analysis open</p>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              The document is generated from the analysis open in this tab.{" "}
              <Link
                to="/analyze"
                className="inline-flex items-center gap-1 text-accent hover:underline"
              >
                <Upload className="h-3 w-3" aria-hidden /> Analyze a repository
              </Link>{" "}
              or open a stored one from the{" "}
              <Link to="/architecture" search={{}} className="text-accent hover:underline">
                architecture explorer
              </Link>
              .
            </p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="noise-texture relative min-h-screen">
      {result.demo && (
        <div className="no-print mx-auto max-w-[820px] px-4 pt-28 sm:px-8">
          <p className="rounded-md border border-border-strong bg-surface-raised/60 px-4 py-3 font-mono text-[0.72rem] leading-relaxed text-muted-foreground">
            Demo mode · showing the bundled sample repository, not a real analysis.
          </p>
        </div>
      )}
      <div className={result.demo ? "-mt-24" : ""}>
        <ReportDocument result={result} standalone />
      </div>
    </main>
  );
}
