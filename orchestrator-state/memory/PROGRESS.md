# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System
- **Last completed slices**: P00-S01-T002 (done), P00-S01-T003 (done), P00-S01-T004 (design tokens, done), **P00-S02-T001 (Docker compose services — developer done, validator/tester pending)**
- **Next pending slices**: P00-S01-T005 (i18n bundles), P00-S02-T002 (health endpoints /live /ready — depends on P00-S02-T001)
- **Blockers**: none
- **Follow-ups pending**: FU-20260508225027 (medium, wiring — env var name drift in config.py vs TECHNICAL_GUIDE §11.1, non-blocking)
- **Generated at**: 2026-05-09T01:00:00Z

## Docker Compose Stack (P00-S02-T001)

All 6 non-gated services verified healthy on 2026-05-09. Frontend service gated behind `profiles: [frontend]` (needs T004 tsconfig.json — T004 is done but compose build not yet verified post-T004).

| Service | Image | Host Port | Status | Notes |
|---------|-------|-----------|--------|-------|
| postgres | pgvector/pgvector:pg18-bookworm | 5433 | HEALTHY | pgvector 0.8.2, PostgreSQL 18.3; host port 5433 avoids local PG conflict |
| redis | redis:8-alpine | 6379 | HEALTHY | Redis 8.6.3; Python client redis==6.4.0 compatible |
| minio | minio/minio:RELEASE.2025-09-07T16-13-09Z | 9000 (S3), 127.0.0.1:9001 (console) | HEALTHY | Console bound to 127.0.0.1 only |
| litellm | ghcr.io/berriai/litellm:v1.83.14-stable | 4000 | HEALTHY | start_period 120s (slow init ~2min); no curl/wget — uses python3 urllib for healthcheck |
| backend | hilo-people-backend:dev | 8000 | HEALTHY | appuser UID 1001 (non-root); PID 1 = uvicorn; python:3.13-slim-bookworm |
| worker | hilo-people-backend:dev (same image) | — | RUNNING | Placeholder cmd (no Celery yet); healthcheck disabled until P02-S04-T002 |
| frontend | hilo-people-frontend:dev | 8080 | GATED | profiles: [frontend]; build gated on T004 tsconfig.json |

### Infra files created in P00-S02-T001
- `/docker-compose.yml` — 7 services, single hilo-network bridge, 3 named volumes
- `/backend/Dockerfile` — multi-stage python:3.13-slim-bookworm, non-root appuser UID 1001
- `/frontend/Dockerfile` — multi-stage node:22-alpine → nginx-unprivileged:1.29-alpine, USER 101
- `/.dockerignore`, `/backend/.dockerignore`, `/frontend/.dockerignore`
- `/infra/litellm/config.yaml` — minimal placeholder
- `/infra/nginx/default.conf` — SPA fallback + /api/v1 reverse proxy
- `/.env.example` — appended compose-specific vars (POSTGRES_*, MINIO_*, AWS_ENDPOINT_URL, IMAGE_TAG, BUILD_VERSION)

### Rancher-ready constraints (all verified)
- Multi-stage Dockerfiles: YES
- USER non-root (appuser UID 1001, nginx UID 101): YES
- Logs to stdout/stderr only (PYTHONUNBUFFERED=1, nginx /dev/stdout): YES
- HTTP healthchecks (backend /health, minio /minio/health/live, litellm /health/liveliness): YES
- Named volumes for stateful services: YES
- No host.docker.internal, no network_mode: host, no privileged: YES
- restart: unless-stopped, stop_grace_period: 30s: YES
- Build args IMAGE_TAG + BUILD_VERSION: YES

### ADR seed
Rancher-ready compose stack ADR preserved in handoff P00-S02-T001.md (pending fold-in to TECHNICAL_GUIDE ADR section in a maintenance slice)

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | available | uvicorn starts, GET /health returns {status, version, uptime} |
| Health check | verified | curl http://127.0.0.1:8001/health → 200 |
| Endpoints implemented | 1 live | GET /health (structlog wired in T003) |
| Migrations applied | 0 | First migration: P01-S01-T001 |
| Seed data | not loaded | Seed script: P00-S02-T003 |
| Backend tests | 39 passing | 39 smoke tests (all dep categories) |
| Deps installed | YES | pip install -e ".[dev]" clean in .venv-t003 |

### Backend Dependencies (exact pins, verified against PyPI 2026-05-08)

**Runtime:**

