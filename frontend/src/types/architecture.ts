export type ArchitectureNodeType =
  | "client"
  | "gateway"
  | "service"
  | "module"
  | "model"
  | "datastore"
  | "cache"
  | "external";

export interface ArchitectureNode {
  id: string;
  type: ArchitectureNodeType;
  label: string;
  description?: string;
  confidence?: number;
  /** Layout hint, 0..1 normalized. Backend may omit; layout falls back to layers. */
  position?: { x: number; y: number };
  layer?: number;
  metadata?: {
    dependencies?: string[];
    consumers?: string[];
    sourcePath?: string;
    lines?: [number, number];
    dependencyCount?: number;
    consumerCount?: number;
    /** Real source excerpt the inference was drawn from. */
    snippet?: string;
    /** Language tag for the excerpt, e.g. "python", "tsx", "yaml". */
    snippetLanguage?: string;
    /** First line number of the excerpt in the source file. */
    snippetStart?: number;
    /** What ArchLens read out of the excerpt. */
    snippetSignals?: string[];
    [key: string]: unknown;
  };
}

export interface ArchitectureEdge {
  id: string;
  source: string;
  target: string;
  type: "imports" | "calls" | "reads" | "writes" | "queries";
  confidence?: number;
  label?: string;
}

export interface ArchitectureGraphData {
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
}

export interface AnalysisSummary {
  repository: string;
  branch: string;
  filesScanned: number;
  modules: number;
  apiRoutes: number;
  externalServices: number;
  circularDependencies: number;
  languages: { name: string; share: number }[];
}

export interface HealthMetric {
  key: string;
  label: string;
  value: number;
  /** 0..100 normalized score for the bar; value may be a raw figure. */
  score: number;
  unit?: string;
  hint?: string;
}

export interface ArchitectureHealth {
  score: number;
  grade: string;
  strengths: string[];
  warnings: string[];
  metrics: HealthMetric[];
}

export interface AIExplanation {
  nodeId: string;
  question: string;
  verdict: string;
  evidence: string[];
  confidence: number;
}

export type DiffChangeKind = "added" | "modified" | "removed";

export interface DiffChange {
  kind: DiffChangeKind;
  label: string;
  detail: string;
}

export interface ArchitectureDiffData {
  versionA: { label: string; graph: ArchitectureGraphData };
  versionB: { label: string; graph: ArchitectureGraphData };
  changes: DiffChange[];
}

export interface AnalysisStage {
  id: string;
  label: string;
  detail?: string;
}
