import { useEffect, useState } from "react";
import { Check, Copy, X } from "lucide-react";
import type { ArchitectureNode } from "@/types/architecture";

interface SourceViewerProps {
  node: ArchitectureNode;
  onClose: () => void;
}

/** Full-window view of the source ArchLens read for a component. */
export function SourceViewer({ node, onClose }: SourceViewerProps) {
  const meta = node.metadata ?? {};
  // The backend returns a real excerpt per component, not whole files.
  const code = (meta.snippet ?? "").replace(/\s+$/, "");
  const lines = code ? code.split("\n") : [];
  const startLine = meta.snippetStart ?? meta.lines?.[0] ?? 1;
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Source for ${node.label}`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm sm:p-8"
    >
      <div className="flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-border-strong bg-surface">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <p className="label-mono text-accent">{node.label}</p>
            <p className="mt-1 truncate font-mono text-[0.8rem] text-foreground">
              {meta.sourcePath ?? "source excerpt"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[0.65rem] tracking-[0.12em] text-subtle uppercase">
              {meta.snippetLanguage ?? "code"}
              {lines.length > 0 && ` · ${startLine}–${startLine + lines.length - 1}`}
            </span>
            <button
              type="button"
              onClick={copy}
              className="inline-flex items-center gap-2 rounded-md border border-border-strong px-3 py-2 font-mono text-[0.66rem] tracking-[0.12em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close source view"
              className="rounded-md border border-border p-2 text-muted-foreground hover:text-foreground"
            >
              <X size={14} />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-auto bg-[oklch(0.13_0.008_250)]">
          {lines.length > 0 ? (
            <pre className="min-w-full py-4 font-mono text-[0.78rem] leading-[1.75]">
              <code>
                {lines.map((line, i) => (
                  <span key={i} className="flex">
                    <span
                      aria-hidden
                      className="w-14 shrink-0 pr-4 text-right text-subtle/70 select-none"
                    >
                      {startLine + i}
                    </span>
                    <span className="whitespace-pre pr-6 text-foreground/90">{line || " "}</span>
                  </span>
                ))}
              </code>
            </pre>
          ) : (
            <p className="p-6 text-sm text-muted-foreground">
              No source excerpt was captured for this component.
            </p>
          )}
        </div>

        {meta.snippetSignals && meta.snippetSignals.length > 0 && (
          <footer className="border-t border-border px-5 py-4">
            <p className="label-mono">What ArchLens read here</p>
            <ul className="mt-2 space-y-1">
              {meta.snippetSignals.map((signal) => (
                <li key={signal} className="flex gap-2 text-[0.8rem] text-muted-foreground">
                  <span className="text-accent" aria-hidden>
                    →
                  </span>
                  {signal}
                </li>
              ))}
            </ul>
          </footer>
        )}
      </div>
    </div>
  );
}
