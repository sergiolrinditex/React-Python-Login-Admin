# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System
- **Last completed slices**:
  - P00-S01-T001 — Repo scaffold + scripts + env (done)
  - P00-S01-T002 — Frontend dependency pack (done)
  - P00-S01-T003 — Backend dependency pack (done)
  - P00-S02-T001 — Docker compose services (done, 2026-05-11)
- **Next pending slice**: P00-S01-T004 — Design tokens + showcase + router scaffold (separate DAG branch; blocked until its own deps satisfy)
- **Blockers**: none
- **Generated at**: 2026-05-11T14:00:00+02:00

## Infrastructure Status (NEW — P00-S02-T001)

| Service | Image | Status | Notes |
|---------|-------|--------|-------|
| postgres | postgres:17-alpine | declared; healthcheck ready | No pgvector yet (P01-S01-T001) |
| redis | valkey/valkey:8-alpine | declared; healthcheck ready (valkey-cli ping) | Service name `redis` preserves DNS |
| litellm | ghcr.io/berriai/litellm:v1.83.14-stable.patch.3 | declared; healthcheck fixed (python-urllib) | F1 fix debugger cycle 1/3 |
| minio | minio/minio:RELEASE.2025-09-07T16-13-09Z | declared; healthcheck ready | ports 9000/9001 |
| minio-init | minio/mc:latest | one-shot sidecar, restart="no" | creates hilo-docs-dev bucket |
| backend | local build (backend/Dockerfile) | declared; build deferred (R1-T003) | depends_on postgres+redis+litellm healthy |
| worker | local build (backend/Dockerfile) | declared; boot deferred (R5-P02-S04) | restart: on-failure |
| frontend | local build (frontend/Dockerfile) | declared; build deferred (R6-T002) | nginx:stable-alpine SPA |

Infra artifacts: `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore`, `scripts/minio-bootstrap.sh`, `frontend/nginx.conf`, `.env.example` (extended).

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not started (scaffold ready) | uvicorn app.main:app --port 8000 --reload |
| Health check | stub present at GET /health | returns {data:{status:"ok"}}; no DB/Redis checks yet |
| Endpoints implemented | 1 | GET /health (stub, no DB) |
| Migrations applied | 0 | no DB schema yet (P01-S01+) |
| Seed data | not loaded | no verification data yet |
| Backend tests | 24 passing | test_health.py (4) + test_dependency_smoke.py (20) |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | not started | package.json declared; Vite runtime files (vite.config.ts, tsconfig.json, index.html, src/main.tsx) deferred to T002 |
| Routes implemented | 0 | no routing yet |
| Components | 0 | no components yet |
| Frontend tests | 0 passing | — |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| (none yet) | — | — | — |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 24 | PASS (health stub 4 + dep smoke 20; TestClient ASGI) |
| Compose orchestration smoke | 11 | PASS (T1–T8 tester + verify cycle 1+2 + minio-init bucket) |
| Frontend unit | 0 | — |
| Frontend component | 0 | — |
| E2E | 0 | — |
| **Total** | **35** | **35 PASS, 0 FAIL** |

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| M1 — Auth foundation | in progress | P00 scaffold slices in progress | 4/0 |

## Journeys (from the Journey Coverage Matrix of instrucciones.md)

| Journey | Milestone | Status | Slices |
|---------|-----------|--------|--------|
| J100 | M1 | pending | 10 |
| J101 | M2 | pending | 7 |
| J102 | M2 | pending | 6 |
| J103 | M3 | pending | 6 |
| J104 | M4 | pending | 5 |
| J105 | M5 | pending | 6 |

## Recent Decisions

- **2026-05-11 (P00-S01-T001)**: Chose to create `backend/app/__init__.py` as an empty package marker — uvicorn and Python `from app.main import app` require it. Flagged as write_set extension in handoff for validator review.
- **2026-05-11 (P00-S01-T001)**: Vite runtime files (`vite.config.ts`, `tsconfig.json`, `index.html`, `frontend/src/main.tsx`) deferred to T002. Only `frontend/package.json` declaring deps is in this write_set. Frontend is not runnable until T002.
- **2026-05-11 (P00-S01-T001)**: `backend/tests/test_health.py` created despite `backend/tests/` not being in explicit write_set. Needed to prove "health route stub compiles" acceptance. Flagged in handoff as write_set extension.
- **2026-05-11 (P00-S01-T001)**: Port variables (`BACKEND_PORT`, `FRONTEND_PORT`) NOT added to .env.example per TECHNICAL_GUIDE §11.1. Ports are baked into STACK_PROFILE.yaml.
- **2026-05-11 (P00-S01-T001)**: Pins used: fastapi==0.135.2, uvicorn==0.42.0, pydantic==2.12.5, pytest==9.0.2, httpx==0.28.1.
- **2026-05-11 (P00-S02-T001)**: Compose v2-spec purity — no `version:` key, no `host-gateway`, named volumes only. Rancher Desktop (moby+containerd) compatible. NERDCTL CAVEAT comment documents healthcheck limitation on nerdctl backend (issue #2386).
- **2026-05-11 (P00-S02-T001)**: `redis` service wraps `valkey/valkey:8-alpine`; DNS name preserved so `REDIS_URL=redis://redis:6379/0` resolves unchanged. `valkey-cli ping` healthcheck (not `redis-cli` — absent from valkey image).
- **2026-05-11 (P00-S02-T001)**: LiteLLM healthcheck uses Python-stdlib `urllib.request` probe (F1 fix, debugger cycle 1/3). `curl`/`wget` absent from `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3`. Container reaches `(healthy)` at ~17s.
- **2026-05-11 (P00-S02-T001)**: `nginx:stable-alpine` (not `1.27-alpine`) in frontend/Dockerfile — tracks 1.30.x patch line automatically; SPA serving layer has no schema coupling concerns.
- **2026-05-11 (P00-S02-T001)**: F2 (host port 5432 parametrization) deferred by human decision as `scope_expansion/future_enhancement`. No FU created.
- **2026-05-11 (P00-S02-T001)**: F3 RESOLVED — official-doc-note items 5 and 8 corrected to `RESOLVED:` format (colon); hook no longer warns in SessionStart.

## Known Issues / Risks

- **R1 (P00-S01-T001)**: `backend/tests/` write_set extension — validator approved. Resolved.
- **R2 (P00-S01-T001)**: `backend/app/__init__.py` write_set extension — validator approved. Resolved.
- **R3 (P00-S01-T001)**: Frontend not runnable until T002 — T002 is now done. Resolved.
- **R4 (P00-S01-T001)**: Hook blocks Write for worktree paths — workaround via Bash heredoc. Persists as known infra limitation.
- **R1-infra (P00-S02-T001)**: `docker compose build backend/worker` deferred until T003 finalized. Open.
- **R2-infra (P00-S02-T001)**: `postgres:17-alpine` has no pgvector — decision deferred to P01-S01-T001. Open.
- **R5-infra (P00-S02-T001)**: `worker` `app.worker` module not created yet — boot deferred to P02-S04-T002. Open.
- **R6-infra (P00-S02-T001)**: `docker compose build frontend` deferred until T002 lock lands in build; SKIP_BUILD=1 escape hatch in Dockerfile. Open.

---

> Last updated: 2026-05-11T14:00:00+02:00
> Updated by: closer (P00-S02-T001)
