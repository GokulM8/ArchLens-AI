import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import tsConfigPaths from "vite-tsconfig-paths";

import { checkBuildApiBase } from "./src/lib/apiBase.ts";

// VITE_API_BASE_URL is baked into the bundles at build time. Fail the build on
// a malformed value, and on a relative one where no proxy serves /api (Render
// sets ARCHLENS_REQUIRE_ABSOLUTE_API_URL=true).
checkBuildApiBase(
  process.env["VITE_API_BASE_URL"],
  process.env["ARCHLENS_REQUIRE_ABSOLUTE_API_URL"] === "true",
);

export default defineConfig({
  plugins: [tsConfigPaths(), tailwindcss(), tanstackStart(), react()],
  server: {
    proxy: {
      // Dev proxy: the browser calls same-origin /api/* and Vite forwards to
      // the ArchLens backend (`uvicorn app.api:app` listens on 8000). Override
      // with VITE_BACKEND_PROXY_TARGET if the backend runs elsewhere.
      "/api": {
        target: process.env["VITE_BACKEND_PROXY_TARGET"] ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
