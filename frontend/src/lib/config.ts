/**
 * Build-time frontend configuration (Vite `VITE_*` variables, see .env.example).
 * Nothing secret belongs here: every VITE_ value is embedded in the bundle.
 */

/** Base URL of the ArchLens API. Defaults to the same-origin `/api` prefix,
 *  which the Vite dev proxy and the nginx deployment both forward to FastAPI. */
export const API_BASE: string = (
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) || "/api"
).replace(/\/+$/, "");

/** Explicit demo mode: no backend, bundled sample data, clearly labelled. */
export const DEMO_MODE: boolean = import.meta.env["VITE_DEMO_MODE"] === "true";
