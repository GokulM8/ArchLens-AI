import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { ArchitectureNode } from "@/types/architecture";
import { CodeSnippet } from "@/components/CodeSnippet";
import { SourceViewer } from "@/components/SourceViewer";

const typeLabel: Record<string, string> = {
  client: "CLIENT",
  gateway: "GATEWAY",
  service: "SERVICE",
  module: "MODULE",
  model: "MODEL",
  datastore: "DATASTORE",
  cache: "CACHE",
  external: "EXTERNAL",
};

interface NodeInspectorProps {
  node: ArchitectureNode | null;
  onClose?: () => void;
}

export function NodeInspector({ node, onClose }: NodeInspectorProps) {
  const [sourceOpen, setSourceOpen] = useState(false);

  useEffect(() => {
    setSourceOpen(false);
  }, [node?.id]);

  if (!node) {
    return (
      <aside className="panel flex h-full min-h-[280px] flex-col justify-center p-6">
        <p className="label-mono">Node inspector</p>
        <p className="mt-3 text-sm text-muted-foreground">
          Select a component in the graph to inspect its role, dependencies, API consumers and
          source location.
        </p>
      </aside>
    );
  }

  const meta = node.metadata ?? {};

  return (
    <aside className="panel flex h-full flex-col p-6" aria-live="polite">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-display text-[1.7rem] tracking-[-0.03em] text-foreground">
            {node.label}
          </h3>
          <p className="label-mono mt-2 text-accent">{typeLabel[node.type] ?? node.type}</p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close inspector"
            className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-foreground"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {node.description && (
        <div className="mt-6">
          <p className="label-mono">Purpose</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{node.description}</p>
        </div>
      )}

      {meta.dependencies && meta.dependencies.length > 0 && (
        <div className="mt-6">
          <p className="label-mono">Dependencies</p>
          <ul className="mt-2 space-y-1.5">
            {meta.dependencies.map((dep) => (
              <li key={dep} className="font-mono text-[0.76rem] text-foreground/85">
                <span className="mr-2 text-subtle" aria-hidden>
                  •
                </span>
                {dep}
              </li>
            ))}
          </ul>
        </div>
      )}

      {meta.consumers && meta.consumers.length > 0 && (
        <div className="mt-6">
          <p className="label-mono">API consumers</p>
          <ul className="mt-2 space-y-1.5">
            {meta.consumers.map((c) => (
              <li key={c} className="font-mono text-[0.76rem] text-foreground/85">
                <span className="mr-2 text-subtle" aria-hidden>
                  •
                </span>
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {typeof node.confidence === "number" && (
        <div className="mt-6">
          <div className="flex items-baseline justify-between">
            <p className="label-mono">Confidence</p>
            <p className="font-mono text-sm text-accent tabular-nums">
              {Math.round(node.confidence * 100)}%
            </p>
          </div>
          <div className="mt-2 h-[3px] w-full bg-border">
            <div
              className="h-full bg-accent transition-[width] duration-700"
              style={{ width: `${Math.round(node.confidence * 100)}%` }}
            />
          </div>
        </div>
      )}

      {meta.sourcePath && (
        <div className="mt-6 border-t border-border pt-5">
          <p className="label-mono">Source</p>
          <p className="mt-2 font-mono text-[0.76rem] text-foreground">{meta.sourcePath}</p>
          {meta.lines && (
            <p className="mt-1 font-mono text-[0.72rem] text-subtle">
              Lines {meta.lines[0]}–{meta.lines[1]}
            </p>
          )}
        </div>
      )}

      {meta.snippet && (
        <div className="mt-5">
          <p className="label-mono">Code it was inferred from</p>
          <CodeSnippet
            className="mt-2"
            code={meta.snippet}
            path={meta.sourcePath}
            language={meta.snippetLanguage}
            startLine={meta.snippetStart}
            signals={meta.snippetSignals}
          />
        </div>
      )}

      <button
        type="button"
        onClick={() => setSourceOpen(true)}
        disabled={!meta.snippet}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md border border-border-strong px-4 py-3 font-mono text-[0.72rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
      >
        View Source <span aria-hidden>→</span>
      </button>

      {sourceOpen && <SourceViewer node={node} onClose={() => setSourceOpen(false)} />}
    </aside>
  );
}
