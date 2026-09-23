import { supportedTechnologies } from "@/data/mockArchitecture";
import { SectionHeading } from "./SectionHeading";

export function Technologies() {
  return (
    <section id="technologies" className="border-t border-border py-24 sm:py-32">
      <div className="mx-auto max-w-[1400px] px-5 sm:px-8">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)] lg:gap-20">
          <SectionHeading
            index="07"
            eyebrow="Supported ecosystems"
            title={
              <>
                ONE LENS.
                <br />
                MANY STACKS.
              </>
            }
            copy="Language support is deterministic per ecosystem — parsers, route conventions and module resolution are implemented explicitly, not guessed."
          />

          <ul className="grid grid-cols-1 gap-x-14 sm:grid-cols-2">
            {supportedTechnologies.map((tech) => (
              <li
                key={tech.name}
                className="group flex flex-col gap-1.5 border-b border-border py-7 transition-colors hover:border-accent/40 sm:py-8"
              >
                <span className="font-display text-[1.35rem] tracking-[-0.02em] text-foreground transition-colors group-hover:text-accent">
                  {tech.name}
                </span>
                <span className="font-mono text-[0.7rem] tracking-[0.08em] text-subtle uppercase">
                  {tech.note}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
