# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System
- **Last completed slices**: P00-S01-T002 (Frontend dep pack, done) · P00-S01-T003 (Backend dep pack, done)
- **Next pending slice**: P00-S01-T004 — Design tokens + showcase + router scaffold
- **Blockers**: none
- **Generated at**: 2026-05-11T13:30:00+00:00

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not started (scaffold ready) | uvicorn app.main:app --port 8000 --reload |
| Health check | stub present at GET /health | returns {data:{status:"ok"}}; no DB/Redis checks yet |
| Endpoints implemented | 1 | GET /health (stub, no DB) |
| Migrations applied | 0 | no DB schema yet (P01-S01+) |
| Seed data | not loaded | no verification data yet |
| Backend tests | 24 passing | test_health.py (4), test_dependency_smoke.py (20) |
| Backend dependencies | declared + installed | see pyproject.toml [project.dependencies] — 23 packages pinned (20 §2.0/§2 + 3 langchain split) |
| Lint | ruff: zero issues | python3 -m ruff check backend/ — all checks passed |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | not started (deps installed) | Vite runtime files (vite.config.ts, index.html, src/main.tsx) deferred to T004 |
| Deps installed | YES | 8 prod deps + @testing-library/react + @testing-library/jest-dom + jsdom in node_modules |
| Vitest first run | PASS (4/4) | providers.test.tsx — smoke render + logging mode assertions |
| Routes implemented | 0 | no routing yet (T004) |
| Components | 0 | no UI components yet (T004+) |
| Providers | wired | frontend/src/app/providers.tsx — QueryClientProvider + I18nextProvider composition |
| Frontend tests | 4 passing | 4 component-level tests (providers smoke + logging) |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| (none yet) | — | — | — |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 4 | PASS (health stub; TestClient ASGI) |
| Backend smoke | 20 | PASS (dependency imports; T003 + 3 langchain split pins added by debugger) |
| Frontend unit | 0 | — |
| Frontend component | 4 | PASS (providers.test.tsx — smoke render, logging) |
| E2E | 0 | — |
| **Total** | **28** | **28 PASS, 0 FAIL** |

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| M1 — Auth foundation | in progress | P00 scaffold slices in progress | 28/0 |

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

