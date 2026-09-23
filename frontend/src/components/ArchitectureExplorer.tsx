import { useState } from "react";
import { mockGraph } from "@/data/mockArchitecture";
import type { ArchitectureGraphData } from "@/types/architecture";
import { ArchitectureGraph } from "./graph/ArchitectureGraph";
import { NodeInspector } from "./NodeInspector";
import { SectionHeading } from "./SectionHeading";

interface ArchitectureExplorerProps {
  data?: ArchitectureGraphData;
  withHeading?: boolean;
}

export function ArchitectureExplorer({
  data = mockGraph,
  withHeading = true,
}: ArchitectureExplorerProps) {
  const [selected, setSelected] = useState<string | null>("prediction");
  const node = data.nodes.find((n) => n.id === selected) ?? null;

  return (
    <section id="architecture" className="border-t border-border py-24 sm:py-32">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        {withHeading && (
          <SectionHeading
            index="03"
            eyebrow="Architecture visualization"
            title={
              <>
                SEE THE SYSTEM.
                <br />
                NOT JUST THE FILES.
              </>
            }
            copy="Pan, zoom and select components. Every node is inferred from real import edges, route registrations and call sites."
          />
        )}

        <div className="mt-14 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="panel relative h-[460px] overflow-hidden sm:h-[560px] lg:h-[640px]">
            <div className="absolute inset-x-0 top-0 z-10 flex items-center justify-between border-b border-border bg-surface/80 px-4 py-3 backdrop-blur-sm">
              <p className="font-mono text-[0.7rem] tracking-[0.16em] text-subtle uppercase">
                graph.json · 9 components · 10 edges
              </p>
              <p className="hidden font-mono text-[0.68rem] text-subtle sm:block">
                drag to pan · click a node
              </p>
            </div>
            <div className="h-full pt-11">
              <ArchitectureGraph data={data} selectedId={selected} onSelect={setSelected} />
            </div>
          </div>

          <NodeInspector node={node} onClose={() => setSelected(null)} />
        </div>
      </div>
    </section>
  );
}
