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
  - P00-S01-T004 — Design tokens + editorial component library + showcase (done, 2026-05-11)
  - P00-S02-T001 — Docker compose services (done, 2026-05-11)
  - P00-S02-T002 — Health live ready endpoints (done, 2026-05-11)
  - P00-S02-T003 — Verification data loader and reset (developer done — pending validator+tester, 2026-05-11)
- **Next pending slice**: P01-S01-T001 — Auth/profile/audit migration (after P00-S02-T003 closes)
- **Blockers**: none
- **Generated at**: 2026-05-11T15:35:00+00:00

## Infrastructure Status (P00-S02-T001)

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

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not started (scaffold ready) | uvicorn app.main:app --port 8000 --reload |
| Health check | 3 endpoints implemented | GET /health (backward compat), GET /live (liveness), GET /ready (readiness with DB+Redis ping) |
| Endpoints implemented | 3 | GET /health, GET /live, GET /ready |
| Migrations applied | 0 | Alembic infra ready (alembic.ini + env.py + versions/.gitkeep), head==base (no migrations yet) |
| Seed data | deferred | bootstrap operational; all groups deferred (tables missing until P01-S01-T001) |
| Backend tests | 42 passing | test_health.py (11) + test_dependency_smoke.py (20) + test_verification_data_bootstrap.py (9) + test_dev_restart_reset.py (2) |
| Backend dependencies | declared + installed | argon2-cffi==25.1.0 added (§10.2 Argon2 password hashing) |
| Lint (ruff) | clean | 0 issues |
| Mypy | clean | 0 issues on app/verification_data |

## Verification Data Status (P00-S02-T003)

| Fixture Group | Path | Status |
|---|---|---|
| auth (users/employee_primary) | data/verification/users/employee_primary.json | ready |
| auth (users/admin_peopletech) | data/verification/users/admin_peopletech.json | ready |
| auth (mfa_primary) | data/verification/auth/mfa_primary.json | ready |
| rag_chat collections | data/verification/rag_chat/collections/politicas_tienda.json | ready |
| rag_chat documents | data/verification/rag_chat/documents/politica_vacaciones_es.json | ready |
| rag_docs documents | data/verification/rag_docs/documents/politica_vacaciones_es.json | ready |
| admin_ai providers | data/verification/admin_ai/providers/litellm_verification.json | ready |
| mcp_agents servers | data/verification/mcp_agents/servers/sandbox_readonly.json | ready |
| mcp_agents agents | data/verification/mcp_agents/agents/people_helper.json | ready |
| history conversations | data/verification/history/conversations.json | ready |

Bootstrap loader: `python -m app.verification_data.bootstrap --source data/verification`
- Groups deferred (tables missing) → exit 0, WARN per group
- Idempotent: two runs produce identical output
- --dry-run: validates fixtures without touching DB (exit 0)
- --only <group>: supports auth, rag_chat, history, admin_ai, rag_docs, mcp_agents

## Alembic Status (P00-S02-T003)

| File | Status |
|---|---|
| backend/alembic.ini | created |
| backend/alembic/env.py | created |
| backend/alembic/script.py.mako | created |
| backend/alembic/versions/.gitkeep | created |
| alembic upgrade head | exit 0 (no migrations, head==base) |
| alembic downgrade base + upgrade head cycle | exit 0 (tested) |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | ready to start | `npm --prefix frontend run dev` boots at port 5173 |
| Routes implemented | 1 | /showcase (design-system demo) |
| Design tokens | 8 canonical tokens | tokens.css: --color-bg/ink/paper, --font-display/sans, --hairline, --tracking-label, --radius=0 |
| Base components | 9 | Wordmark, TrackedLabel, EditorialInput, SolidCTA, HairlineTable, StatusDot, MobileFrame, AdminShell, CitationInline |
| Frontend tests | 42 passing | providers (4 T002) + design-system (34 T004) + showcase (4 T004) |
| Build | green | `npm run build` → tsc -b + vite build, 109 modules, 316kB gzip 99kB |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| (none yet) | — | — | Alembic infra ready (P00-S02-T003); tables added by P01-S01-T001+ |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 42 | PASS (health 11 + dep smoke 20 + verif_data_bootstrap 9 + dev_restart_reset 2) |
| Compose orchestration smoke | 11 | PASS (T1–T8 tester + verify cycle 1+2 + minio-init bucket) |
| Frontend unit | 0 | — |
| Frontend component | 42 | PASS (providers 4 + design-system 34 + showcase 4) |
| E2E | 0 | — |
| **Total** | **95** | **95 PASS, 0 FAIL** |

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| M1 — Auth foundation | in progress | P00 scaffold slices in progress | 95/0 |

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

- **2026-05-11 (P00-S01-T001)**: Chose to create `backend/app/__init__.py` as an empty package marker.
- **2026-05-11 (P00-S01-T002)**: react-router v7 ESM. Vitest handles it via jsdom.
- **2026-05-11 (P00-S01-T003)**: Full backend dep pack pinned from PyPI live JSON.
- **2026-05-11 (P00-S02-T001)**: Compose v2-spec purity — no `version:` key.
- **2026-05-11 (P00-S02-T002)**: Sync SQLAlchemy engine with `pool_pre_ping=True` for /ready.
- **2026-05-11 (P00-S02-T003)**: Opción C refinada — loader functional + Alembic infra vacía + fixtures + carga condicional runtime via inspect().has_table(). Tables missing → WARN deferred → exit 0. Once P01-S01-T001 creates tables, next bootstrap run loads data automatically.
- **2026-05-11 (P00-S02-T003)**: argon2-cffi==25.1.0 added to pyproject.toml + requirements.txt (§10.2 Argon2 requirement). Password idempotency via verify-before-rehash pattern (INSERT branch: hash fresh; UPDATE branch: verify existing, re-hash only if changed).
- **2026-05-11 (P00-S02-T003)**: TOTP secret in plain text in data/verification/auth/mfa_primary.json — sandbox decision. WARNING in data/verification/README.md. Human must confirm at /verify-slice (R3 risk).
- **2026-05-11 (P00-S02-T003)**: Pydantic extra="ignore" (not "forbid") to allow _comment fields in JSON fixtures.
- **2026-05-11 (P00-S02-T003)**: dev-restart.profile.sh filled with real stack commands (back/front/db_health/db_reset). Write-set extension justified by scripts/dev-restart.sh:159,219 which call db_reset().

## Known Issues / Risks

- **R1 (P00-S01-T001)**: `backend/tests/` write_set extension — validator approved. Resolved.
- **R2 (P00-S01-T001)**: `backend/app/__init__.py` write_set extension — validator approved. Resolved.
- **R1-infra (P00-S02-T001)**: `docker compose build backend/worker` deferred until T003 finalized. Open.
- **R2-infra (P00-S02-T001)**: `postgres:17-alpine` has no pgvector — decision deferred to P01. Open.
- **R3 (P00-S02-T003)**: TOTP secret in JSON plain text — sandbox decision, documented in data/verification/README.md. **Human must confirm at /verify-slice.**
- **R4 (P00-S02-T003)**: data/verification/ committed to repo — sandbox policy. Human to decide if secrets manager needed for production.
- **R1-T004**: ESLint not installed — `npm run lint` fails. Pre-existing. Lint gate = `tsc -b` which passes.

---

> Last updated: 2026-05-11T15:35:00+00:00
> Updated by: developer — P00-S02-T003 slice complete (Alembic infra + verification data loader + fixtures + dev-restart.profile.sh)
