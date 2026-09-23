import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SectionHeadingProps {
  index?: string;
  eyebrow?: string;
  title: ReactNode;
  copy?: ReactNode;
  className?: string;
  align?: "left" | "center";
}

export function SectionHeading({
  index,
  eyebrow,
  title,
  copy,
  className,
  align = "left",
}: SectionHeadingProps) {
  return (
    <div className={cn(align === "center" && "mx-auto max-w-3xl text-center", className)}>
      {(index || eyebrow) && (
        <p className="label-mono flex items-center gap-3">
          {index && <span className="text-accent">{index}</span>}
          {eyebrow}
        </p>
      )}
      <h2 className="mt-5 text-[clamp(2.1rem,5.4vw,4.2rem)] text-display text-foreground">{title}</h2>
      {copy && (
        <p
          className={cn(
            "mt-6 max-w-xl text-[0.98rem] leading-relaxed text-muted-foreground",
            align === "center" && "mx-auto",
          )}
        >
          {copy}
        </p>
      )}
    </div>
  );
}
