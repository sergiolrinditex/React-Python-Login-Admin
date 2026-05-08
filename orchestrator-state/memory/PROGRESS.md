# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System
- **Last completed slice**: P00-S01-T001 — Repo scaffold + scripts + env (developer done, validator/tester pending)
- **Next pending slice**: P00-S01-T002 (frontend deps), P00-S01-T003 (backend deps), P00-S01-T004 (design tokens) — parallel wave after T001 closes
- **Blockers**: none
- **Generated at**: 2026-05-08T21:02:47Z

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not started | uvicorn not yet installed (T003); stub compiles |
| Health check | stub declared | GET /health returns {status, version, uptime} |
| Endpoints implemented | 1 declared | GET /health stub in backend/app/main.py |
| Migrations applied | 0 | First migration: P01-S01-T001 |
| Seed data | not loaded | Seed script: P00-S02-T003 |
| Backend tests | 0 passing | First tests: T003 (dependency smoke) |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | not started | npm deps not yet installed (T002) |
| Routes implemented | 0 | React Router added in T002/P03 |
| Components | 0 | Design system added in T004 |
| Frontend tests | 0 passing | Vitest added in T002 |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| (none yet) | — | — | First migration: P01-S01-T001 |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 0 | — |
| Frontend unit | 0 | — |
| Frontend component | 0 | — |
| E2E | 0 | — |
| **Total** | **0** | — |

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

- **P00-S01-T001**: Bootstrap mínimo: `backend/app/main.py` with FastAPI stub + GET /health; `backend/pyproject.toml` with fastapi==0.115.12 + uvicorn[standard]==0.34.2 pinned; `frontend/package.json` with minimal react/vite/vitest deps pinned; `.env.example` with canonical var names from TECHNICAL_GUIDE + dev-restart.profile.sh (API_PORT/FRONT_PORT). All other deps (SQLAlchemy, React Router, TanStack Query, etc.) deferred to T002/T003. `scripts/setup-from-scratch.sh` extended with `--check` mode to support verify command without running DB migrations/seeds.
- **P00-S01-T001**: `scripts/setup-from-scratch.sh --check` exits 0 with no "no existe" warnings for backend/app or frontend/src.
- **P00-S01-T001 (debugger, 2026-05-08)**: Version-pin audit against PyPI + npm registry triggered by `/verify-slice`. Bumped 13 stale pins to current stable: fastapi 0.136.1, uvicorn[standard] 0.46.0, ruff 0.15.12, mypy 2.0.0, pytest 9.0.3, pytest-asyncio 1.3.0 (backend); react/react-dom 19.2.6, @types/react 19.2.14, @types/react-dom 19.2.3, @vitejs/plugin-react 6.0.1, typescript 6.0.3, vite 8.0.11, vitest 4.1.5 (frontend). Declarative-only — `npm install` lands in T002, `pip install` in T003; major-bump compat (pytest 9.x, pytest-asyncio 1.x, mypy 2.x, vite 8, react 19, ts 6) verified at install time by official-docs-researcher safety net.

## Known Issues / Risks

- `setup-from-scratch.sh --check` still warns `.env no existe` (expected — .env is gitignored and not present in fresh checkout). This is not a failure.
- FastAPI import in `backend/app/main.py` will raise ImportError until T003 installs deps. Accepted: task pack says "compiles" means valid Python AST, which it does.

---

> Last updated: 2026-05-08T21:02:47Z
> Updated by: developer (P00-S01-T001)
