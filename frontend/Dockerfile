# ArchLens AI frontend (TanStack Start SSR, served by srvx)
# Build context: ./frontend  (see docker-compose.yml)

FROM oven/bun:1.4.3 AS build
WORKDIR /app
COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile
COPY . .
# Build-time, public configuration only (embedded in the browser bundle).
ARG VITE_API_BASE_URL=/api
ARG VITE_DEMO_MODE=false
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_DEMO_MODE=$VITE_DEMO_MODE
RUN bun run build

FROM oven/bun:1.4.3 AS deps
WORKDIR /app
COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile --production

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production PORT=3000
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
# Build-context files can carry host-specific modes (e.g. 0700 from FAT/exFAT).
RUN chmod -R a+rX,go-w /app
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
# --dir . makes --static resolve from /app (srvx otherwise resolves it from the entry's directory).
CMD ["node", "node_modules/srvx/bin/srvx.mjs", "serve", "--prod", "--dir", ".", "--entry", "./dist/server/server.js", "--static", "./dist/client", "--port", "3000"]
