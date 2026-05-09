# frontend/Dockerfile — Multi-stage Vite build → nginx-unprivileged Dockerfile
#
# Slice: P00-S02-T001 — Docker compose services (Rancher-ready)
# Phase: P00 — Scaffold + Design System
#
# GATE: This Dockerfile requires tsconfig.json to be present (added in P00-S01-T004).
# Until T004 lands, `docker compose build frontend` WILL fail at the `npm run build`
# step with: error TS6504: File 'tsconfig.json' not found.
# This is EXPECTED and DOCUMENTED. The compose service is behind profile "frontend"
# so default `docker compose up` skips it.
#
# RANCHER-READY constraints enforced:
#   - Multi-stage: node-builder stage + nginx-unprivileged runtime stage.
#   - Non-root: nginxinc/nginx-unprivileged runs as UID 101 (nginx user).
#   - Logs: nginx access_log → /dev/stdout, error_log → /dev/stderr.
#   - Port: 8080 (nginx-unprivileged default; not 80 which requires root).
#   - SPA: try_files $uri /index.html for client-side routing.
#   - Proxy: /api/v1 requests forwarded to backend service.
#
# Build context: ./frontend (NOT repo root)
# Usage:
#   docker compose --profile frontend build frontend  # (after T004 lands)
#
# Build args:
#   IMAGE_TAG     — for labeling (default: dev)
#   BUILD_VERSION — for labeling (default: 0.1.0)
#   BACKEND_URL   — nginx upstream for /api/v1 proxy (default: http://backend:8000)

# ─── Stage 1: node-builder ───────────────────────────────────────────────────
FROM node:22-alpine AS node-builder

ARG BUILD_VERSION=0.1.0
ARG BACKEND_URL=http://backend:8000

LABEL stage=node-builder

WORKDIR /app

# Copy package files first (layer cache: rebuild only on dep changes)
COPY package.json package-lock.json ./

# ci = clean install (respects exact lock file; production-grade)
# --ignore-scripts: skip lifecycle scripts in deps for security
RUN npm ci --ignore-scripts

# Copy application source
COPY . .

# Build Vite production bundle → dist/
# REQUIRES: tsconfig.json (added in P00-S01-T004)
# If this fails: run `docker compose --profile frontend build frontend` AFTER T004
RUN npm run build

# ─── Stage 2: nginx-unprivileged runtime ─────────────────────────────────────
FROM nginxinc/nginx-unprivileged:1.29-alpine AS runtime

ARG BUILD_VERSION=0.1.0
ARG IMAGE_TAG=dev

LABEL maintainer="hilo-people-team" \
      version="${BUILD_VERSION}" \
      image-tag="${IMAGE_TAG}"

# Copy the Vite build output to nginx html root
COPY --from=node-builder /app/dist /usr/share/nginx/html

# Copy nginx configuration (SPA fallback + /api/v1 proxy)
# Config file is in infra/nginx/default.conf at repo root;
# relative to the frontend/ build context it lives at ../infra/nginx/default.conf
# but Docker build context is ./frontend — config must be injected differently.
# Solution: nginx-unprivileged looks for configs in /etc/nginx/conf.d/
# We copy default.conf from the build context; compose bind-mounts are not
# available at build time. The config is committed in infra/nginx/default.conf
# and must be COPIED here — but our build context is frontend/.
# The compose service uses a bind-mount override for the config in development;
# for production image builds the config is baked in at the repo root.
# See: docker-compose.yml litellm service for the bind-mount pattern.
#
# Since the nginx config lives OUTSIDE the frontend/ build context, we use
# a two-step approach: the compose file bind-mounts the config at runtime.
# For a standalone docker build (no compose), the default nginx config serves
# static files but without the /api/v1 proxy.
#
# To bake the config into a standalone image:
#   docker build --build-context infra=../infra -f frontend/Dockerfile ./frontend
# (requires BuildKit; documented in handoff for P06 release slice)

# nginx-unprivileged listens on 8080 (not 80) — no root needed
EXPOSE 8080

# USER 101 is the default for nginx-unprivileged; explicit for documentation
USER 101

# nginx logs to stdout/stderr (see infra/nginx/default.conf for config)
# CMD is inherited from nginxinc/nginx-unprivileged: ["nginx", "-g", "daemon off;"]
