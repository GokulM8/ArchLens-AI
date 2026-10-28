import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { FileText } from "lucide-react";
import type { AnalysisResult } from "@/services/api";
import { ArchitectureGraph } from "@/components/graph/ArchitectureGraph";
import { NodeInspector } from "@/components/NodeInspector";
import { HealthDashboard } from "@/components/HealthDashboard";
import { ReportDocument } from "@/components/analyze/ReportDocument";
import { CopilotPanel } from "@/components/analyze/CopilotPanel";

export function ResultDashboard({
  result,
  onReset,
}: {
  result: AnalysisResult;
  onReset: () => void;
}) {
  const [selected, setSelected] = useState<string | null>(
    result.explanation?.nodeId ?? result.graph.nodes[0]?.id ?? null,
  );
  const [reportOpen, setReportOpen] = useState(false);
  const node = result.graph.nodes.find((n) => n.id === selected) ?? null;
  const { summary } = result;

  const stats = [
    { value: summary.filesScanned.toLocaleString(), label: "files" },
    { value: String(summary.modules), label: "modules" },
    { value: String(summary.apiRoutes), label: "api routes" },
    { value: String(summary.externalServices), label: "external services" },
  ];

  return (
    <div className="space-y-5">
      <div className="panel flex flex-wrap items-end justify-between gap-6 p-6 sm:p-8">
        <div>
          <p className="label-mono">
            Repository
            {result.demo && <span className="ml-2 text-warning">· demo data (no backend)</span>}
          </p>
          <h2 className="mt-2 font-display text-[2.2rem] tracking-[-0.035em] text-foreground">
            {summary.repository}
          </h2>
          <p className="mt-1 font-mono text-[0.72rem] text-subtle">
            branch {summary.branch} · {summary.circularDependencies} circular dependencies
          </p>
        </div>
        <dl className="flex flex-wrap gap-x-10 gap-y-4">
          {stats.map((s) => (
            <div key={s.label}>
              <dd className="font-mono text-[1.4rem] text-foreground tabular-nums">{s.value}</dd>
              <dt className="label-mono mt-1">{s.label}</dt>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setReportOpen(true)}
            className="flex items-center gap-2 rounded-md bg-accent px-5 py-3 font-mono text-[0.72rem] tracking-[0.14em] text-accent-foreground uppercase transition-opacity hover:opacity-90"
          >
            <FileText className="h-3.5 w-3.5" aria-hidden />
            Full report · document / PDF
          </button>
          {!result.demo && (
            <Link
              to="/architecture"
              search={{ id: result.analysisId }}
              className="rounded-md border border-border-strong px-5 py-3 font-mono text-[0.72rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
            >
              Explore &amp; compare
            </Link>
          )}
          <Link
            to="/document"
            className="rounded-md border border-border-strong px-5 py-3 font-mono text-[0.72rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
          >
            Architecture document
          </Link>
          <button
            type="button"
            onClick={onReset}
            className="rounded-md border border-border-strong px-5 py-3 font-mono text-[0.72rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
          >
            New analysis
          </button>
        </div>
      </div>

      {result.empty ? (
        <div className="panel p-6 sm:p-8" role="status">
          <p className="label-mono">No architecture to show</p>
          <p className="mt-3 max-w-2xl text-[0.92rem] leading-relaxed text-muted-foreground">
            The analysis finished, but no Python modules were found in this archive. ArchLens
            currently analyses Python sources only — check that the ZIP contains your project&apos;s
            .py files.
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="panel h-[440px] overflow-hidden sm:h-[560px]">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <p className="label-mono">Architecture graph</p>
                <p className="font-mono text-[0.68rem] text-subtle">
                  {result.graph.nodes.length} components · {result.graph.edges.length} edges
                </p>
              </div>
              <div className="h-[calc(100%-2.75rem)]">
                <ArchitectureGraph
                  data={result.graph}
                  selectedId={selected}
                  onSelect={setSelected}
                />
              </div>
            </div>
            <NodeInspector node={node} onClose={() => setSelected(null)} />
          </div>

          <HealthDashboard compact health={result.health} />
        </>
      )}

      <div className="panel p-6 sm:p-8">
        <p className="label-mono flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
          Summary
          <span className="normal-case tracking-normal text-subtle">
            · derived from the static analysis
          </span>
        </p>
        <div className="mt-4 space-y-4">
          {result.aiSummary.map((para, i) => (
            <p key={i} className="max-w-3xl text-[0.92rem] leading-relaxed text-muted-foreground">
              {para}
            </p>
          ))}
        </div>
      </div>

      {!result.demo && !result.empty && <CopilotPanel analysisId={result.analysisId} />}

      {reportOpen && <ReportDocument result={result} onClose={() => setReportOpen(false)} />}
    </div>
  );
}
