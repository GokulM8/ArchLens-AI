import { unzip } from "fflate";

/**
 * Reads an uploaded repository archive in the browser and turns it into plain
 * text files. Nothing is executed and nothing leaves the tab.
 */

export interface RepoFile {
  /** Repo-relative path, e.g. "src/api/client.ts". */
  path: string;
  name: string;
  ext: string;
  language: string;
  content: string;
  lines: number;
  bytes: number;
}

const MAX_FILES = 4000;
const MAX_FILE_BYTES = 240_000;

const IGNORED_SEGMENTS = [
  "node_modules",
  ".git",
  "dist",
  "build",
  ".next",
  ".venv",
  "venv",
  "__pycache__",
  ".turbo",
  "coverage",
  ".cache",
  "vendor",
];

const languageByExt: Record<string, string> = {
  ts: "typescript",
  tsx: "tsx",
  js: "javascript",
  jsx: "jsx",
  mjs: "javascript",
  cjs: "javascript",
  py: "python",
  rb: "ruby",
  go: "go",
  rs: "rust",
  java: "java",
  kt: "kotlin",
  php: "php",
  cs: "csharp",
  c: "c",
  h: "c",
  cpp: "cpp",
  hpp: "cpp",
  swift: "swift",
  sql: "sql",
  sh: "shell",
  yml: "yaml",
  yaml: "yaml",
  json: "json",
  toml: "toml",
  css: "css",
  scss: "scss",
  html: "html",
  md: "markdown",
  txt: "text",
  env: "text",
  dockerfile: "dockerfile",
};

export function languageOf(path: string): string {
  const name = path.split("/").pop() ?? path;
  if (/^dockerfile/i.test(name)) return "dockerfile";
  const ext = name.includes(".") ? (name.split(".").pop() ?? "").toLowerCase() : "";
  return languageByExt[ext] ?? "text";
}

function isTextCandidate(path: string): boolean {
  const name = (path.split("/").pop() ?? "").toLowerCase();
  if (name.startsWith(".")) return /^\.(env|gitignore|dockerignore|editorconfig)/.test(name);
  if (!name.includes(".")) return /^dockerfile|^makefile|^procfile/.test(name);
  return languageOf(path) !== "text" || /\.(txt|env|lock|cfg|ini|conf)$/.test(name);
}

function isIgnored(path: string): boolean {
  const parts = path.split("/");
  return parts.some((p) => IGNORED_SEGMENTS.includes(p));
}

/** Archives usually nest everything under "repo-main/" — drop that prefix. */
function stripRoot(paths: string[]): (path: string) => string {
  const firsts = new Set(paths.map((p) => p.split("/")[0] ?? ""));
  if (firsts.size !== 1) return (p) => p;
  const root = [...firsts][0];
  if (!root) return (p) => p;
  return (p) => (p.startsWith(`${root}/`) ? p.slice(root.length + 1) : p);
}

export interface IngestResult {
  /** Name derived from the archive / its root folder. */
  repository: string;
  files: RepoFile[];
  skipped: number;
}

export async function ingestArchive(file: File): Promise<IngestResult> {
  const buffer = new Uint8Array(await file.arrayBuffer());

  const entries = await new Promise<Record<string, Uint8Array>>((resolve, reject) => {
    unzip(buffer, (err, data) => (err ? reject(err) : resolve(data)));
  });

  const allPaths = Object.keys(entries).filter((p) => !p.endsWith("/"));
  if (allPaths.length === 0) throw new Error("The archive contains no files.");

  // Only treat the first segment as a repository root when every entry shares it.
  const firstSegment = (allPaths[0] ?? "").split("/")[0] ?? "";
  const sharedRoot =
    firstSegment && allPaths.every((p) => p.startsWith(`${firstSegment}/`)) ? firstSegment : "";
  const rootName = sharedRoot;
  const strip = stripRoot(allPaths);
  const decoder = new TextDecoder("utf-8", { fatal: false });

  const files: RepoFile[] = [];
  let skipped = 0;

  for (const raw of allPaths) {
    const path = strip(raw);
    if (!path || isIgnored(path) || !isTextCandidate(path)) {
      skipped += 1;
      continue;
    }
    const bytes = entries[raw];
    if (!bytes) continue;
    if (bytes.byteLength > MAX_FILE_BYTES) {
      skipped += 1;
      continue;
    }
    const content = decoder.decode(bytes);
    // Binary heuristic: NUL byte inside the decoded text.
    if (content.includes("\u0000")) {
      skipped += 1;
      continue;
    }
    const name = path.split("/").pop() ?? path;
    files.push({
      path,
      name,
      ext: name.includes(".") ? (name.split(".").pop() ?? "") : "",
      language: languageOf(path),
      content,
      lines: content.split("\n").length,
      bytes: bytes.byteLength,
    });
    if (files.length >= MAX_FILES) break;
  }

  if (files.length === 0) throw new Error("No readable source files were found in the archive.");

  const repository =
    (rootName && rootName !== "." ? rootName : file.name.replace(/\.zip$/i, "")) || "repository";

  return { repository, files, skipped };
}
