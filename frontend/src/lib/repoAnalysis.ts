import type { RepoFile } from "@/lib/repoIngest";
import type {
  AIExplanation,
  AnalysisSummary,
  ArchitectureEdge,
  ArchitectureGraphData,
  ArchitectureHealth,
  ArchitectureNode,
  ArchitectureNodeType,
} from "@/types/architecture";
import type { AnalysisResult } from "@/services/api";

/**
 * Static analysis of an uploaded repository, entirely in the browser.
 * Reads imports, groups files into components, and produces the same
 * backend-shaped payloads the rest of the UI already consumes.
 */

export interface IndexedFile {
  path: string;
  language: string;
  lines: number;
  bytes: number;
  content: string;
  /** In-repo files this file imports. */
  imports: string[];
  /** Package names imported from outside the repo. */
  externals: string[];
  /** In-repo files that import this file. */
  usedBy: string[];
  /** Component (graph node) this file belongs to. */
  componentId: string;
  /** Exported / top-level symbol names, best effort. */
  symbols: string[];
}

export interface RepoIndex {
  repository: string;
  files: Record<string, IndexedFile>;
  paths: string[];
  /** componentId -> file paths */
  componentFiles: Record<string, string[]>;
  externals: { name: string; count: number }[];
}

export interface RepoAnalysis {
  result: AnalysisResult;
  index: RepoIndex;
}

const CODE_LANGS = new Set([
  "typescript",
  "tsx",
  "javascript",
  "jsx",
  "python",
  "go",
  "java",
  "ruby",
  "rust",
  "php",
  "csharp",
  "kotlin",
  "swift",
  "c",
  "cpp",
]);

/* ------------------------------- imports -------------------------------- */

