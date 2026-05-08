# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 0 — Scaffold + Design System
- **Last completed slices**: P00-S01-T002 (frontend deps, done), P00-S01-T003 (backend deps, developer done — validator/tester pending)
- **Next pending slice**: P00-S01-T004 (design tokens)
- **Blockers**: none
- **Generated at**: 2026-05-08T22:00:00Z

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
| App running | not started | No tsconfig.json; build blocked (expected, T004 adds it) |
| npm deps installed | DONE | 10 runtime + 10 dev deps (exact pins, no ^ ~) |
| Routes implemented | 0 | React Router 7.15.0 installed; router wiring is P01-S03-T001 |
| Providers | AppProviders wired | QueryClientProvider + I18nextProvider in frontend/src/app/providers.tsx |
| Components | 0 | Design system added in T004 |
| Frontend tests | 1 passing | 1 smoke test: providers.test.tsx |

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
| Frontend unit | 0 | — |
| Frontend component | 1 | PASS (providers smoke test) |
| E2E | 0 | — |
| **Total** | **40** | **40 PASS** |

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

- **P00-S01-T001**: Bootstrap mínimo. Pinned versions from debugger 2026-05-08.
- **P00-S01-T002 (2026-05-08)**: Frontend runtime deps installed. AppProviders wired (QueryClientProvider + I18nextProvider). 1 smoke test.
- **P00-S01-T003 (2026-05-08)**: Full backend dep stack installed. Key constraints: (1) pydantic==2.12.5 forced by litellm==1.83.14; (2) redis==6.4.0 forced by celery→kombu<6.5. core/ package created: config.py (pydantic-settings), logging.py (structlog with redaction), db.py (async engine + session factory). main.py updated with structlog wiring (option b: one-line import + call). 39/39 smoke tests GREEN. ruff+mypy clean. uvicorn /health=200.
- **P00-S01-T003 — pyjwt choice**: chose `pyjwt[crypto]` over `python-jose` — modern FastAPI standard in 2026.
- **P00-S01-T003 — asyncpg-only**: no psycopg2-binary; asyncpg covers both SQLAlchemy async + Alembic async migrations.
- **P00-S01-T003 — hatchling config**: added `[tool.hatch.build.targets.wheel] packages = ["app"]` + backend/README.md to fix editable install.
- **P00-S01-T002 — react-router-dom v7**: In v7, `react-router-dom` is a thin re-export of `react-router`. P01-S03-T001 planner must choose API intentionally.
- **P00-S01-T002 — zod v4**: Pinned zod@4.4.3. Breaking changes from v3 documented.

## Known Issues / Risks

- `setup-from-scratch.sh --check` still warns `.env no existe` (expected — .env is gitignored).
- `npm run build` will fail until `tsconfig.json` is added (expected — T004).
- `npm run lint` will fail until ESLint is configured (not in T002/T003 scope).
- pip-audit: 5 findings in `setuptools==65.5.0` (system Python, not declared dep). No CVEs in declared backend deps.
- `redis==6.4.0` is below latest 7.4.0 — constrained by celery/kombu. Will need upgrade when celery releases a kombu that supports redis>=7.

---

> Last updated: 2026-05-08T22:00:00Z
> Updated by: developer (P00-S01-T003)
