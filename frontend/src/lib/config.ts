/**
 * Build-time frontend configuration (Vite `VITE_*` variables, see .env.example).
 * Nothing secret belongs here: every VITE_ value is embedded in the bundle.
 */

import { resolveApiBase } from "./apiBase";

/** Base URL of the ArchLens API (build-time). Defaults to the same-origin `/api`
 *  prefix, which the Vite dev proxy and the nginx deployment both forward to
 *  FastAPI. Set an absolute URL when the backend is a separate service (Render).
 *  Validated again at build time in vite.config.ts. */
export const API_BASE: string = resolveApiBase(
  import.meta.env["VITE_API_BASE_URL"] as string | undefined,
);

/** Explicit demo mode: no backend, bundled sample data, clearly labelled. */
export const DEMO_MODE: boolean = import.meta.env["VITE_DEMO_MODE"] === "true";
