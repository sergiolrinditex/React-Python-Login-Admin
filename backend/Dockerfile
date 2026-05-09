# backend/Dockerfile — Multi-stage Python 3.13-slim Dockerfile for Hilo People backend
#
# Slice: P00-S02-T001 — Docker compose services (Rancher-ready)
# Phase: P00 — Scaffold + Design System
#
# RANCHER-READY constraints enforced:
#   - Multi-stage: builder stage (with pip + build tools) + runtime stage (slim only).
#   - Non-root: appuser UID=1001 in runtime stage. No process runs as root.
#   - PID 1: Python/uvicorn process directly (exec-form CMD). No shell wrapper.
#   - Logs: stdout/stderr only. PYTHONUNBUFFERED=1 ensures no buffering.
#   - No secrets baked in: only non-sensitive build metadata via ARG.
#   - Healthcheck: HTTP GET /health (maps to k8s livenessProbe + readinessProbe).
#
# Build context: ./backend (NOT repo root)
# Usage:
#   docker build -f backend/Dockerfile ./backend
#   docker compose build backend
#
# Build args:
#   IMAGE_TAG      — tag for labeling (default: dev)
#   BUILD_VERSION  — app version passed as APP_VERSION env var (default: 0.1.0)

# ─── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.13-slim-bookworm AS builder

# Build-time metadata args (non-sensitive)
ARG BUILD_VERSION=0.1.0

LABEL stage=builder

# Install build-time system deps (gcc required by some C extensions: asyncpg, cryptography)
# These stay in the builder stage only; runtime stage gets only the wheels.
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency declaration files first (layer cache: rebuild only on dep changes)
COPY pyproject.toml README.md ./

# Install deps into /root/.local so they can be copied to runtime stage
# --user puts them in /root/.local/lib/pythonX.Y/site-packages
# -e . installs the app package in editable mode (wheel stored in /root/.local)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -e .

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.13-slim-bookworm AS runtime

ARG BUILD_VERSION=0.1.0
ARG IMAGE_TAG=dev

LABEL maintainer="hilo-people-team" \
      version="${BUILD_VERSION}" \
      image-tag="${IMAGE_TAG}" \
      worker-placeholder="false"

# Runtime system deps only (libpq: asyncpg needs the postgres client lib at runtime)
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user (UID 1001, no login shell, no home directory needed for app)
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

# Copy site-packages from builder (only the installed packages, not build tools)
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source (after deps for better layer caching)
WORKDIR /app
COPY --chown=appuser:appgroup . .

# Ensure installed scripts/console_scripts are on PATH for appuser
ENV PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1" \
    APP_VERSION="${BUILD_VERSION}"

# Switch to non-root user before exposing or running
USER appuser

EXPOSE 8000

# Healthcheck (maps to k8s livenessProbe HTTP GET /health)
# Will be upgraded to /ready (DB+Redis probes) in P00-S02-T002
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# PID 1 = uvicorn directly (exec form — no shell wrapper, SIGTERM handled natively)
# --host 0.0.0.0 required inside a container (bind to all interfaces)
# --port controlled by env var via pydantic-settings; default 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
