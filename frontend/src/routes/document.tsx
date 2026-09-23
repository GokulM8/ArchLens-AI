import { createFileRoute, Link } from "@tanstack/react-router";
import { Upload } from "lucide-react";
import { ReportDocument } from "@/components/analyze/ReportDocument";
import { useAnalysis } from "@/lib/useAnalysis";

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
  const { result, real } = useAnalysis();

  return (
    <main className="noise-texture relative min-h-screen">
      {!real && (
        <div className="no-print mx-auto max-w-[820px] px-4 pt-28 sm:px-8">
          <p className="rounded-md border border-border-strong bg-surface-raised/60 px-4 py-3 font-mono text-[0.72rem] leading-relaxed text-muted-foreground">
            Showing the sample repository.{" "}
            <Link to="/analyze" className="inline-flex items-center gap-1 text-accent hover:underline">
              <Upload className="h-3 w-3" aria-hidden /> Upload your own
            </Link>{" "}
            to generate this document from real files.
          </p>
        </div>
      )}
      <div className={real ? "" : "-mt-24"}>
        <ReportDocument result={result} standalone />
      </div>
    </main>
  );
}