| Package | Version | Notes |
|---------|---------|-------|
| `fastapi` | 0.136.1 | |
| `uvicorn[standard]` | 0.46.0 | |
| `python-multipart` | 0.0.27 | FastAPI form parsing |
| `itsdangerous` | 2.2.0 | signed cookies |
| `sqlalchemy[asyncio]` | 2.0.49 | |
| `alembic` | 1.18.4 | |
| `asyncpg` | 0.31.0 | covers both ORM + Alembic async |
| `pydantic` | 2.12.5 | constrained by litellm==1.83.14 (requires exactly 2.12.5) |
| `pydantic-settings` | 2.14.1 | |
| `argon2-cffi` | 25.1.0 | |
| `pyjwt[crypto]` | 2.12.1 | chosen over python-jose |
| `cryptography` | 48.0.0 | Fernet credential cipher |
| `httpx` | 0.28.1 | promoted to runtime (was dev-only in T001) |
| `pypdf` | 6.10.2 | |
| `python-docx` | 1.2.0 | |
| `celery[redis]` | 5.6.3 | |
| `redis` | 6.4.0 | constrained by celery 5.6.3→kombu <6.5 |
| `resend` | 2.30.0 | |
| `structlog` | 25.5.0 | |
| `prometheus-client` | 0.25.0 | |
| `boto3` | 1.43.6 | |
| `pgvector` | 0.4.2 | Python binding (PG extension via P01) |
| `litellm` | 1.83.14 | HIGH VOLATILITY |
| `langchain` | 1.2.18 | |
| `langchain-core` | 1.3.3 | |
| `langchain-community` | 0.4.1 | |
| `langchain-text-splitters` | 1.1.2 | |
| `langgraph` | 1.1.10 | |
| `deepagents` | 0.5.7 | |
| `mcp` | 1.27.1 | official modelcontextprotocol/python-sdk |
| `tiktoken` | 0.12.0 | |

**Dev:**

| Package | Version |
|---------|---------|
| `ruff` | 0.15.12 |
| `mypy` | 2.0.0 |
| `pytest` | 9.0.3 |
| `pytest-asyncio` | 1.3.0 |
| `pytest-cov` | 7.1.0 |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | vite up at :5174 | Port 5174 per local .env FRONT_PORT override (default 5173 collides with sibling project) |
| Build | PASSING | `npm run build` exits 0; dist/ created (fixed in T004 via tsconfig.json + tsconfig.node.json) |
| npm deps installed | DONE | 10 runtime + 10 dev deps (exact pins, no ^ ~) |
| Routes implemented | 1 (/showcase) | /showcase route wired in src/main.tsx; productive routes in P01-S03-T001 |
| Providers | AppProviders wired | QueryClientProvider + I18nextProvider in frontend/src/app/providers.tsx |
| Components | 8 shipped | Wordmark, TrackedLabel, StatusDot, EditorialInput, SolidCTA, HairlineTable, MobileFrame, AdminShell |
| Design tokens | Implemented | CSS custom properties in shared/styles/tokens.css + TS mirror in shared/styles/index.ts |
| Frontend tests | 47 passing | 1 providers smoke + 7 tokens/component unit tests + 8 showcase smoke |

### Frontend Dependencies (exact pins, as of 2026-05-08 npm registry)

**Runtime:**

| Package | Version |
|---|---|
| `react` | 19.2.6 |
| `react-dom` | 19.2.6 |
| `react-router-dom` | 7.15.0 |
| `@tanstack/react-query` | 5.100.9 |
| `react-hook-form` | 7.75.0 |
| `zod` | 4.4.3 |
| `@hookform/resolvers` | 5.2.2 |
| `i18next` | 26.0.10 |
| `react-i18next` | 17.0.7 |
| `i18next-browser-languagedetector` | 8.2.1 |

**Dev:**

| Package | Version |
|---|---|
| `@types/react` | 19.2.14 |
| `@types/react-dom` | 19.2.3 |
| `@vitejs/plugin-react` | 6.0.1 |
| `typescript` | 6.0.3 |
| `vite` | 8.0.11 |
| `vitest` | 4.1.5 |
| `@testing-library/react` | 16.3.2 |
| `@testing-library/dom` | 10.4.1 |
| `@testing-library/jest-dom` | 6.9.1 |
| `jsdom` | 29.1.1 |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| (none yet) | — | — | First migration: P01-S01-T001 |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 0 | — |
| Backend smoke | 39 | PASS (dependency smoke — all dep categories) |
| Frontend unit | 7 | PASS (tokens TS mirror + component tests) |
| Frontend component | 9 | PASS (providers smoke + showcase smoke: 1+8) |
| E2E | 0 | — |
| **Total** | **55** | **55 PASS** |

Note: Vitest counts 47 tests (4 test files). Backend smoke 39 tests separate. Grand total: 86 tests passing.

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| M1 — Auth foundation | pending | P01-P02 | — |

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

