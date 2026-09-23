import { useMemo, useState, type ComponentType } from "react";
import { Bot, Braces, Database, Globe2, Server, Users } from "lucide-react";
import { heroGraph, heroNodeFacts } from "@/data/mockArchitecture";
import { useReducedMotion } from "@/hooks/useCountUp";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type Point = { x: number; y: number };

const nodeLayout: Record<string, Point> = {
  frontend: { x: 12, y: 50 },
  api: { x: 37, y: 50 },
  auth: { x: 64, y: 19 },
  users: { x: 64, y: 50 },
  ml: { x: 64, y: 81 },
  db: { x: 88, y: 50 },
};

const nodeIcons: Record<string, ComponentType<{ className?: string }>> = {
  frontend: Globe2,
  api: Braces,
  auth: Bot,
  users: Users,
  ml: Server,
  db: Database,
};

function connectionPath(source: Point, target: Point) {
  const x1 = source.x * 10 + 82;
  const y1 = source.y * 5.2;
  const x2 = target.x * 10 - 82;
  const y2 = target.y * 5.2;
  const bend = Math.max(60, (x2 - x1) * 0.5);
  return `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
}

export function HeroGraph({ className }: { className?: string }) {
  const [active, setActive] = useState<string | null>("api");
  const [hotEdge, setHotEdge] = useState<string | null>(null);
  const reduced = useReducedMotion();

  const neighbours = useMemo(() => {
    if (!active) return new Set<string>();
    const connected = new Set<string>([active]);
    heroGraph.edges.forEach((edge) => {
      if (edge.source === active) connected.add(edge.target);
      if (edge.target === active) connected.add(edge.source);
    });
    return connected;
  }, [active]);

  const activeNode = heroGraph.nodes.find((node) => node.id === active);
  const activeFacts = active ? heroNodeFacts[active] : undefined;

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border-strong bg-surface/70 shadow-panel",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-4 border-b border-border bg-surface-raised/45 px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="relative flex h-2 w-2 shrink-0" aria-hidden>
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-50" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
          </span>
          <p className="truncate font-blueprint-mono text-[0.62rem] tracking-[0.14em] text-muted-foreground uppercase">
            Architecture blueprint · live inference
          </p>
        </div>
        <div className="hidden items-center gap-4 font-blueprint-mono text-[0.6rem] tracking-[0.12em] text-subtle uppercase sm:flex">
          <span>{heroGraph.nodes.length} nodes</span>
          <span>{heroGraph.edges.length} links</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="blueprint-grid relative h-[470px] min-w-[900px] lg:h-[520px]">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_42%_50%,var(--accent-dim),transparent_27%)] opacity-30" />

          <svg
            className="absolute inset-0 h-full w-full"
            viewBox="0 0 1000 520"
            preserveAspectRatio="none"
            aria-label="Frontend connects to the API service, which branches to authentication, users, and prediction services before reaching the database."
            role="img"
          >
            <defs>
              <linearGradient id="blueprint-line" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="var(--border-strong)" />
                <stop offset="0.55" stopColor="var(--accent)" stopOpacity="0.72" />
                <stop offset="1" stopColor="var(--border-strong)" />
              </linearGradient>
              <filter id="blueprint-glow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {heroGraph.edges.map((edge, index) => {
              const source = nodeLayout[edge.source];
              const target = nodeLayout[edge.target];
              if (!source || !target) return null;
              const path = connectionPath(source, target);
              const hot = hotEdge === edge.id || active === edge.source || active === edge.target;
              const dimmed = active !== null && !hot;
              const isDataLink = edge.type === "queries";

              return (
                <g key={edge.id}>
                  <path
                    d={path}
                    fill="none"
                    stroke="transparent"
                    strokeWidth="18"
                    className="cursor-pointer"
                    onMouseEnter={() => setHotEdge(edge.id)}
                    onMouseLeave={() => setHotEdge(null)}
                  />
                  <path
                    d={path}
                    fill="none"
                    stroke={hot ? "var(--accent)" : "url(#blueprint-line)"}
                    strokeWidth={hot ? 2 : 1.25}
                    strokeDasharray={isDataLink ? "5 6" : undefined}
                    strokeLinecap="round"
                    vectorEffect="non-scaling-stroke"
                    filter={hot ? "url(#blueprint-glow)" : undefined}
                    className={cn("pointer-events-none transition-opacity duration-200", dimmed && "opacity-15")}
                    style={hot && !reduced ? { animation: "dash-flow 1.4s linear infinite" } : undefined}
                  />
                  {hot && !reduced && (
                    <circle r="3" fill="var(--accent)" className="pointer-events-none">
                      <animateMotion dur={`${1.8 + index * 0.08}s`} repeatCount="indefinite" path={path} />
                    </circle>
                  )}
                </g>
              );
            })}
          </svg>

          {heroGraph.nodes.map((node) => {
            const point = nodeLayout[node.id];
            if (!point) return null;
            const facts = heroNodeFacts[node.id];
            const Icon = nodeIcons[node.id] ?? Server;
            const connected = active === null || neighbours.has(node.id);
            const selected = active === node.id;

            return (
              <Button
                key={node.id}
                type="button"
                variant="outline"
                onMouseEnter={() => setActive(node.id)}
                onFocus={() => setActive(node.id)}
                aria-pressed={selected}
                aria-label={`${node.label}, ${facts?.type ?? node.type}, ${Math.round((facts?.confidence ?? 0) * 100)} percent confidence`}
                className={cn(
                  "group absolute z-10 flex h-[108px] w-[164px] -translate-x-1/2 -translate-y-1/2 flex-col items-stretch justify-start overflow-visible whitespace-normal rounded-lg border bg-surface p-0 text-left shadow-panel transition-[border-color,opacity,transform,box-shadow] duration-200 hover:-translate-y-[calc(50%+2px)] hover:bg-surface",
                  selected ? "border-accent shadow-glow" : "border-border-strong hover:border-accent/60",
                  !connected && "opacity-30",
                )}
                style={{ left: `${point.x}%`, top: `${point.y}%` }}
              >
                {node.id !== "frontend" && (
                  <span className="absolute top-1/2 -left-1.5 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-accent/70 bg-surface shadow-glow" aria-hidden />
                )}
                {node.id !== "db" && (
                  <span className="absolute top-1/2 -right-1.5 h-3 w-3 -translate-y-1/2 rounded-full border-2 border-accent/70 bg-surface shadow-glow" aria-hidden />
                )}

                <span className="flex h-8 w-full items-center justify-between border-b border-border px-3">
                  <span className="flex items-center gap-2 font-blueprint-mono text-[0.57rem] tracking-[0.13em] text-muted-foreground uppercase">
                    <span className={cn("h-1.5 w-1.5 rounded-full", selected ? "bg-accent" : "bg-accent/55")} />
                    {facts?.type ?? node.type}
                  </span>
                  <span className="font-blueprint-mono text-[0.56rem] text-subtle">{Math.round((facts?.confidence ?? 0) * 100)}%</span>
                </span>
                <span className="flex w-full items-center gap-3 px-3 py-3">
                  <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-secondary text-muted-foreground transition-colors", selected && "border-accent/40 text-accent")}>
                    <Icon className="h-4 w-4" aria-hidden />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-blueprint text-[0.78rem] font-semibold text-foreground">{node.label}</span>
                    <span className="mt-1 block truncate font-blueprint-mono text-[0.52rem] text-subtle">{facts?.dependencies ?? 0} dependencies</span>
                  </span>
                </span>
              </Button>
            );
          })}

          {activeNode && activeFacts && (
            <div className="absolute bottom-5 left-5 z-20 flex items-center gap-5 rounded-md border border-border-strong bg-popover/90 px-4 py-2.5 shadow-panel backdrop-blur-md" role="status">
              <div>
                <p className="font-blueprint-mono text-[0.55rem] tracking-[0.14em] text-accent uppercase">Selected</p>
                <p className="mt-1 font-blueprint text-xs font-semibold text-foreground">{activeNode.label}</p>
              </div>
              <dl className="flex gap-4 border-l border-border pl-4 font-blueprint-mono text-[0.56rem] text-subtle">
                <div><dt>Deps</dt><dd className="mt-1 text-foreground">{activeFacts.dependencies}</dd></div>
                <div><dt>Uses</dt><dd className="mt-1 text-foreground">{activeFacts.consumers}</dd></div>
                <div><dt>Signal</dt><dd className="mt-1 text-accent">{Math.round(activeFacts.confidence * 100)}%</dd></div>
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
}