const JS_IMPORT = /(?:import\s[^'"]*?from\s*|import\s*|require\(\s*|from\s*)['"]([^'"]+)['"]/g;
const PY_IMPORT = /^[ \t]*(?:from\s+([\w.]+)\s+import|import\s+([\w.,\t ]+))/gm;
const GO_IMPORT = /"([\w./-]+)"/g;

function rawImports(file: RepoFile): string[] {
  const out: string[] = [];
  const { content, language } = file;

  if (language === "python") {
    for (const m of content.matchAll(PY_IMPORT)) {
      const mod = m[1] ?? m[2] ?? "";
      mod
        .split(",")
        .map((s) => s.trim().split(" ")[0] ?? "")
        .filter(Boolean)
        .forEach((s) => out.push(s));
    }
    return out;
  }

  if (language === "go") {
    const block = content.match(/import\s*\(([\s\S]*?)\)/);
    const scope = block?.[1] ?? content.slice(0, 2000);
    for (const m of scope.matchAll(GO_IMPORT)) if (m[1]) out.push(m[1]);
    return out;
  }

  for (const m of content.matchAll(JS_IMPORT)) if (m[1]) out.push(m[1]);
  return out;
}

function normalize(path: string): string {
  const parts: string[] = [];
  for (const part of path.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") parts.pop();
    else parts.push(part);
  }
  return parts.join("/");
}

const RESOLVE_EXT = [
  "",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".mjs",
  ".py",
  ".go",
  ".rb",
  ".java",
  "/index.ts",
  "/index.tsx",
  "/index.js",
  "/index.jsx",
  "/__init__.py",
];

function resolveImport(spec: string, from: string, known: Set<string>): string | null {
  const dir = from.split("/").slice(0, -1).join("/");

  const candidates: string[] = [];
  if (spec.startsWith(".")) {
    candidates.push(normalize(`${dir}/${spec}`));
  } else if (spec.startsWith("@/") || spec.startsWith("~/")) {
    const rest = spec.slice(2);
    candidates.push(normalize(`src/${rest}`), normalize(rest), normalize(`app/${rest}`));
  } else if (spec.includes("/") || /^[\w.]+$/.test(spec)) {
    // Python-style dotted module or bare in-repo path.
    const dotted = spec.replace(/\./g, "/");
    candidates.push(normalize(dotted), normalize(`${dir}/${dotted}`), normalize(`src/${dotted}`));
  }

  for (const base of candidates) {
    if (!base) continue;
    for (const ext of RESOLVE_EXT) {
      const candidate = `${base}${ext}`;
      if (known.has(candidate)) return candidate;
    }
  }
  return null;
}

function externalName(spec: string): string | null {
  if (spec.startsWith(".") || spec.startsWith("/") || spec.startsWith("@/") || spec.startsWith("~/"))
    return null;
  if (spec.startsWith("@")) return spec.split("/").slice(0, 2).join("/");
  return spec.split("/")[0] ?? null;
}

/* ------------------------------ components ------------------------------ */

const typeRules: { test: RegExp; type: ArchitectureNodeType }[] = [
  { test: /^(web|frontend|client|ui|app|pages|views|components|src\/pages)$/i, type: "client" },
  { test: /(gateway|proxy|nginx|traefik|edge|ingress)/i, type: "gateway" },
  { test: /(service|services|api|server|backend|routes|router|handlers|controllers|functions|endpoints)/i, type: "service" },
  { test: /(model|models|ml|training|inference|weights)/i, type: "model" },
  { test: /(db|database|data|migrations|prisma|schema|sql|repository|repositories|store|stores)/i, type: "datastore" },
  { test: /(cache|redis|queue|broker|kafka)/i, type: "cache" },
  { test: /(infra|deploy|docker|k8s|terraform|ci|scripts)/i, type: "external" },
];

function inferType(group: string, files: RepoFile[]): ArchitectureNodeType {
  for (const rule of typeRules) if (rule.test.test(group)) return rule.type;
  const joined = files
    .slice(0, 8)
    .map((f) => f.content.slice(0, 1500))
    .join("\n");
  if (/@app\.(get|post|put|delete)|@router\.|express\(|fastify|createServer/i.test(joined))
    return "service";
  if (/createRoot|ReactDOM|useState\(|<\w+\s/i.test(joined)) return "client";
  if (/CREATE TABLE|sqlalchemy|mongoose|prisma|knex/i.test(joined)) return "datastore";
  return "module";
}

const typeDescription: Record<ArchitectureNodeType, string> = {
  client: "User-facing code. Renders the interface and calls into the backend.",
  gateway: "Request boundary. Routes and forwards traffic to internal code.",
  service: "Business logic. Owns request handling for a bounded responsibility.",
  module: "Shared implementation reused by other parts of the system.",
  model: "Model and inference code loaded by services.",
  datastore: "Data access and persistence layer.",
  cache: "Short-lived storage in front of expensive work.",
  external: "Infrastructure and tooling around the application.",
};

const layerOrder: ArchitectureNodeType[] = [
  "client",
  "gateway",
  "service",
  "module",
  "model",
  "cache",
  "datastore",
  "external",
];

function groupOf(path: string): string {
  const parts = path.split("/");
  if (parts.length === 1) return "root";
  if (parts[0] === "src" && parts.length > 2) return `src/${parts[1]}`;
  return parts[0] ?? "root";
}

function titleize(group: string): string {
  return group
    .split(/[/_\-.]/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

/* -------------------------------- snippets ------------------------------ */

function snippetOf(file: IndexedFile): { code: string; start: number } {
  const lines = file.content.split("\n");
  let start = 0;
  while (start < lines.length && (lines[start] ?? "").trim() === "") start += 1;
  // Prefer the first definition-ish line so the excerpt shows real logic.
  const anchor = lines.findIndex((l) =>
    /^(export\s|def\s|class\s|function\s|async\s+def\s|const\s\w+\s*=\s*(async\s*)?\(|@app\.|@router\.|func\s)/.test(
      l.trim(),
    ),
  );
  if (anchor > start) start = Math.max(0, anchor - 2);
  const slice = lines.slice(start, start + 14);
  return { code: slice.join("\n").replace(/\s+$/, ""), start: start + 1 };
}

/* -------------------------------- analysis ------------------------------ */

function countMatches(content: string, re: RegExp): number {
  return (content.match(re) ?? []).length;
}

export function analyzeRepository(repository: string, files: RepoFile[]): RepoAnalysis {
  const known = new Set(files.map((f) => f.path));

  const indexed: Record<string, IndexedFile> = {};
  const externalCount = new Map<string, number>();

  for (const file of files) {
    const specs = rawImports(file);
    const imports = new Set<string>();
    const externals = new Set<string>();

    for (const spec of specs) {
      const resolved = resolveImport(spec, file.path, known);
      if (resolved && resolved !== file.path) {
        imports.add(resolved);
        continue;
      }
      const ext = externalName(spec);
      if (ext) {
        externals.add(ext);
        externalCount.set(ext, (externalCount.get(ext) ?? 0) + 1);
      }
    }

    const symbols = [
      ...file.content.matchAll(
        /^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function|class|def|const|interface|type|func)\s+(\w+)/gm,
      ),
    ]
      .map((m) => m[1] ?? "")
      .filter(Boolean)
      .slice(0, 40);

    indexed[file.path] = {
      path: file.path,
      language: file.language,
      lines: file.lines,
      bytes: file.bytes,
      content: file.content,
      imports: [...imports],
      externals: [...externals],
      usedBy: [],
      componentId: "",
      symbols,
    };
  }

  for (const file of Object.values(indexed)) {
    for (const dep of file.imports) {
      const target = indexed[dep];
      if (target && !target.usedBy.includes(file.path)) target.usedBy.push(file.path);
    }
  }

  /* group files into components */
  const codeFiles = files.filter((f) => CODE_LANGS.has(f.language));
  const basis = codeFiles.length >= 4 ? codeFiles : files;

  const groups = new Map<string, RepoFile[]>();
  for (const file of basis) {
    const group = groupOf(file.path);
    const list = groups.get(group);
    if (list) list.push(file);
    else groups.set(group, [file]);
  }

  const ranked = [...groups.entries()]
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, 10);

  const componentFiles: Record<string, string[]> = {};
  const nodes: ArchitectureNode[] = [];

  const idOf = (group: string) => group.replace(/[^\w]+/g, "-").toLowerCase() || "root";

  for (const [group, groupFiles] of ranked) {
    const id = idOf(group);
    componentFiles[id] = groupFiles.map((f) => f.path);
    for (const f of groupFiles) {
      const entry = indexed[f.path];
      if (entry) entry.componentId = id;
    }
  }

  // Files outside the ranked groups still need a home for the explorer.
  for (const file of Object.values(indexed)) {
    if (!file.componentId) file.componentId = "other";
  }

  for (const [group, groupFiles] of ranked) {
    const id = idOf(group);
    const type = inferType(group, groupFiles);
    const paths = componentFiles[id] ?? [];

    const representative =
      paths
        .map((p) => indexed[p])
        .filter((f): f is IndexedFile => Boolean(f))
        .sort((a, b) => b.usedBy.length * 3 + b.lines - (a.usedBy.length * 3 + a.lines))[0] ?? null;

    const internalDeps = new Set<string>();
    const consumers = new Set<string>();
    let routeCount = 0;
    const groupExternals = new Set<string>();

    for (const p of paths) {
      const f = indexed[p];
      if (!f) continue;
      f.imports.forEach((dep) => {
        if (!paths.includes(dep)) internalDeps.add(dep);
      });
      f.usedBy.forEach((user) => {
        if (!paths.includes(user)) consumers.add(user);
      });
      f.externals.forEach((e) => groupExternals.add(e));
      routeCount += countMatches(
        f.content,
        /(@(?:app|router|api)\.(?:get|post|put|patch|delete)|\b(?:app|router)\.(?:get|post|put|patch|delete)\s*\(|@(?:Get|Post|Put|Delete)Mapping)/g,
      );
    }

    const snippet = representative ? snippetOf(representative) : null;
    const totalLines = paths.reduce((sum, p) => sum + (indexed[p]?.lines ?? 0), 0);

    const signals: string[] = [];
    if (representative)
      signals.push(
        `${paths.length} file${paths.length === 1 ? "" : "s"} under ${group}/ → grouped as one ${type}`,
      );
    if (routeCount > 0) signals.push(`${routeCount} route handler(s) declared here → service boundary`);
    if (internalDeps.size > 0)
      signals.push(
        `Imports ${[...internalDeps].slice(0, 3).join(", ")}${internalDeps.size > 3 ? ", …" : ""} → outgoing dependencies`,
      );
    if (consumers.size > 0)
      signals.push(`Imported by ${consumers.size} file(s) elsewhere → used across the system`);
    if (groupExternals.size > 0)
      signals.push(`External packages: ${[...groupExternals].slice(0, 5).join(", ")}`);

    const confidence = Math.min(
      0.99,
      0.62 + Math.min(0.2, paths.length / 40) + (routeCount > 0 ? 0.1 : 0) + (consumers.size ? 0.07 : 0),
    );

    nodes.push({
      id,
      type,
      label: titleize(group),
      description: `${typeDescription[type]} ${paths.length} file${paths.length === 1 ? "" : "s"}, ${totalLines.toLocaleString()} lines.`,
      confidence: Number(confidence.toFixed(2)),
      metadata: {
        dependencies: [...internalDeps].slice(0, 8),
        consumers: [...consumers].slice(0, 8),
        sourcePath: representative?.path ?? paths[0] ?? group,
        lines: representative ? [1, representative.lines] : undefined,
        dependencyCount: internalDeps.size,
        consumerCount: consumers.size,
        snippet: snippet?.code,
        snippetLanguage: representative?.language,
        snippetStart: snippet?.start,
        snippetSignals: signals,
        fileCount: paths.length,
        routeCount,
        groupPath: group,
      } as NonNullable<ArchitectureNode["metadata"]>,
    });
  }

  /* layout: layer by type, spread vertically */
  const byLayer = new Map<number, ArchitectureNode[]>();
  nodes.forEach((node) => {
    const layer = Math.max(0, layerOrder.indexOf(node.type));
    const list = byLayer.get(layer);
    if (list) list.push(node);
    else byLayer.set(layer, [node]);
  });
  const layers = [...byLayer.keys()].sort((a, b) => a - b);
  layers.forEach((layer, column) => {
    const list = byLayer.get(layer) ?? [];
    list.forEach((node, row) => {
      node.layer = column;
      node.position = {
        x: column * 260,
        y: 120 + row * 170 - ((list.length - 1) * 170) / 2 + 220,
      };
    });
  });

  /* edges between components, from real file imports */
  const edgeWeights = new Map<string, number>();
  for (const file of Object.values(indexed)) {
    for (const dep of file.imports) {
      const target = indexed[dep];
      if (!target) continue;
      if (file.componentId === target.componentId) continue;
      if (!componentFiles[file.componentId] || !componentFiles[target.componentId]) continue;
      const key = `${file.componentId}→${target.componentId}`;
      edgeWeights.set(key, (edgeWeights.get(key) ?? 0) + 1);
    }
  }

  const nodeType = new Map(nodes.map((n) => [n.id, n.type] as const));
  const edges: ArchitectureEdge[] = [...edgeWeights.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 26)
    .map(([key, weight]) => {
      const [source = "", target = ""] = key.split("→");
      const tt = nodeType.get(target);
      const type: ArchitectureEdge["type"] =
        tt === "datastore" ? "queries" : tt === "cache" ? "reads" : tt === "service" ? "calls" : "imports";
      return {
        id: `${source}-${target}`,
        source,
        target,
        type,
        confidence: Math.min(0.99, 0.7 + weight / 30),
        label: `${weight} import${weight === 1 ? "" : "s"}`,
      };
    });

  const graph: ArchitectureGraphData = { nodes, edges };

  /* summary */
  const bytesByLanguage = new Map<string, number>();
  for (const f of files) {
    if (f.language === "text" || f.language === "markdown" || f.language === "json") continue;
    bytesByLanguage.set(f.language, (bytesByLanguage.get(f.language) ?? 0) + f.bytes);
  }
  const totalLangBytes = [...bytesByLanguage.values()].reduce((a, b) => a + b, 0) || 1;
  const languages = [...bytesByLanguage.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, bytes]) => ({ name, share: bytes / totalLangBytes }));

  const apiRoutes = files.reduce(
    (sum, f) =>
      sum +
      countMatches(
        f.content,
        /(@(?:app|router|api)\.(?:get|post|put|patch|delete)|\b(?:app|router)\.(?:get|post|put|patch|delete)\s*\(|@(?:Get|Post|Put|Delete)Mapping)/g,
      ),
    0,
  );

  const circular = countCycles(indexed);

  const summary: AnalysisSummary = {
    repository,
    branch: "uploaded",
    filesScanned: files.length,
    modules: groups.size,
    apiRoutes,
    externalServices: externalCount.size,
    circularDependencies: circular,
    languages: languages.length ? languages : [{ name: "text", share: 1 }],
  };

  /* health */
  const avgLines = files.reduce((s, f) => s + f.lines, 0) / Math.max(1, files.length);
  const bigFiles = files.filter((f) => f.lines > 400).length;
  const orphanFiles = Object.values(indexed).filter(
    (f) => f.usedBy.length === 0 && f.imports.length === 0 && CODE_LANGS.has(f.language),
  ).length;
  const couplingRatio = edges.length / Math.max(1, nodes.length);

  const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));
  const metrics = [
    {
      key: "modularity",
      label: "Modularity",
      value: nodes.length,
      score: clamp(60 + nodes.length * 4 - couplingRatio * 12),
      unit: " components",
      hint: "Distinct components inferred from directory and import structure.",
    },
    {
      key: "coupling",
      label: "Coupling",
      value: Number(couplingRatio.toFixed(2)),
      score: clamp(100 - couplingRatio * 22),
      unit: " edges/component",
      hint: "Average cross-component dependencies per component.",
    },
    {
      key: "cycles",
      label: "Cycle freedom",
      value: circular,
      score: clamp(100 - circular * 12),
      unit: " cycles",
      hint: "Import cycles found between files.",
    },
    {
      key: "size",
      label: "File size discipline",
      value: Math.round(avgLines),
      score: clamp(110 - avgLines / 4 - bigFiles * 2),
      unit: " avg lines",
      hint: `${bigFiles} file(s) exceed 400 lines.`,
    },
    {
      key: "reach",
      label: "Connectedness",
      value: orphanFiles,
      score: clamp(100 - (orphanFiles / Math.max(1, files.length)) * 160),
      unit: " isolated files",
      hint: "Source files with no imports in or out.",
    },
  ];

  const score = Math.round(metrics.reduce((s, m) => s + m.score, 0) / metrics.length);
  const grade = score >= 90 ? "A" : score >= 80 ? "B+" : score >= 70 ? "B" : score >= 60 ? "C" : "D";

  const strengths: string[] = [];
  const warnings: string[] = [];
  if (circular === 0) strengths.push("No import cycles detected between files.");
  else warnings.push(`${circular} import cycle(s) detected — they make refactoring risky.`);
  if (bigFiles === 0) strengths.push("No source file exceeds 400 lines.");
  else warnings.push(`${bigFiles} file(s) exceed 400 lines and likely hold mixed responsibilities.`);
  if (couplingRatio < 2) strengths.push("Components stay loosely coupled across directories.");
  else warnings.push("Cross-component imports are dense; boundaries are blurred.");
  if (orphanFiles > 0)
    warnings.push(`${orphanFiles} source file(s) are not connected to the import graph.`);
  if (apiRoutes > 0) strengths.push(`${apiRoutes} route handler(s) found and attributed to components.`);

  const health: ArchitectureHealth = {
    score,
    grade,
    strengths: strengths.length ? strengths : ["Structure parsed without anomalies."],
    warnings: warnings.length ? warnings : ["Nothing notable to flag."],
    metrics,
  };

  /* explanation for the most connected component */
  const focus =
    [...nodes].sort(
      (a, b) =>
        (b.metadata?.consumerCount ?? 0) +
        (b.metadata?.dependencyCount ?? 0) -
        ((a.metadata?.consumerCount ?? 0) + (a.metadata?.dependencyCount ?? 0)),
    )[0] ?? nodes[0];

  const explanation: AIExplanation = focus
    ? {
        nodeId: focus.id,
        question: `Why is ${focus.label} a ${focus.type}?`,
        verdict: `ArchLens classified ${focus.label} as a ${focus.type} because of how the code in ${focus.metadata?.["groupPath"] ?? focus.label} imports, is imported and handles requests.`,
        evidence: (focus.metadata?.snippetSignals as string[] | undefined) ?? [],
        confidence: focus.confidence ?? 0.8,
      }
    : { nodeId: "none", question: "", verdict: "", evidence: [], confidence: 0 };

  const topExternals = [...externalCount.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name]) => name);

  const aiSummary = [
    `${repository} contains ${files.length.toLocaleString()} readable files across ${groups.size} top-level areas. ArchLens reduced them to ${nodes.length} components connected by ${edges.length} dependency edges, all derived from real import statements in the code.`,
    languages.length
      ? `The codebase is primarily ${languages
          .slice(0, 3)
          .map((l) => `${l.name} (${Math.round(l.share * 100)}%)`)
          .join(", ")}. ${apiRoutes > 0 ? `${apiRoutes} route handler(s) were found, which anchors the service layer.` : "No HTTP route handlers were found, so the service layer is inferred from import direction instead."}`
      : "Language shares could not be determined.",
    topExternals.length
      ? `Third-party surface: ${topExternals.join(", ")}. These are the packages the code reaches outside the repository.`
      : "No third-party packages are imported.",
    `Architecture score ${score}/100 (${grade}). ${warnings[0] ?? strengths[0] ?? ""}`,
  ];

  const result: AnalysisResult = { summary, graph, health, explanation, aiSummary };

  const index: RepoIndex = {
    repository,
    files: indexed,
    paths: Object.keys(indexed).sort(),
    componentFiles,
    externals: [...externalCount.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count),
  };

  return { result, index };
}

/** Counts distinct back edges in the file import graph (cheap cycle proxy). */
function countCycles(files: Record<string, IndexedFile>): number {
  const state = new Map<string, 0 | 1 | 2>();
  let cycles = 0;

  const visit = (path: string, stack: Set<string>) => {
    state.set(path, 1);
    stack.add(path);
    for (const dep of files[path]?.imports ?? []) {
      if (!files[dep]) continue;
      if (stack.has(dep)) {
        cycles += 1;
        continue;
      }
      if (state.get(dep) !== 2) visit(dep, stack);
    }
    stack.delete(path);
    state.set(path, 2);
  };

  for (const path of Object.keys(files)) if (state.get(path) !== 2) visit(path, new Set());
  return cycles;
}
