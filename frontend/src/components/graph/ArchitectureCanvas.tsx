import { useEffect, useMemo, useState, type ComponentType } from "react";
import {
  Boxes,
  Braces,
  Brain,
  Cloud,
  Database,
  Globe2,
  Layers,
  Maximize2,
  Minus,
  Plus,
  RotateCcw,
  Server,
  X,
  Zap,
} from "lucide-react";
import type { ArchitectureGraphData } from "@/types/architecture";
import { useReducedMotion } from "@/hooks/useCountUp";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const typeLabel: Record<string, string> = {
  client: "Client",
  gateway: "Gateway",
  service: "Service",
  module: "Module",
  model: "Model",
  datastore: "Datastore",
  cache: "Cache",
  external: "External",
};

const typeIcon: Record<string, ComponentType<{ className?: string }>> = {
  client: Globe2,
  gateway: Braces,
  service: Server,
  module: Layers,
  model: Brain,
  datastore: Database,
  cache: Zap,
  external: Cloud,
};

const VIEW_W = 1000;
const VIEW_H = 520;

type Point = { x: number; y: number };

export interface ArchitectureCanvasProps {
  data: ArchitectureGraphData;
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  interactive?: boolean;
}

export default function ArchitectureCanvas({
  data,
  selectedId = null,
  onSelect,
  interactive = true,
}: ArchitectureCanvasProps) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [hotEdge, setHotEdge] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const reduced = useReducedMotion();
  const focus = hovered ?? selectedId;

  const zoomBy = (delta: number) =>
    setZoom((z) => Math.min(2.2, Math.max(0.5, Math.round((z + delta) * 100) / 100)));

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [expanded]);

  /** Normalise arbitrary node coordinates into 6%–94% of the panel. */
  const layout = useMemo(() => {
    const pts = data.nodes.map((n) => n.position ?? { x: 0, y: 0 });
    const xs = pts.map((p) => p.x);
    const ys = pts.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = maxX - minX || 1;
    const spanY = maxY - minY || 1;
    const map: Record<string, Point> = {};
    data.nodes.forEach((node, i) => {
      const p = pts[i]!;
      map[node.id] = {
        x: 9 + ((p.x - minX) / spanX) * 82,
        y: 14 + ((p.y - minY) / spanY) * 72,
      };
    });
    return map;
  }, [data.nodes]);

  const linked = useMemo(() => {
    if (!focus) return new Set<string>();
    const set = new Set<string>([focus]);
    data.edges.forEach((e) => {
      if (e.source === focus) set.add(e.target);
      if (e.target === focus) set.add(e.source);
    });
    return set;
  }, [focus, data.edges]);

  const activeNode = data.nodes.find((n) => n.id === focus);
  const activeDeps =
    activeNode?.metadata?.dependencyCount ?? activeNode?.metadata?.dependencies?.length ?? 0;
  const activeConsumers = data.edges.filter((e) => e.target === activeNode?.id).length;

  function path(source: Point, target: Point) {
    const x1 = (source.x / 100) * VIEW_W + 82;
    const y1 = (source.y / 100) * VIEW_H;
    const x2 = (target.x / 100) * VIEW_W - 82;
    const y2 = (target.y / 100) * VIEW_H;
    const bend = Math.max(60, (x2 - x1) * 0.5);
    return `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
  }

  const panel = (
    <div
      className={cn(
        "relative flex w-full flex-col overflow-hidden rounded-xl border border-border-strong bg-surface/70 shadow-panel",
        expanded ? "h-full" : "h-full",
      )}
    >
      <div className="flex items-center justify-between gap-4 border-b border-border bg-surface-raised/45 px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="relative flex h-2 w-2 shrink-0" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-50" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <p className="truncate font-blueprint-mono text-[0.62rem] tracking-[0.14em] text-muted-foreground uppercase">
            Architecture blueprint · inferred graph
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-4 font-blueprint-mono text-[0.6rem] tracking-[0.12em] text-subtle uppercase lg:flex">
            <span>{data.nodes.length} nodes</span>
            <span>{data.edges.length} links</span>
          </div>
          <div className="flex items-center gap-1 rounded-md border border-border bg-surface/80 p-1">
            <button
              type="button"
              onClick={() => zoomBy(-0.1)}
              aria-label="Zoom out"
              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-accent"
            >
              <Minus className="h-3 w-3" aria-hidden />
            </button>
            <span className="min-w-[2.6rem] text-center font-blueprint-mono text-[0.58rem] text-subtle">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => zoomBy(0.1)}
              aria-label="Zoom in"
              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-accent"
            >
              <Plus className="h-3 w-3" aria-hidden />
            </button>
            <button
              type="button"
              onClick={() => setZoom(1)}
              aria-label="Reset zoom"
              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-secondary hover:text-accent"
            >
              <RotateCcw className="h-3 w-3" aria-hidden />
            </button>
          </div>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? "Close full view" : "Open graph in full view"}
            className="flex h-8 items-center gap-2 rounded-md border border-border bg-surface/80 px-2.5 font-blueprint-mono text-[0.58rem] tracking-[0.12em] text-muted-foreground uppercase transition-colors hover:border-accent/60 hover:text-accent"
          >
            {expanded ? <X className="h-3 w-3" aria-hidden /> : <Maximize2 className="h-3 w-3" aria-hidden />}
            <span className="hidden sm:inline">{expanded ? "Close" : "Full view"}</span>
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <div
          className="blueprint-grid relative h-full min-h-[470px] min-w-[900px]"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "top left",
            width: `${100 / zoom}%`,
            height: `${100 / zoom}%`,
          }}
        >
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_45%_50%,var(--accent-dim),transparent_28%)] opacity-30" />

          <svg
            className="absolute inset-0 h-full w-full"
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            preserveAspectRatio="none"
            role="img"
            aria-label="Inferred architecture graph with services, caches and datastores connected left to right."
          >
            <defs>
              <linearGradient id="arch-line" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="var(--border-strong)" />
                <stop offset="0.55" stopColor="var(--accent)" stopOpacity="0.72" />
                <stop offset="1" stopColor="var(--border-strong)" />
              </linearGradient>
              <filter id="arch-glow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {data.edges.map((edge, index) => {
              const source = layout[edge.source];
              const target = layout[edge.target];
              if (!source || !target) return null;
              const d = path(source, target);
              const hot = hotEdge === edge.id || focus === edge.source || focus === edge.target;
              const dimmed = focus !== null && !hot;
              const isDataLink =
                edge.type === "queries" || edge.type === "reads" || edge.type === "writes";

              return (
                <g key={edge.id}>
                  <path
                    d={d}
                    fill="none"
                    stroke="transparent"
                    strokeWidth="18"
                    className="cursor-pointer"
                    onMouseEnter={() => setHotEdge(edge.id)}
                    onMouseLeave={() => setHotEdge(null)}
                  />
                  <path
                    d={d}
                    fill="none"
                    stroke={hot ? "var(--accent)" : "url(#arch-line)"}
                    strokeWidth={hot ? 2 : 1.25}
                    strokeDasharray={isDataLink ? "5 6" : undefined}
                    strokeLinecap="round"
                    vectorEffect="non-scaling-stroke"
                    filter={hot ? "url(#arch-glow)" : undefined}
                    className={cn(
                      "pointer-events-none transition-opacity duration-200",
                      dimmed && "opacity-15",
                    )}
                    style={hot && !reduced ? { animation: "dash-flow 1.4s linear infinite" } : undefined}
                  />
                  {hot && !reduced && (
                    <circle r="3" fill="var(--accent)" className="pointer-events-none">
                      <animateMotion dur={`${1.8 + index * 0.08}s`} repeatCount="indefinite" path={d} />
                    </circle>
                  )}
                </g>
              );
            })}
          </svg>

          {data.nodes.map((node) => {
            const point = layout[node.id];
            if (!point) return null;
            const Icon = typeIcon[node.type] ?? Boxes;
            const pct =
              typeof node.confidence === "number" ? Math.round(node.confidence * 100) : null;
            const deps = node.metadata?.dependencyCount ?? node.metadata?.dependencies?.length ?? 0;
            const connected = focus === null || linked.has(node.id);
            const selected = focus === node.id;

            return (
              <Button
                key={node.id}
                type="button"
                variant="outline"
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(node.id)}
                onBlur={() => setHovered(null)}
                onClick={() =>
                  interactive && onSelect?.(node.id === selectedId ? null : node.id)
                }
                aria-pressed={selected}
                aria-label={`${node.label}, ${typeLabel[node.type] ?? node.type}${pct !== null ? `, ${pct} percent confidence` : ""}`}
                className={cn(
                  "group absolute z-10 flex h-[108px] w-[164px] -translate-x-1/2 -translate-y-1/2 flex-col items-stretch justify-start overflow-visible whitespace-normal rounded-lg border bg-surface p-0 text-left shadow-panel transition-[border-color,opacity,transform,box-shadow] duration-200 hover:-translate-y-[calc(50%+2px)] hover:bg-surface",
                  selected ? "border-accent shadow-glow" : "border-border-strong hover:border-accent/60",
                  !connected && "opacity-30",
                )}
                style={{ left: `${point.x}%`, top: `${point.y}%` }}
              >
                <span
                  className="absolute top-1/2 -left-1.5 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-accent/70 bg-surface shadow-glow"
                  aria-hidden
                />
                <span
                  className="absolute top-1/2 -right-1.5 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-accent/70 bg-surface shadow-glow"
                  aria-hidden
                />

                <span className="flex h-8 w-full items-center justify-between border-b border-border px-3">
                  <span className="flex items-center gap-2 font-blueprint-mono text-[0.57rem] tracking-[0.13em] text-muted-foreground uppercase">
                    <span
                      className={cn("h-1.5 w-1.5 rounded-full", selected ? "bg-accent" : "bg-accent/55")}
                    />
                    {typeLabel[node.type] ?? node.type}
                  </span>
                  {pct !== null && (
                    <span
                      className={cn(
                        "font-blueprint-mono text-[0.56rem]",
                        selected ? "text-accent" : "text-subtle",
                      )}
                    >
                      {pct}%
                    </span>
                  )}
                </span>
                <span className="flex w-full items-center gap-3 px-3 py-3">
                  <span
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-secondary text-muted-foreground transition-colors",
                      selected && "border-accent/40 text-accent",
                    )}
                  >
                    <Icon className="h-4 w-4" aria-hidden />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-blueprint text-[0.78rem] font-semibold text-foreground">
                      {node.label}
                    </span>
                    <span className="mt-1 block truncate font-blueprint-mono text-[0.52rem] text-subtle">
                      {deps} dependencies
                    </span>
                  </span>
                </span>
              </Button>
            );
          })}

          {activeNode && (
            <div
              className="absolute bottom-5 left-5 z-20 flex items-center gap-5 rounded-md border border-border-strong bg-popover/90 px-4 py-2.5 shadow-panel backdrop-blur-md"
              role="status"
            >
              <div>
                <p className="font-blueprint-mono text-[0.55rem] tracking-[0.14em] text-accent uppercase">
                  Selected
                </p>
                <p className="mt-1 font-blueprint text-xs font-semibold text-foreground">
                  {activeNode.label}
                </p>
              </div>
              <dl className="flex gap-4 border-l border-border pl-4 font-blueprint-mono text-[0.56rem] text-subtle">
                <div>
                  <dt>Deps</dt>
                  <dd className="mt-1 text-foreground">{activeDeps}</dd>
                </div>
                <div>
                  <dt>Uses</dt>
                  <dd className="mt-1 text-foreground">{activeConsumers}</dd>
                </div>
                {typeof activeNode.confidence === "number" && (
                  <div>
                    <dt>Signal</dt>
                    <dd className="mt-1 text-accent">{Math.round(activeNode.confidence * 100)}%</dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          <div className="absolute right-5 bottom-5 flex items-center gap-2 rounded-md border border-border bg-surface/85 px-3 py-2 font-blueprint-mono text-[0.55rem] tracking-[0.1em] text-subtle uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            Inference active
          </div>
        </div>
      </div>
    </div>
  );

  if (expanded) {
    return (
      <>
        <div className="flex h-full w-full items-center justify-center rounded-xl border border-dashed border-border-strong bg-surface/40 p-6 text-center font-blueprint-mono text-[0.6rem] tracking-[0.12em] text-subtle uppercase">
          Graph open in full view
        </div>
        <div
          className="fixed inset-0 z-50 flex flex-col bg-background/95 p-3 backdrop-blur-sm sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-label="Architecture graph, full view"
        >
          {panel}
        </div>
      </>
    );
  }

  return panel;
}
