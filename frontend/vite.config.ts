import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import tsConfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tsConfigPaths(), tailwindcss(), tanstackStart(), react()],
  server: {
    proxy: {
      // Dev proxy: the browser calls same-origin /api/* and Vite forwards to
      // the ArchLens backend (Docker maps it to 8001). Override with
      // VITE_BACKEND_PROXY_TARGET if the backend runs elsewhere.
      "/api": {
        target: process.env['VITE_BACKEND_PROXY_TARGET'] ?? "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