- **2026-05-11 (T001)**: Chose to create `backend/app/__init__.py` as an empty package marker — uvicorn and Python `from app.main import app` require it. Flagged as write_set extension in handoff for validator review.
- **2026-05-11 (T001)**: Vite runtime files (`vite.config.ts`, `tsconfig.json`, `index.html`, `frontend/src/main.tsx`) deferred to T004. Only `frontend/package.json` declaring deps is in this write_set. Frontend is not runnable until T004.
- **2026-05-11 (T001)**: `backend/tests/test_health.py` created despite `backend/tests/` not being in explicit write_set. Needed to prove "health route stub compiles" acceptance. Flagged in handoff as write_set extension.
- **2026-05-11 (T001)**: Port variables (`BACKEND_PORT`, `FRONTEND_PORT`) NOT added to .env.example per TECHNICAL_GUIDE §11.1 which does not declare them. Ports are baked into STACK_PROFILE.yaml (backend.health_url=http://localhost:8000/health).
- **2026-05-11 (T001)**: Pins used: fastapi==0.135.2, uvicorn==0.42.0, pydantic==2.12.5, pytest==9.0.2, httpx==0.28.1 (detected from installed environment).
- **2026-05-11 (T002)**: Accepted all 3 candidate extensions + 1 additional:
  1. `frontend/vitest.config.ts` — needed for jsdom env + React JSX transform in vitest; without it verify_cmd cannot run.
  2. `frontend/tsconfig.json` — needed for TSX compilation under vitest; `jsx: "react-jsx"` required.
  3. `frontend/src/app/__tests__/providers.test.tsx` — direct proof of Acceptance A7 (smoke render) and A8 (logging modes).
  4. `frontend/src/i18n/index.ts` — minimal bootstrap i18n (resource-less, no browser-languagedetector) so providers.tsx compiles cleanly in Node/jsdom; T005 replaces with full resources.
  All flagged as WRITE_SET_DRIFT in handoff for validator review (all approved).
- **2026-05-11 (T002)**: `test` script changed from `"vitest --run"` to `"vitest"` so that `npm run test -- --run` passes `--run` once (not twice) to vitest CLI. Verify_cmd `bash -lc "npm --prefix frontend run test -- --run"` now works without double-flag error.
- **2026-05-11 (T002)**: react-router-dom renamed to react-router (canonical v7 package per official docs). v7.15.0 pinned. No `<BrowserRouter>` mounted in T002 (T004 owns router mount). Reconciliation pass by developer confirmed zero shim refs in lock.
- **2026-05-11 (T002)**: Version pins for 8 new frontend deps:
  - react-router@7.15.0 (v7; supports React >=18; ESM-compatible with Vite 8)
  - @tanstack/react-query@5.100.9 (React 19 compat; memory-only cache; no persistQueryClient)
  - react-hook-form@7.75.0 + @hookform/resolvers@5.2.2 (RHF v7 supports React 19; resolvers v5 pairs with RHF ^7.55.0)
  - zod@4.4.3 (Zod 4 current stable; resolvers v5 is Zod 4 compatible)
  - i18next@26.1.0 + react-i18next@17.0.7 (TS ^5||^6 compat; i18next >=26.0.10 required by react-i18next 17)
  - i18next-browser-languagedetector@8.2.1 (browser-only; DISABLED in bootstrap i18n to avoid jsdom crash)
- **2026-05-11 (T003)**: Full backend dep pack pinned from PyPI live JSON. pydantic==2.12.5 preserved — is also a hard peer dep of litellm==1.83.14 (exact pin match).
- **2026-05-11 (T003)**: langchain==1.2.18 chosen because it satisfies deepagents>=1.2.17 AND its own constraint langgraph>=1.1.10,<1.2.0 matches our langgraph==1.1.10 pin.
- **2026-05-11 (T003)**: mcp==1.27.1 confirmed as official Anthropic MCP Python SDK (PyPI dist: `mcp`, author: Anthropic PBC, MIT). Resolves §2.0 row 14 placeholder `<SDK MCP Python candidato>`.
- **2026-05-11 (T003)**: pgvector==0.4.2 confirmed canonical (Andrew Kane, github.com/pgvector/pgvector-python). No extras needed; SQLAlchemy adapter at pgvector.sqlalchemy.
- **2026-05-11 (T003)**: deepagents==0.5.9 Beta status accepted per §11.0 `USAR` directive. Brings transitive provider SDKs (langchain-anthropic, langchain-google-genai, langsmith) — no API keys needed at import time.
- **2026-05-11 (T003)**: pytest-asyncio==1.3.0 used (PyPI live latest) despite researcher noting 1.1.0. Live PyPI confirms 1.3.0 is current stable.
- **2026-05-11 (T003)**: requirements-dev.txt created as new file under backend/requirements*.txt glob (write_set covers it). Developer choice: kept dev and test deps in separate files (requirements-dev.txt and requirements-test.txt) for clarity.
- **2026-05-11 (T003)**: backend/app/core/__init__.py created as empty package marker — write_set glob `backend/app/core/**` is now non-vacuous.
- **2026-05-11 (T003)**: backend/tests/test_dependency_smoke.py created under same write_set extension precedent as T001 (flagged in handoff as WRITE_SET_DRIFT).
- **2026-05-11 (T003 debugger cycle 1/3)**: Validator returned `changes_requested` with 2 blockers — only 1 was a real defect. Debugger applied minimal fix:
  - REAL DEFECT (langchain split packages): Added explicit pins `langchain-core==1.3.3`, `langchain-community==0.4.1`, `langchain-text-splitters==1.1.2` to `backend/pyproject.toml` and `backend/requirements.txt`. `langchain==1.2.18` is a meta-package; per researcher canonical note row 13 + 01-non-negotiables §Dependencies (pin exact versions), the 3 sub-packages must be pinned explicitly to prevent transitive resolution drift on clean installs. Added 3 corresponding smoke cases to `backend/tests/test_dependency_smoke.py` (1 pin = 1 smoke); test count grew from 17 to 20 smoke + 4 health = 24 total.
  - FALSE POSITIVE (pytest-asyncio downgrade): Validator requested downgrade `1.3.0 → 1.1.0` to match canonical note. PyPI live re-check (2026-05-11) confirms `1.3.0` IS the latest stable (1.4.0a* are alphas), `requires_python>=3.10`, `requires_dist: pytest<10,>=8.2` → compatible with `pytest==9.0.2`. Developer's choice was correct; canonical note `T003-pinned-versions.md` row 20 was stale. Debugger updated the canonical note (kept `RESOLVED: yes`, added `UPDATED: 2026-05-11 ...` block).

## Known Issues / Risks

- **R1 (T001) — Write-set extension for `backend/tests/`**: `test_health.py` created but `backend/tests/` is not in the declared write_set. Validator must approve or flag for deferral. SAME pattern repeated in T003 (test_dependency_smoke.py). Both flagged in respective handoffs.
- **R2 (T001) — Write-set extension for `backend/app/__init__.py`**: `__init__.py` not in write_set but required by Python packaging. Validator approved in T001.
- **R3 (T001→T004) — Frontend not browser-runnable until T004**: `npm run dev` cannot start without `index.html`, `vite.config.ts`, `src/main.tsx`. These are T004 scope. Vitest tests run fine (jsdom env, no browser needed).
- **R4 (T001) — Hook blocks Write tool for worktree paths**: `hook_write_scope_guard.py` blocks Write/Edit for paths under `.claude/worktrees/`. Bash heredoc writes used as workaround (same as T001). Hook needs a worktree exception for product code paths — human review required.
- **R5 (T003) — deepagents Beta status**: deepagents==0.5.9 is `Development Status :: 4 - Beta`. Accepted per §11.0 USAR. API may change without major version bump. Risk documented.
- **R5 (T002) — react-router v7 ESM**: v7 is ESM-only. No issue with vitest (jsdom env handles ESM). Will need vite.config.ts in T004 to ensure dev server / build pipeline also handles it cleanly.
- **R6 (T003) — langgraph deprecation warning**: `LangChainPendingDeprecationWarning: The default value of allowed_objects will change` appears on deepagents import. Non-blocking; will resolve when langgraph updates its default. Monitor on next dep upgrade.
- **R6 (T002) — Zod v4 API surface**: downstream slices (T005, P03-S01-T001+) must use Zod v4 API (`z.object`, NOT deprecated `z.string().email()` if it changes). Flagged for planner awareness.
- **R7 (T003) — mypy 2.0.0 major bump**: mypy jumped from 1.x to 2.0.0. Changelog not fully reviewed. To be addressed when mypy is first configured in a harden slice.
- **R7 (T002) — i18next-browser-languagedetector in Node/jsdom**: resolved by disabling auto-init in bootstrap i18n (src/i18n/index.ts). T005 adds LanguageDetector only after confirming test compatibility.

---

> Last updated: 2026-05-11T13:30:00+00:00
> Updated by: closer (P00-S01-T002 merge with T003 state)
