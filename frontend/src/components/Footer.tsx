import { Link } from "@tanstack/react-router";

export function Footer() {
  return (
    <footer className="hairline mt-8">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-10 px-5 py-14 sm:px-8 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="font-mono text-[0.8rem] tracking-[0.32em]">ARCHLENS</p>
          <p className="mt-3 max-w-xs text-sm text-muted-foreground">Understand your codebase.</p>
        </div>

        <nav aria-label="Footer" className="flex flex-wrap gap-x-10 gap-y-3">
          <Link to="/" className="text-sm text-muted-foreground hover:text-foreground">
            Product
          </Link>
          <Link to="/architecture" className="text-sm text-muted-foreground hover:text-foreground">
            Architecture
          </Link>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer noopener"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            GitHub
          </a>
          <Link to="/" hash="technologies" className="text-sm text-muted-foreground hover:text-foreground">
            Docs
          </Link>
          <Link to="/privacy" className="text-sm text-muted-foreground hover:text-foreground">
            Privacy
          </Link>
          <Link to="/terms" className="text-sm text-muted-foreground hover:text-foreground">
            Terms
          </Link>
        </nav>
      </div>
      <div className="mx-auto max-w-[1400px] px-5 pb-10 sm:px-8">
        <p className="label-mono">© 2026 ArchLens AI</p>
      </div>
    </footer>
  );
}
