import { Link } from "@tanstack/react-router";
import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";

const links = [
  { label: "Product", to: "/", hash: "product" },
  { label: "How it works", to: "/", hash: "pipeline" },
  { label: "Architecture", to: "/architecture" },
  { label: "Docs", to: "/", hash: "technologies" },
] as const;


export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-500 ${
        scrolled
          ? "border-b border-border bg-background/80 backdrop-blur-xl"
          : "border-b border-transparent"
      }`}
    >
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-5 sm:px-8"
      >
        <Link
          to="/"
          className="font-mono text-[0.8rem] font-medium tracking-[0.32em] text-foreground"
        >
          ARCHLENS
        </Link>

        <ul className="hidden items-center gap-8 md:flex">
          {links.map((link) => (
            <li key={link.label}>
              <Link
                to={link.to}
                {...("hash" in link ? { hash: link.hash } : {})}

                className="text-[0.82rem] text-muted-foreground transition-colors hover:text-foreground"
              >
                {link.label}
              </Link>
            </li>
          ))}
          <li>
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer noopener"
              className="text-[0.82rem] text-muted-foreground transition-colors hover:text-foreground"
            >
              GitHub
            </a>
          </li>
        </ul>

        <div className="flex items-center gap-3">
          <Link
            to="/analyze"
            className="hidden items-center gap-2 rounded-md bg-accent px-4 py-2 font-mono text-[0.72rem] tracking-[0.12em] text-accent-foreground uppercase transition-transform duration-200 hover:-translate-y-px md:inline-flex"
          >
            Analyze Repository <span aria-hidden>→</span>
          </Link>
          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-foreground md:hidden"
          >
            {open ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>
      </nav>

      {open && (
        <div className="border-t border-border bg-background/95 px-5 pb-6 pt-4 backdrop-blur-xl md:hidden">
          <ul className="flex flex-col gap-1">
            {links.map((link) => (
              <li key={link.label}>
                <Link
                  to={link.to}
                  {...("hash" in link ? { hash: link.hash } : {})}

                  onClick={() => setOpen(false)}
                  className="block py-3 font-mono text-sm tracking-[0.08em] text-muted-foreground uppercase"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <Link
            to="/analyze"
            onClick={() => setOpen(false)}
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-3 font-mono text-xs tracking-[0.14em] text-accent-foreground uppercase"
          >
            Analyze Repository <span aria-hidden>→</span>
          </Link>
        </div>
      )}
    </header>
  );
}
