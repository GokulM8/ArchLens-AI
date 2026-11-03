/**
 * Resolution of the API base URL from `VITE_API_BASE_URL`.
 *
 * TanStack Start (Vite) replaces `import.meta.env.VITE_*` at BUILD time: the
 * value is baked into both the browser bundle and the SSR bundle, so changing
 * it on a host such as Render requires a rebuild, not just a restart.
 *
 * Kept free of `import.meta` and path aliases so vite.config.ts and the
 * Node test runner can import it directly.
 */

export const DEFAULT_API_BASE = "/api";

/**
 * Normalise a configured base URL:
 *  - empty/unset → the same-origin `/api` prefix (Vite dev proxy, nginx);
 *  - an absolute `http(s)://host[/path]` URL → itself without trailing slashes
 *    (the backend on another origin, e.g. a separate Render service);
 *  - a path starting with `/` → itself without trailing slashes.
 * Anything else (a bare host, a protocol-relative URL, query or fragment) is
 * rejected, because it would silently send requests to the wrong place.
 */
export function resolveApiBase(raw: string | undefined | null): string {
  const value = (raw ?? "").trim();
  if (!value) return DEFAULT_API_BASE;

  if (/^https?:\/\//i.test(value)) {
    let url: URL;
    try {
      url = new URL(value);
    } catch {
      throw new Error(`VITE_API_BASE_URL is not a valid URL: ${value}`);
    }
    if (url.search || url.hash || url.username || url.password) {
      throw new Error(
        `VITE_API_BASE_URL must not contain credentials, a query or a fragment: ${value}`,
      );
    }
    return `${url.origin}${url.pathname}`.replace(/\/+$/, "");
  }

  if (value.startsWith("/") && !value.startsWith("//")) {
    return value.replace(/\/+$/, "") || DEFAULT_API_BASE;
  }

  throw new Error(
    `VITE_API_BASE_URL must be an absolute http(s) URL (e.g. https://archlens-backend.onrender.com) or a path starting with "/": ${value}`,
  );
}

export function isAbsoluteApiBase(base: string): boolean {
  return /^https?:\/\//i.test(base);
}

/**
 * Build-time check used by vite.config.ts. When `requireAbsolute` is set
 * (ARCHLENS_REQUIRE_ABSOLUTE_API_URL=true, as on Render where no proxy serves
 * `/api`), a relative or missing base fails the build instead of producing a
 * frontend that calls itself.
 */
export function checkBuildApiBase(raw: string | undefined, requireAbsolute: boolean): string {
  const base = resolveApiBase(raw);
  if (requireAbsolute && !isAbsoluteApiBase(base)) {
    throw new Error(
      "VITE_API_BASE_URL must be set to the backend's absolute URL (e.g. https://archlens-backend.onrender.com) " +
        "because ARCHLENS_REQUIRE_ABSOLUTE_API_URL=true: there is no proxy serving /api in this deployment.",
    );
  }
  return base;
}
