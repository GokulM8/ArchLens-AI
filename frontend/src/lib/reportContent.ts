import type { AnalysisResult } from "@/services/api";
import type { ArchitectureEdge, ArchitectureNode } from "@/types/architecture";

/**
 * Turns an analysis result into a written report model: what each component is,
 * which code implements it, and why it exists in the architecture.
 * Backend-shaped input only — no UI concerns here.
 */

const rolePurpose: Record<string, string> = {
  client: "User-facing entry point. Renders the interface and issues requests to the backend.",
  gateway:
    "Traffic boundary. Routes, protects and forwards incoming requests to internal services.",
  service: "Business-logic owner. Executes a bounded responsibility on behalf of API routes.",
  module: "Shared implementation detail. Reused by services rather than exposed directly.",
  model: "Data model. Defines the entities and schemas other components exchange or persist.",
  datastore: "System of record. Persists domain data used across services.",
  cache: "Latency layer. Stores short-lived copies of expensive reads.",
  external: "Third-party dependency reached over the network.",
};

const edgeVerb: Record<ArchitectureEdge["type"], string> = {
  imports: "imports",
  calls: "calls over HTTP",
  reads: "reads from",
  writes: "writes to",
  queries: "queries",
};

export interface ReportComponent {
  id: string;
  name: string;
  kind: string;
  purpose: string;
  what: string;
  sourcePath: string;
  lines: string;
  confidence: string;
  dependencies: string[];
  consumers: string[];
  usedIn: string[];
  snippet?: string | undefined;
  snippetStart?: number | undefined;
  snippetSignals?: string[] | undefined;
}

export interface RepositoryReport {
  title: string;
  branch: string;
  generatedAt: string;
  overview: string[];
  facts: { label: string; value: string }[];
  languages: { name: string; share: string }[];
  components: ReportComponent[];
  connections: { from: string; relation: string; to: string; confidence: string }[];
  health: {
    score: number;
    grade: string;
    metrics: { label: string; value: string; hint: string }[];
    strengths: string[];
    warnings: string[];
  };
  evidence: { verdict: string; points: string[]; confidence: string } | null;
}

function pct(value?: number) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "—";
}

function componentOf(
  node: ArchitectureNode,
  edges: ArchitectureEdge[],
  labels: Record<string, string>,
): ReportComponent {
  const meta = node.metadata ?? {};
  const outgoing = edges.filter((e) => e.source === node.id);
  const incoming = edges.filter((e) => e.target === node.id);

  return {
    id: node.id,
    name: node.label,
    kind: node.type,
    purpose: rolePurpose[node.type] ?? "Component detected in the dependency graph.",
    what: node.description ?? "No description inferred.",
    sourcePath: meta.sourcePath ?? "—",
    lines: meta.lines ? `lines ${meta.lines[0]}–${meta.lines[1]}` : "—",
    confidence: pct(node.confidence),
    dependencies: meta.dependencies?.length ? meta.dependencies : ["none detected"],
    consumers: meta.consumers?.length ? meta.consumers : ["none detected"],
    usedIn: [
      ...incoming.map((e) => `${labels[e.source] ?? e.source} ${edgeVerb[e.type]} this component`),
      ...outgoing.map((e) => `This component ${edgeVerb[e.type]} ${labels[e.target] ?? e.target}`),
    ],
    snippet: meta.snippet,
    snippetStart: meta.snippetStart,
    snippetSignals: meta.snippetSignals,
  };
}

export function buildRepositoryReport(result: AnalysisResult): RepositoryReport {
  const { summary, graph, health, explanation, aiSummary } = result;
  const labels: Record<string, string> = {};
  graph.nodes.forEach((n) => {
    labels[n.id] = n.label;
  });

  return {
    title: summary.repository,
    branch: summary.branch,
    generatedAt: new Date().toISOString().slice(0, 10),
    overview: aiSummary,
    facts: [
      { label: "Files scanned", value: summary.filesScanned.toLocaleString() },
      { label: "Modules", value: String(summary.modules) },
      { label: "API routes", value: String(summary.apiRoutes) },
      { label: "External services", value: String(summary.externalServices) },
      { label: "Components inferred", value: String(graph.nodes.length) },
      { label: "Dependency edges", value: String(graph.edges.length) },
      { label: "Circular dependencies", value: String(summary.circularDependencies) },
      { label: "Architecture score", value: `${health.score} / 100 · ${health.grade}` },
    ],
    languages: summary.languages.map((l) => ({
      name: l.name,
      share: `${Math.round(l.share * 100)}%`,
    })),
    components: graph.nodes.map((node) => componentOf(node, graph.edges, labels)),
    connections: graph.edges.map((edge) => ({
      from: labels[edge.source] ?? edge.source,
      relation: edgeVerb[edge.type],
      to: labels[edge.target] ?? edge.target,
      confidence: pct(edge.confidence),
    })),
    health: {
      score: health.score,
      grade: health.grade,
      metrics: health.metrics.map((m) => ({
        label: m.label,
        value: `${m.value}${m.unit ?? ""}`,
        hint: m.hint ?? "",
      })),
      strengths: health.strengths,
      warnings: health.warnings,
    },
    evidence: explanation
      ? {
          verdict: explanation.verdict,
          points: explanation.evidence,
          confidence: pct(explanation.confidence),
        }
      : null,
  };
}
