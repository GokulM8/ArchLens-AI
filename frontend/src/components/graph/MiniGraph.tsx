import type { ArchitectureGraphData } from "@/types/architecture";
import { cn } from "@/lib/utils";

interface MiniGraphProps {
  data: ArchitectureGraphData;
  /** Ids rendered with the accent treatment (e.g. diff additions). */
  emphasis?: string[];
  className?: string;
  animate?: boolean;
}

/**
 * Lightweight declarative graph for compact contexts (diff, backgrounds).
 * Consumes the same ArchitectureGraphData contract as the interactive canvas.
 * Visual language mirrors the hero graph: routed connections, typed cards,
 * confidence bars.
 */
export function MiniGraph({ data, emphasis = [], className, animate = true }: MiniGraphProps) {
  const pos = (id: string) => data.nodes.find((n) => n.id === id)?.position ?? { x: 0.5, y: 0.5 };

  return (
    <div className={cn("relative h-full w-full", className)}>
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden
      >
        <defs>
          <marker
            id="mini-arrow"
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M0 0.5 L7.5 4 L0 7.5 Z" className="fill-accent/70" />
          </marker>
        </defs>
        {data.edges.map((edge, i) => {
          const a = pos(edge.source);
          const b = pos(edge.target);
          const hot = emphasis.includes(edge.source) || emphasis.includes(edge.target);
          const x1 = a.x * 100;
          const y1 = a.y * 100;
          const x2 = b.x * 100;
          const y2 = b.y * 100;
          const mx = (x1 + x2) / 2;
          const d = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
          return (
            <path
              key={edge.id}
              d={d}
              fill="none"
              vectorEffect="non-scaling-stroke"
              markerEnd={hot ? "url(#mini-arrow)" : undefined}
              className={hot ? "stroke-accent" : "stroke-border-strong"}
              strokeWidth={hot ? 1.4 : 1}
              strokeDasharray={hot ? "4 4" : undefined}
              style={
                hot && animate
                  ? { animation: `dash-flow 1.6s linear infinite`, animationDelay: `${i * 0.1}s` }
                  : undefined
              }
            />
          );
        })}
      </svg>

      {data.nodes.map((node) => {
        const hot = emphasis.includes(node.id);
        const confidence = Math.round((node.confidence ?? 0.85) * 100);
        return (
          <div
            key={node.id}
            className={cn(
              "absolute -translate-x-1/2 -translate-y-1/2 rounded-lg border px-2.5 py-1.5 whitespace-nowrap shadow-md transition-colors",
              hot
                ? "border-accent/70 bg-accent/10 shadow-accent/10"
                : "border-border-strong bg-surface-raised",
            )}
            style={{
              left: `${(node.position?.x ?? 0.5) * 100}%`,
              top: `${(node.position?.y ?? 0.5) * 100}%`,
            }}
          >
            <p className="font-blueprint-mono text-[0.55rem] tracking-[0.13em] text-muted-foreground uppercase">
              {node.type}
            </p>

            <p
              className={cn(
                "font-blueprint text-[0.66rem] leading-tight font-semibold",
                hot ? "text-accent" : "text-foreground",
              )}
            >
              {node.label}
            </p>

            <div className="mt-1 h-0.5 w-full overflow-hidden rounded-full bg-border">
              <div
                className={cn("h-full rounded-full", hot ? "bg-accent" : "bg-accent/60")}
                style={{ width: `${confidence}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
