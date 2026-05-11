# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System (in progress)
- **Last completed slice**: P00-S01-T001 — Repo scaffold + scripts + env
- **Next pending slice**: P00-S01-T002 — Frontend dependency pack
- **Blockers**: none
- **Generated at**: 2026-05-11T04:10:00+00:00

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
| App running | not started | package.json declared; deps not installed (T002) |
| Routes implemented | 0 | No UI yet |
| Components | 0 | No UI yet |
| Frontend tests | 0 passing | Test infra declared in package.json (Vitest) |

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
| Frontend unit | 0 | — |
| Frontend component | 0 | — |
| E2E | 0 | — |
| **Total** | **5** | **5 passing** |

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
- **P00-S01-T001**: `frontend/package.json` declares React ^19.2.0, Vite ^8.0.0, TypeScript ^6.0.0, Vitest ^4.1.0, @vitejs/plugin-react ^6.0.1 (deps not installed — that's T002)
- **P00-S01-T001 reconciliation**: Pinned 2026-05 stable ecosystem (React 19.2, Vite 8.0, Vitest 4.1, TypeScript 6.0, FastAPI 0.136, Pydantic 2.13) after official-docs-researcher reconciliation.
- **P00-S01-T001**: `backend/pyproject.toml` (PEP 621) with FastAPI, uvicorn, pydantic 2, python-dotenv; dev: pytest, httpx, ruff, mypy
- **P00-S01-T001**: `backend/app/main.py` health stub with BEFORE/AFTER logging, X-Request-ID middleware, uptime tracking
- **P00-S01-T001**: `.env.example` uses asymmetric JWT (`JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`) per TECHNICAL_GUIDE §10.2 (RS256)
- **P00-S01-T001**: `scripts/dev-restart.profile.sh` populated with real stack commands (uvicorn + vite)
- **P00-S01-T001**: `scripts/setup-from-scratch.sh` updated with `--check` mode for structure validation

## Known Issues / Risks

- Python 3.11.5 available locally (STACK_PROFILE declares `>=3.12`); `pyproject.toml` requires-python = ">=3.12". Tests run OK on 3.11 in dev machine. T003 should pin a venv or Docker image with 3.12.
- Backend deps installed globally (no venv yet); T003 should set up a proper venv or Docker workflow.
- Frontend deps not installed yet — that's T002's responsibility.

---

> Last updated: 2026-05-11T04:10:00+00:00
> Updated by: developer (P00-S01-T001)