- **P00-S02-T001 (2026-05-09)**: Docker compose stack (Rancher-ready). 7 services declared. Key decisions: (1) pgvector/pgvector:pg18-bookworm (researcher confirmed pg18 available; `pg18-bookworm` explicit Debian stable); (2) redis:8-alpine (researcher confirmed Redis 8.6.3 is current stable, not 7.4); (3) litellm:v1.83.14-stable (pin to exact version matching Python lib, not floating main-stable); (4) nginx-unprivileged:1.29-alpine (researcher found 1.27 does NOT exist, 1.29 is current); (5) python:3.13-slim-bookworm (explicit Bookworm); (6) postgres host port 5433 (avoids conflict with local PG on 5432); (7) litellm healthcheck uses python3 urllib (no curl/wget in LiteLLM image); (8) LiteLLM start_period 120s (image needs ~2min to initialize); (9) worker healthcheck disabled (inherits /health from Dockerfile which fails since worker has no HTTP port — real Celery healthcheck in P02-S04-T002); (10) postgres volume mount at /var/lib/postgresql not /data (PG18 changed data dir layout per github.com/docker-library/postgres/pull/1259).
- **P00-S01-T001**: Bootstrap mínimo. Pinned versions from debugger 2026-05-08.
- **P00-S01-T002 (2026-05-08)**: Frontend runtime deps installed. AppProviders wired (QueryClientProvider + I18nextProvider). 1 smoke test.
- **P00-S01-T003 (2026-05-08)**: Full backend dep stack installed. Key constraints: (1) pydantic==2.12.5 forced by litellm==1.83.14; (2) redis==6.4.0 forced by celery→kombu<6.5. core/ package created: config.py (pydantic-settings), logging.py (structlog with redaction), db.py (async engine + session factory). main.py updated with structlog wiring (option b: one-line import + call). 39/39 smoke tests GREEN. ruff+mypy clean. uvicorn /health=200.
- **P00-S01-T004 (2026-05-09)**: Path A — bootstrap completion files included in T004 scope (justified by PROGRESS.md Known Issues + T002 handoff deferrals). Vite config co-located, Vitest separate (vitest.config.ts). Tokens implemented as CSS custom properties in tokens.css; TS mirror in shared/styles/index.ts exports names as strings (not values). Component naming: `MobileFrame` (TECHNICAL_GUIDE wins over instrucciones `MobileShell`). `@testing-library/jest-dom/vitest` import per researcher note. All 8 design-system components shipped. 47 tests GREEN. Build passing.
- **P00-S01-T004 — tsconfig.node.json**: Added `"composite": true` (required for `tsc -b` project references). `noEmit: true` removed from node config.
- **P00-S01-T004 — CSS import in TS**: Added `src/vite-env.d.ts` with `/// <reference types="vite/client" />` to allow CSS side-effect imports without TS2882 errors.
- **P00-S01-T004 — toHaveStyle + CSS vars**: jsdom resolves CSS variables to empty/default computed values. Tests use `getAttribute('style').toContain('var(...)')` instead of `toHaveStyle({ prop: 'var(...)' })`.
- **P00-S01-T003 — pyjwt choice**: chose `pyjwt[crypto]` over `python-jose` — modern FastAPI standard in 2026.
- **P00-S01-T003 — asyncpg-only**: no psycopg2-binary; asyncpg covers both SQLAlchemy async + Alembic async migrations.
- **P00-S01-T003 — hatchling config**: added `[tool.hatch.build.targets.wheel] packages = ["app"]` + backend/README.md to fix editable install.
- **P00-S01-T002 — react-router-dom v7**: In v7, `react-router-dom` is a thin re-export of `react-router`. P01-S03-T001 planner must choose API intentionally.
- **P00-S01-T002 — zod v4**: Pinned zod@4.4.3. Breaking changes from v3 documented.

## Known Issues / Risks

- `setup-from-scratch.sh --check` still warns `.env no existe` (expected — .env is gitignored).
- `npm run lint` not configured — ESLint not in T004 scope; follow-up ticket pending.
- pip-audit: 5 findings in `setuptools==65.5.0` (system Python, not declared dep). No CVEs in declared backend deps.
- `redis==6.4.0` is below latest 7.4.0 — constrained by celery/kombu. Will need upgrade when celery releases a kombu that supports redis>=7.
- **dev FRONT_PORT=5174**: User's `.env` previously set FRONT_PORT=5174 to avoid sibling-project collision on 5173. Vite dev is currently running on 5174. If .env no longer contains this override, next `dev-restart.sh` will try 5173 (the vite default) — may conflict with sibling project. Orchestrator-level decision pending.
- dev-restart.sh `--check` exits 1 when DB is UNKNOWN (no /ready endpoint yet). Cosmetic; not blocking but noisy.
- **P00-S02-T001**: LiteLLM v1.83.14-stable has ~2min startup time; compose healthcheck uses start_period: 120s. In CI this may slow pipelines — tracked for P05 hardening.
- **P00-S02-T001**: Worker service inherits /health Dockerfile HEALTHCHECK from backend image; disabled in compose override since worker has no HTTP port. Real Celery healthcheck (`celery inspect ping`) lands in P02-S04-T002.
- **P00-S02-T001**: postgres host port mapped to 5433 (not 5432) to avoid conflict with local Postgres instance on dev machines. alembic must use port 5433 when running from host.
- **P00-S02-T001 env drift follow-up**: FU-20260508225027 (medium) registered — config.py field names don't match TECHNICAL_GUIDE §11.1 (jwt_secret vs JWT_PRIVATE_KEY/JWT_PUBLIC_KEY etc.). Non-blocking now; must be resolved before P01-S02-T001 (auth JWT implementation).

---

> Last updated: 2026-05-09T00:47:00Z
> Updated by: developer (P00-S01-T004)
