# Hilo People — backend Dockerfile (multi-stage).
#
# Slice:  P00-S02-T001 — Docker compose services
# Phase:  P00 Scaffold + Design System
# Source: TECHNICAL_GUIDE §11.2 Build targets
#
# STAGE 1 (builder): installs Python dependencies into a venv.
# STAGE 2 (runtime): copies the venv and app code; runs as non-root user.
#
# Base: python:3.12-slim-bookworm (debian slim — avoids alpine wheel issues
#       for psycopg/numpy/torch; confirmed best practice for scientific Python).
#
# DEPENDENCY NOTE (R1):
#   The builder stage runs `pip install -r requirements.txt`.
#   `backend/requirements.txt` contains the MINIMAL bootstrap deps from T001
#   (fastapi, uvicorn, pydantic). The full dep pack (SQLAlchemy, Alembic,
#   Celery, LiteLLM, etc.) lands in P00-S01-T003. If this Dockerfile is built
#   before T003 merges, the image will be functional but missing those deps.
#   The full production build is validated in P06-S01-T001.
#
# BUILD CONTEXT: repo root (docker-compose.yml uses `context: .`).
#   The .dockerignore at repo root excludes .git, node_modules, .venv,
#   orchestrator-state, __pycache__, and other build-context noise.

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create isolated venv so runtime stage gets a clean copy
RUN python -m venv /build/venv
ENV PATH="/build/venv/bin:$PATH"

# Copy dependency manifests first (layer-cache friendly)
COPY backend/requirements.txt ./requirements.txt

# Install all runtime deps into the venv
RUN pip install --upgrade pip --no-cache-dir \
    && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# Runtime system libs only (libpq for asyncpg/psycopg native bindings)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security compliance (01-non-negotiables.md §Security)
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/sh --create-home appuser

WORKDIR /app

# Copy venv from builder
COPY --from=builder /build/venv /app/venv
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application source
COPY backend/app ./app

# Fix ownership
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Default command: uvicorn without --reload (dev uses host dev-server instead).
# The celery worker overrides this command in docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
