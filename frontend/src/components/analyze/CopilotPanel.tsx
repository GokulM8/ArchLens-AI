import { useEffect, useState, type FormEvent } from "react";
import {
  ApiError,
  askCopilot,
  getCopilotStatus,
  type CopilotAnswer,
  type CopilotStatus,
} from "@/services/api";

type StatusLoad =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; status: CopilotStatus };

/**
 * Questions about one stored analysis, answered by the configured LLM.
 * Answers are model output and are labelled as such; the deterministic
 * results above stay the source of truth.
 */
export function CopilotPanel({ analysisId }: { analysisId: string }) {
  const [status, setStatus] = useState<StatusLoad>({ state: "loading" });
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<CopilotAnswer[]>([]);

  useEffect(() => {
    let cancelled = false;
    getCopilotStatus()
      .then((s) => !cancelled && setStatus({ state: "ready", status: s }))
      .catch((e: Error) => !cancelled && setStatus({ state: "error", message: e.message }));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setAnswers([]);
    setError(null);
  }, [analysisId]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || pending) return;
    setPending(true);
    setError(null);
    try {
      const answer = await askCopilot(analysisId, q);
      setAnswers((prev) => [answer, ...prev]);
      setQuestion("");
    } catch (err) {
      if (err instanceof ApiError && err.retryAfter !== undefined) {
        setError(`${err.message} (retry in ${err.retryAfter}s)`);
      } else {
        setError(err instanceof Error ? err.message : "The Copilot request failed.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="panel p-6 sm:p-8">
      <p className="label-mono flex flex-wrap items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
        Architecture Copilot
        <span className="normal-case tracking-normal text-subtle">
          · AI-generated answers, may be wrong
        </span>
      </p>

      {status.state === "loading" && (
        <p className="mt-4 text-sm text-muted-foreground" role="status">
          Checking whether the Copilot is available…
        </p>
      )}

      {status.state === "error" && (
        <p className="mt-4 text-sm text-destructive" role="alert">
          Could not check the Copilot: {status.message}
        </p>
      )}

      {status.state === "ready" && !status.status.enabled && (
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          The Copilot is not enabled on this server. The analysis above is complete without it.
        </p>
      )}

      {status.state === "ready" && status.status.enabled && (
        <>
          <p className="mt-4 max-w-3xl text-[0.82rem] leading-relaxed text-subtle">
            {status.status.disclosure}
          </p>
          <form onSubmit={submit} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-start">
            <label className="sr-only" htmlFor="copilot-question">
              Question about this analysis
            </label>
            <textarea
              id="copilot-question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              maxLength={status.status.maxQuestionChars}
              rows={2}
              placeholder="e.g. Which modules depend on the database layer?"
              className="min-h-[3.25rem] w-full flex-1 resize-y rounded-md border border-border-strong bg-transparent px-4 py-3 text-sm text-foreground placeholder:text-subtle focus:border-accent/60 focus:outline-none"
            />
            <button
              type="submit"
              disabled={pending || !question.trim()}
              className="rounded-md bg-accent px-5 py-3 font-mono text-[0.72rem] tracking-[0.14em] text-accent-foreground uppercase transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pending ? "Asking…" : "Ask"}
            </button>
          </form>
          {pending && (
            <p className="mt-3 text-[0.82rem] text-muted-foreground" role="status">
              Waiting for {status.status.provider ?? "the model"}… this can take up to a minute.
            </p>
          )}
        </>
      )}

      {error && (
        <p className="mt-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      {answers.length > 0 && (
        <ul className="mt-6 space-y-5">
          {answers.map((a, i) => (
            <li key={`${answers.length - i}`} className="border-t border-border pt-5">
              <p className="font-mono text-[0.78rem] text-foreground">{a.question}</p>
              {!a.grounded && (
                <p className="mt-2 text-[0.78rem] text-warning">
                  Some claims could not be matched to the analysis
                  {a.groundingWarning ? `: ${a.groundingWarning}` : "."} Treat them as unverified.
                </p>
              )}
              <p className="mt-3 max-w-3xl text-[0.92rem] leading-relaxed whitespace-pre-wrap text-muted-foreground">
                {a.answer}
              </p>
              <p className="label-mono mt-3 normal-case tracking-normal text-subtle">
                {a.provider} · {a.model} · {(a.latencyMs / 1000).toFixed(1)}s ·{" "}
                {a.usage.totalTokens} tokens
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
