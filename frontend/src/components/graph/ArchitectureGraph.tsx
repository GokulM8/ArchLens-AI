import { ClientOnly } from "@tanstack/react-router";
import { Suspense, lazy } from "react";
import type { ArchitectureCanvasProps } from "./ArchitectureCanvas";
import { cn } from "@/lib/utils";

const Canvas = lazy(() => import("./ArchitectureCanvas"));

function Skeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <p className="label-mono animate-pulse">loading graph…</p>
    </div>
  );
}

interface ArchitectureGraphProps extends ArchitectureCanvasProps {
  className?: string;
}

/** SSR-safe wrapper: the canvas renders after hydration only. */
export function ArchitectureGraph({ className, ...props }: ArchitectureGraphProps) {
  return (
    <div
      className={cn("relative h-full w-full", className)}
      role="application"
      aria-label="Interactive architecture graph"
    >
      <ClientOnly fallback={<Skeleton />}>
        <Suspense fallback={<Skeleton />}>
          <Canvas {...props} />
        </Suspense>
      </ClientOnly>
    </div>
  );
}
