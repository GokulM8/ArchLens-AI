import { useRef, useState } from "react";
import { FileArchive, Github } from "lucide-react";
import { DEMO_MODE } from "@/lib/config";

interface RepositoryInputProps {
  onSubmit: (source: string, kind: "git" | "zip", file?: File | null) => void;
}

export function RepositoryInput({ onSubmit }: RepositoryInputProps) {
  const [url, setUrl] = useState("");
  const [archive, setArchive] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const file = archive?.name ?? null;

  function pick(next: File | null) {
    if (next && !/\.zip$/i.test(next.name)) {
      setError("Upload a .zip archive of your repository.");
      return;
    }
    setError(null);
    setArchive(next);
  }

  function submit() {
    if (archive) return onSubmit(archive.name, "zip", archive);
    const trimmed = url.trim();
    if (!/^https?:\/\/.+\/.+/.test(trimmed)) {
      setError("Enter a repository URL such as https://github.com/org/project");
      return;
    }
    setError(null);
    onSubmit(trimmed, "git");
  }

  return (
    <div className="panel noise-texture relative mx-auto max-w-2xl p-6 sm:p-10">
      <h2 className="text-[clamp(1.7rem,4vw,2.6rem)] text-display text-foreground">
        ANALYZE YOUR REPOSITORY
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Upload a ZIP of a Python repository. ArchLens parses the source statically — nothing in the
        archive is executed.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) pick(dropped);
        }}
        className={`mt-8 rounded-md border border-dashed p-8 text-center transition-colors ${
          dragging ? "border-accent bg-accent/8" : "border-border-strong"
        }`}
      >
        <FileArchive size={20} className="mx-auto text-subtle" aria-hidden />
        <p className="mt-3 font-mono text-[0.8rem] text-foreground">
          {file ?? "Drop a ZIP file here"}
        </p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-3 font-mono text-[0.72rem] tracking-[0.14em] text-accent uppercase underline-offset-4 hover:underline"
        >
          {file ? "Choose another file" : "Browse files"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".zip"
          className="sr-only"
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
      </div>

      <div className="my-7 flex items-center gap-4">
        <span className="h-px flex-1 bg-border" aria-hidden />
        <span className="label-mono">or</span>
        <span className="h-px flex-1 bg-border" aria-hidden />
      </div>

      <label htmlFor="repo-url" className="label-mono">
        GitHub repository URL
      </label>
      <div className="mt-2 flex items-center gap-3 rounded-md border border-input bg-background px-3.5 py-3 focus-within:border-accent/60">
        <Github size={15} className="shrink-0 text-subtle" aria-hidden />
        <input
          id="repo-url"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            setArchive(null);
            setError(null);
          }}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="https://github.com/org/project"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? "repo-url-error" : undefined}
          className="w-full bg-transparent font-mono text-[0.82rem] text-foreground placeholder:text-subtle/70 focus:outline-none"
        />
      </div>
      {error && (
        <p id="repo-url-error" className="mt-2 font-mono text-[0.72rem] text-destructive">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={submit}
        className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-md bg-accent px-6 py-4 font-mono text-[0.76rem] tracking-[0.14em] text-accent-foreground uppercase transition-transform duration-200 hover:-translate-y-px"
      >
        Analyze Repository <span aria-hidden>→</span>
      </button>

      <p className="mt-4 text-center font-mono text-[0.68rem] text-subtle">
        {DEMO_MODE
          ? "Demo mode · no backend is called and the bundled sample repository is shown"
          : "Archives are uploaded to your ArchLens backend and analysed there · Git URLs are not supported yet"}
      </p>
    </div>
  );
}
