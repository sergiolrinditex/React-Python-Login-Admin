# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System (in progress)
- **Last completed slice**: P00-S01-T002 — Frontend dependency pack
- **Next pending slice**: P00-S01-T003 — Backend venv + Docker scaffold
- **Blockers**: none
- **Generated at**: 2026-05-11T09:34:00+00:00

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not running (stub only) | uvicorn not started; use `scripts/dev-restart.sh --soft` |
| Health check | declared | `GET /health` → `{status, version, uptime}` at localhost:8000 |
| Endpoints implemented | 1 | GET /health (stub) |
| Migrations applied | 0 | DB not touched (Step 0.2) |
| Seed data | not loaded | Awaiting P00-S02-T001 Docker setup |
| Backend tests | 5 passing | `backend/tests/test_health.py` — all green |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | not started | deps installed; use `npm --prefix frontend run dev` |
| Routes implemented | 0 | No UI yet |
| Components | 1 | `frontend/src/app/providers.tsx` — Providers shell |
| Frontend tests | 3 passing | `frontend/src/app/providers.test.tsx` — all green |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| (none yet) | — | — | Awaiting P00-S02-T001 |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend smoke | 5 | All passing (P00-S01-T001) |
| Backend unit | 0 | — |
| Backend integration | 0 | — |
| Frontend unit (component) | 3 | All passing (P00-S01-T002) |
| Frontend component | 0 | — |
| E2E | 0 | — |
| **Total** | **8** | **8 passing** |

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| M1 Auth propio | pending | P01+ | — |

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

- **P00-S01-T001**: root `package.json` with workspace meta for `frontend/`
- **P00-S01-T001**: `frontend/package.json` declares React ^19.2.0, Vite ^8.0.0, TypeScript ^6.0.0, Vitest ^4.1.0, @vitejs/plugin-react ^6.0.1
- **P00-S01-T002 version reconciliation**: npm registry reality 2026-05-11 forced version bumps:
  - `react-i18next@^17.0.7` (was ^15.5.2 in task pack; v15 peer-optional TypeScript ^5 conflicts with TS 6)
  - `i18next@^26.0.10` (was ^25.2.1; react-i18next v17 requires i18next >= 26)
  - `@tanstack/react-query@^5.100.9` (was ^5.76.1; same major, patch update)
  - `react-hook-form@^7.75.0` (was ^7.56.3)
  - `@hookform/resolvers@^5.2.2` (was ^4.1.3; major bump, zod peer not required)
  - `react-router-dom@^7.15.0` (was ^7.6.0; same major, patch update)
  - `zod@^4.4.3` (was ^3.24.4 in task pack; 4.x is current stable)
  - `@testing-library/jest-dom@^6.9.1` (correct current stable)
- **P00-S01-T002 write_set drift**: lockfile is at worktree root (not `frontend/package-lock.json`) due to npm workspace hoisting. This is correct npm behavior and expected by any npm workspace setup.
- **P00-S01-T002 scaffold completion**: `vite.config.ts`, `vitest.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `index.html` created as T001 scaffold completion (T001 only committed `frontend/package.json`; these files are declared in TECHNICAL_GUIDE §4 structure but were not written in T001).
- **P00-S01-T002**: `frontend/src/app/providers.tsx` — Providers shell with BrowserRouter + QueryClientProvider + I18nextProvider, BEFORE/AFTER logging gated by VITE_ENABLE_VERBOSE_LOGGING.
- **P00-S01-T002**: i18n init inline (empty resources); T005 replaces with real ES/EN/FR namespaces from `i18n/index.ts`.
- **P00-S01-T001**: `backend/pyproject.toml` (PEP 621) with FastAPI, uvicorn, pydantic 2, python-dotenv; dev: pytest, httpx, ruff, mypy
- **P00-S01-T001**: `backend/app/main.py` health stub with BEFORE/AFTER logging, X-Request-ID middleware, uptime tracking
- **P00-S01-T001**: `.env.example` uses asymmetric JWT (`JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`) per TECHNICAL_GUIDE §10.2 (RS256)

## Known Issues / Risks

- Python 3.11.5 available locally (STACK_PROFILE declares `>=3.12`); `pyproject.toml` requires-python = ">=3.12". Tests run OK on 3.11 in dev machine. T003 should pin a venv or Docker image with 3.12.
- Backend deps installed globally (no venv yet); T003 should set up a proper venv or Docker workflow.
- ESLint not installed (no `eslint` package in devDependencies yet); `npm run lint` fails with "command not found". ESLint setup is a later slice.
- `vite.config.ts`, `vitest.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `index.html` were created in T002 as T001 scaffold completion. These belong logically to T001 but weren't committed there. They should be included in the T002 commit or handled as WRITE_SET_DRIFT follow-up.

---

> Last updated: 2026-05-11T09:34:00+00:00
> Updated by: developer (P00-S01-T002)
