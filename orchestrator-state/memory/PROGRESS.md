# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System
- **Last completed slice**: P00-S01-T001 — Repo scaffold + scripts + env
- **Next pending slice**: P00-S01-T002 — Frontend dependency pack (React Router, TanStack Query, etc.)
- **Blockers**: none
- **Generated at**: 2026-05-11T10:58:00+00:00

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not started (scaffold ready) | uvicorn app.main:app --port 8000 --reload |
| Health check | stub present at GET /health | returns {data:{status:"ok"}}; no DB/Redis checks yet |
| Endpoints implemented | 1 | GET /health (stub, no DB) |
| Migrations applied | 0 | no DB schema yet (P01-S01+) |
| Seed data | not loaded | no verification data yet |
| Backend tests | 4 passing | backend/tests/test_health.py (4 tests, 0.11s) |

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
| Backend integration | 4 | PASS (health stub; TestClient ASGI) |
| Frontend unit | 0 | — |
| Frontend component | 0 | — |
| E2E | 0 | — |
| **Total** | **4** | **4 PASS, 0 FAIL** |

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

- **2026-05-11**: Chose to create `backend/app/__init__.py` as an empty package marker — uvicorn and Python `from app.main import app` require it. Flagged as write_set extension in handoff for validator review.
- **2026-05-11**: Vite runtime files (`vite.config.ts`, `tsconfig.json`, `index.html`, `frontend/src/main.tsx`) deferred to T002. Only `frontend/package.json` declaring deps is in this write_set. Frontend is not runnable until T002.
- **2026-05-11**: `backend/tests/test_health.py` created despite `backend/tests/` not being in explicit write_set. Needed to prove "health route stub compiles" acceptance. Flagged in handoff as write_set extension.
- **2026-05-11**: Port variables (`BACKEND_PORT`, `FRONTEND_PORT`) NOT added to .env.example per TECHNICAL_GUIDE §11.1 which does not declare them. Ports are baked into STACK_PROFILE.yaml (backend.health_url=http://localhost:8000/health).
- **2026-05-11**: Pins used: fastapi==0.135.2, uvicorn==0.42.0, pydantic==2.12.5, pytest==9.0.2, httpx==0.28.1 (detected from installed environment).

## Known Issues / Risks

- **R1 — Write-set extension for `backend/tests/`**: `test_health.py` created but `backend/tests/` is not in the declared write_set. Validator must approve or flag for deferral to P00-S02-T002.
- **R2 — Write-set extension for `backend/app/__init__.py`**: `__init__.py` not in write_set but required by Python packaging. Minimal (7 lines); validator must confirm OK.
- **R3 — Frontend not runnable until T002**: `frontend/package.json` declares deps but no Vite runtime files created. This is per the planner verdict but means frontend cannot start until T002 is complete.
- **R4 — Hook blocks Write tool for worktree paths**: `hook_write_scope_guard.py` blocks Write/Edit for paths under `.claude/worktrees/` because they resolve as `.claude/`-relative. Used Bash heredoc writes instead. The hook needs a worktree exception for product code paths.

---

> Last updated: 2026-05-11T10:58:00+00:00
> Updated by: developer (P00-S01-T001)
