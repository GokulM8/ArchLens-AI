import { Code2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CodeSnippetProps {
  code: string;
  path?: string | undefined;
  language?: string | undefined;
  /** Line number of the first row of the excerpt. */
  startLine?: number | undefined;
  /** What the analyzer read out of this excerpt. */
  signals?: string[] | undefined;
  className?: string | undefined;
}

/** Read-only source excerpt with line numbers — the evidence behind an inference. */
export function CodeSnippet({
  code,
  path,
  language,
  startLine = 1,
  signals,
  className,
}: CodeSnippetProps) {
  const lines = code.replace(/\s+$/, "").split("\n");

  return (
    <figure
      className={cn(
        "overflow-hidden rounded-lg border border-border-strong bg-[oklch(0.13_0.008_250)]",
        className,
      )}
    >
      <figcaption className="flex items-center justify-between gap-3 border-b border-border bg-surface-raised/50 px-3 py-2">
        <span className="flex min-w-0 items-center gap-2">
          <Code2 className="h-3 w-3 shrink-0 text-accent" aria-hidden />
          <span className="truncate font-mono text-[0.68rem] text-foreground/90">
            {path ?? "source excerpt"}
          </span>
        </span>
        <span className="shrink-0 font-mono text-[0.6rem] tracking-[0.12em] text-subtle uppercase">
          {language ?? "code"} · {startLine}–{startLine + lines.length - 1}
        </span>
      </figcaption>

      <div className="overflow-x-auto">
        <pre className="min-w-full py-2 font-mono text-[0.7rem] leading-[1.65]">
          <code>
            {lines.map((line, i) => (
              <span key={i} className="flex">
                <span
                  aria-hidden
                  className="w-10 shrink-0 pr-3 text-right text-subtle/70 select-none"
                >
                  {startLine + i}
                </span>
                <span className="whitespace-pre pr-4 text-foreground/85">{line || " "}</span>
              </span>
            ))}
          </code>
        </pre>
      </div>

      {signals && signals.length > 0 && (
        <ul className="space-y-1 border-t border-border bg-surface/50 px-3 py-2.5">
          {signals.map((signal) => (
            <li key={signal} className="flex gap-2 text-[0.72rem] leading-snug text-muted-foreground">
              <span className="text-accent" aria-hidden>
                →
              </span>
              {signal}
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
