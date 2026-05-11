# Hilo People — frontend Dockerfile (multi-stage).
#
# Slice:  P00-S02-T001 — Docker compose services
# Phase:  P00 Scaffold + Design System
# Source: TECHNICAL_GUIDE §11.2 Build targets
#
# STAGE 1 (builder): node:20-alpine; runs `npm ci && npm run build`.
# STAGE 2 (runtime): nginx:stable-alpine; serves /dist as SPA with try_files fallback.
#
# BUILD DEFERRED NOTE (R6):
#   Stage 1 requires:
#     - frontend/package-lock.json (created by T002)
#     - frontend/vite.config.ts    (created by T002)
#     - frontend/index.html        (created by T002)
#     - frontend/src/main.tsx      (created by T002)
#   Until T002 merges, `docker compose build frontend` WILL FAIL on `npm ci`.
#   This is intentional and documented. The productive build is validated
#   in P06-S01-T001 "Production build and compose smoke".
#
#   ARG SKIP_BUILD=1 can be passed to skip the npm build step:
#     docker compose build --build-arg SKIP_BUILD=1 frontend
#   When SKIP_BUILD=1, the nginx stage copies a placeholder — resulting image
#   serves a minimal page. Useful only for compose syntax smoke testing.
#
# BUILD CONTEXT: repo root (docker-compose.yml uses `context: .`).
#   The .dockerignore at repo root excludes node_modules, dist, coverage.

# ── Stage 1: builder — with SKIP_BUILD guard ─────────────────────────────────
FROM node:20-alpine AS builder

ARG SKIP_BUILD=0

WORKDIR /build

# Copy all frontend source (includes package*.json, vite.config.ts, src/, etc.)
COPY frontend/ ./

# When SKIP_BUILD=0 (default): npm ci + npm run build.
# When SKIP_BUILD=1 (T002 not merged yet): create a minimal placeholder dist.
RUN echo "[builder] BEFORE: SKIP_BUILD=${SKIP_BUILD}" && \
    if [ "${SKIP_BUILD}" = "1" ]; then \
      echo "[builder] Skipping npm ci — T002 not merged, creating placeholder dist"; \
      mkdir -p /build/dist && \
      echo '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>Hilo People</title></head><body><p>Build pending: T002 not merged.</p></body></html>' > /build/dist/index.html && \
      echo "[builder] AFTER: placeholder dist created"; \
    else \
      echo "[builder] Running npm ci"; \
      npm ci && \
      echo "[builder] AFTER npm ci: running npm run build" && \
      npm run build && \
      echo "[builder] AFTER: build complete, dist ready"; \
    fi

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM nginx:stable-alpine AS runtime

# Copy nginx SPA config (try_files fallback for React Router)
# frontend/nginx.conf is created as a write_set extension in this slice.
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy static build output from builder
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
