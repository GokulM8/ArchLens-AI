import { useEffect, useMemo } from "react";
import { Download, X } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { AnalysisResult } from "@/services/api";
import { buildRepositoryReport } from "@/lib/reportContent";

/**
 * Printable repository report. Rendered as a light "document" sheet in Poppins;
 * the same sheet is what the browser exports when the user saves it as a PDF.
 */
export function ReportDocument({
  result,
  onClose,
  standalone = false,
}: {
  result: AnalysisResult;
  onClose?: () => void;
  standalone?: boolean;
}) {
  const report = useMemo(() => buildRepositoryReport(result), [result]);

  useEffect(() => {
    document.body.dataset["printing"] = "report";
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (standalone) document.body.style.overflow = previousOverflow;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      delete document.body.dataset["printing"];
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose, standalone]);

  return (
    <div
      className={
        standalone
          ? "px-4 pt-28 pb-16 sm:px-8"
          : "fixed inset-0 z-50 overflow-y-auto bg-black/80 px-4 py-6 backdrop-blur-sm sm:px-8"
      }
      {...(standalone
        ? {}
        : {
            role: "dialog",
            "aria-modal": true as const,
            "aria-label": `Architecture report for ${report.title}`,
          })}
    >
      <div className="report-toolbar no-print mx-auto mb-4 flex max-w-[820px] flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[0.7rem] tracking-[0.16em] text-subtle uppercase">
          Document view · {report.title}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            className="flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 font-mono text-[0.7rem] tracking-[0.14em] text-accent-foreground uppercase transition-opacity hover:opacity-90"
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            Download PDF
          </button>
          {standalone ? (
            <>
              <Link
                to="/architecture"
                className="flex items-center gap-2 rounded-md border border-border-strong px-4 py-2.5 font-mono text-[0.7rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
              >
                Graph
              </Link>
            </>
          ) : (
            <button
              type="button"
              onClick={onClose}
              className="flex items-center gap-2 rounded-md border border-border-strong px-4 py-2.5 font-mono text-[0.7rem] tracking-[0.14em] text-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
              Close
            </button>
          )}
        </div>
      </div>

      <article className="report-sheet mx-auto max-w-[820px] rounded-lg bg-white px-8 py-10 text-[#1a1d21] shadow-panel sm:px-12 sm:py-14">
        <header className="border-b border-[#d9dde2] pb-6">
          <p className="text-[0.68rem] font-semibold tracking-[0.2em] text-[#0f8f6f] uppercase">
            ArchLens AI · Architecture report
          </p>
          <h1 className="mt-3 text-[2rem] leading-tight font-semibold tracking-tight text-[#12161a]">
            {report.title}
          </h1>
          <p className="mt-2 text-[0.82rem] text-[#5b636c]">
            Branch {report.branch} · generated {report.generatedAt}
          </p>
        </header>

        <Section title="1. Overview">
          {report.overview.map((para) => (
            <p
              key={para.slice(0, 24)}
              className="mt-3 text-[0.92rem] leading-relaxed text-[#39414a]"
            >
              {para}
            </p>
          ))}
          <dl className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {report.facts.map((fact) => (
              <div key={fact.label} className="rounded-md border border-[#e3e7eb] px-3 py-3">
                <dd className="text-[1rem] font-semibold text-[#12161a]">{fact.value}</dd>
                <dt className="mt-1 text-[0.66rem] tracking-[0.1em] text-[#7a828c] uppercase">
                  {fact.label}
                </dt>
              </div>
            ))}
          </dl>
          <p className="mt-5 text-[0.82rem] text-[#5b636c]">
            Languages:{" "}
            {report.languages.map((l, i) => (
              <span key={l.name}>
                {i > 0 ? " · " : ""}
                {l.name} {l.share}
              </span>
            ))}
          </p>
        </Section>

        <Section title="2. Components — what the code does and where it lives">
          {report.components.map((component, index) => (
            <section
              key={component.id}
              className="mt-6 break-inside-avoid border-t border-[#e3e7eb] pt-5 first:mt-4"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-[1.05rem] font-semibold text-[#12161a]">
                  2.{index + 1} {component.name}
                </h3>
                <span className="text-[0.68rem] tracking-[0.12em] text-[#0f8f6f] uppercase">
                  {component.kind} · {component.confidence} confidence
                </span>
              </div>
              <p className="mt-2 text-[0.9rem] leading-relaxed text-[#39414a]">{component.what}</p>
              <p className="mt-2 text-[0.88rem] leading-relaxed text-[#5b636c]">
                <strong className="font-semibold text-[#12161a]">Purpose: </strong>
                {component.purpose}
              </p>
              <p className="mt-2 text-[0.82rem] text-[#39414a]">
                <strong className="font-semibold text-[#12161a]">Code location: </strong>
                <span className="font-mono text-[0.78rem]">{component.sourcePath}</span> ·{" "}
                {component.lines}
              </p>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <ListBlock title="Code it depends on" items={component.dependencies} mono />
                <ListBlock title="Where it is used" items={component.consumers} mono />
              </div>
              {component.snippet && (
                <div className="mt-3 break-inside-avoid overflow-hidden rounded-md border border-[#d9dde2]">
                  <p className="border-b border-[#e3e7eb] bg-[#f4f6f8] px-3 py-1.5 text-[0.64rem] tracking-[0.12em] text-[#7a828c] uppercase">
                    Code it was inferred from
                  </p>
                  <pre className="overflow-x-auto bg-[#fbfcfd] px-3 py-2 font-mono text-[0.7rem] leading-[1.6] text-[#22282e]">
                    <code>
                      {component.snippet.split("\n").map((line, i) => (
                        <span key={i} className="flex">
                          <span className="w-8 shrink-0 pr-2 text-right text-[#a3abb4]">
                            {(component.snippetStart ?? 1) + i}
                          </span>
                          <span className="whitespace-pre">{line || " "}</span>
                        </span>
                      ))}
                    </code>
                  </pre>
                  {component.snippetSignals && component.snippetSignals.length > 0 && (
                    <ul className="space-y-1 border-t border-[#e3e7eb] px-3 py-2 text-[0.78rem] text-[#5b636c]">
                      {component.snippetSignals.map((s) => (
                        <li key={s}>→ {s}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              {component.usedIn.length > 0 && (
                <ul className="mt-3 space-y-1 text-[0.82rem] text-[#5b636c]">
                  {component.usedIn.map((line) => (
                    <li key={line}>— {line}</li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </Section>

        <Section title="3. Connections between components">
          <table className="mt-4 w-full border-collapse text-left text-[0.82rem]">
            <thead>
              <tr className="border-b border-[#d9dde2] text-[0.66rem] tracking-[0.12em] text-[#7a828c] uppercase">
                <th className="py-2 pr-3 font-medium">From</th>
                <th className="py-2 pr-3 font-medium">Relation</th>
                <th className="py-2 pr-3 font-medium">To</th>
                <th className="py-2 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {report.connections.map((row) => (
                <tr
                  key={`${row.from}-${row.to}-${row.relation}`}
                  className="border-b border-[#eef1f4]"
                >
                  <td className="py-2 pr-3 text-[#12161a]">{row.from}</td>
                  <td className="py-2 pr-3 text-[#5b636c]">{row.relation}</td>
                  <td className="py-2 pr-3 text-[#12161a]">{row.to}</td>
                  <td className="py-2 text-[#0f8f6f]">{row.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section title="4. Architecture health">
          <p className="mt-3 text-[0.92rem] text-[#39414a]">
            Overall score {report.health.score} / 100 — {report.health.grade}.
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {report.health.metrics.map((metric) => (
              <div key={metric.label} className="rounded-md border border-[#e3e7eb] px-3 py-3">
                <dd className="text-[1rem] font-semibold text-[#12161a]">{metric.value}</dd>
                <dt className="mt-1 text-[0.66rem] tracking-[0.08em] text-[#7a828c] uppercase">
                  {metric.label}
                </dt>
                {metric.hint && <p className="mt-1 text-[0.7rem] text-[#8b939c]">{metric.hint}</p>}
              </div>
            ))}
          </dl>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <ListBlock title="Strengths" items={report.health.strengths} />
            <ListBlock title="Warnings" items={report.health.warnings} />
          </div>
        </Section>

        {report.evidence && (
          <Section title="5. Why the analysis reached these conclusions">
            <p className="mt-3 text-[0.92rem] leading-relaxed text-[#39414a]">
              {report.evidence.verdict}
            </p>
            <ul className="mt-3 space-y-1.5 text-[0.85rem] text-[#5b636c]">
              {report.evidence.points.map((point) => (
                <li key={point}>— {point}</li>
              ))}
            </ul>
            <p className="mt-3 text-[0.78rem] text-[#8b939c]">
              Evidence confidence {report.evidence.confidence}. Every statement above is derived
              from static analysis of the repository, not from guesses about intent.
            </p>
          </Section>
        )}

        <footer className="mt-10 border-t border-[#d9dde2] pt-4 text-[0.7rem] text-[#8b939c]">
          ArchLens AI · Understand your codebase. Before you touch a single file.
        </footer>
      </article>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-9">
      <h2 className="text-[1.15rem] font-semibold tracking-tight text-[#12161a]">{title}</h2>
      {children}
    </section>
  );
}

function ListBlock({ title, items, mono }: { title: string; items: string[]; mono?: boolean }) {
  return (
    <div>
      <p className="text-[0.66rem] tracking-[0.12em] text-[#7a828c] uppercase">{title}</p>
      <ul
        className={`mt-2 space-y-1 text-[0.8rem] text-[#39414a] ${mono ? "font-mono text-[0.75rem]" : ""}`}
      >
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
