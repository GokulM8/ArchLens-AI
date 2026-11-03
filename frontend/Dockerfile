# ArchLens AI frontend (TanStack Start SSR, served by srvx)
# Build context: ./frontend  (see docker-compose.yml)

FROM oven/bun:1.4.3 AS build
WORKDIR /app
COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile
COPY . .
# Build-time, public configuration only (embedded in the browser AND SSR
# bundles; changing it needs a rebuild). Render passes the service's
# environment variables as build args with these names.
#   VITE_API_BASE_URL: "/api" behind nginx (Compose); the backend's absolute
#     URL when it is a separate service (Render).
#   ARCHLENS_REQUIRE_ABSOLUTE_API_URL=true makes the build fail unless
#     VITE_API_BASE_URL is an absolute http(s) URL.
ARG VITE_API_BASE_URL=/api
ARG VITE_DEMO_MODE=false
ARG ARCHLENS_REQUIRE_ABSOLUTE_API_URL=false
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_DEMO_MODE=$VITE_DEMO_MODE \
    ARCHLENS_REQUIRE_ABSOLUTE_API_URL=$ARCHLENS_REQUIRE_ABSOLUTE_API_URL
RUN bun run build

FROM oven/bun:1.4.3 AS deps
WORKDIR /app
COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile --production

FROM node:22-slim
WORKDIR /app
# PORT is the default only: Render (and other hosts) override it at runtime,
# and srvx reads it when no --port flag is given.
ENV NODE_ENV=production PORT=3000
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
# Build-context files can carry host-specific modes (e.g. 0700 from FAT/exFAT).
RUN chmod -R a+rX,go-w /app
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
# --dir . makes --static resolve from /app (srvx otherwise resolves it from the entry's directory).
# No --port: srvx listens on $PORT (default 3000 above); --host binds all interfaces.
CMD ["node", "node_modules/srvx/bin/srvx.mjs", "serve", "--prod", "--dir", ".", "--host", "0.0.0.0", "--entry", "./dist/server/server.js", "--static", "./dist/client"]
