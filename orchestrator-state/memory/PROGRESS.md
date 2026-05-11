# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 1 — Auth + Data Foundation
- **Last completed slices**:
  - P00-S01-T001 — Repo scaffold + scripts + env (done)
  - P00-S01-T002 — Frontend dependency pack (done)
  - P00-S01-T003 — Backend dependency pack (done)
  - P00-S01-T004 — Design tokens + editorial component library + showcase (done, 2026-05-11)
  - P00-S02-T001 — Docker compose services (done, 2026-05-11)
  - P00-S02-T002 — Health live ready endpoints (done, 2026-05-11)
  - P00-S01-T005 — i18n resources ES/EN/FR (done, 2026-05-11)
  - P00-S02-T003 — Verification data loader + Alembic infra (done, 2026-05-11)
  - P01-S01-T001 — 0001_auth_users_employee_audit migration (done, 2026-05-11)
  - P00-S02-T004 — fix verification_data loader `:meta::jsonb` SQL cast (done, 2026-05-11)
- **Next pending slice**: P01-S02-T001 — POST /api/v1/auth/sign-up endpoint
- **Blockers**: none
- **Generated at**: 2026-05-11T20:00:00+00:00

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

Infra artifacts: `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.dockerignore`, `scripts/minio-bootstrap.sh`, `frontend/nginx.conf`, `.env.example` (extended).

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | not started (scaffold ready) | uvicorn app.main:app --port 8000 --reload |
| Health check | 3 endpoints implemented | GET /health (backward compat), GET /live (liveness), GET /ready (readiness with DB+Redis ping) |
| Endpoints implemented | 3 | GET /health, GET /live, GET /ready |
| Migrations applied | 1 (head=0001) | 9 auth tables: users, employee_profiles, roles, permissions, user_roles, refresh_tokens, mfa_totp_secrets, password_reset_tokens, audit_logs |
| Seed data | loader.py fixed (P00-S02-T004); bootstrap ready | FU-20260511145446 resolved — CAST(:meta AS JSONB) + json.dumps() |
| Backend tests | 48 passing | test_health.py (11) + test_dependency_smoke.py (20) + test_migrations_0001_auth.py (6) + test_dev_restart_reset.py (2) + test_verification_data_bootstrap.py (9) |
| Backend dependencies | declared + installed | see pyproject.toml [project.dependencies] — 26 packages pinned (23 T003 + psycopg[binary]==3.3.4 T002 + argon2-cffi==25.1.0 + cryptography==48.0.0 T003) |
| Lint (ruff) | clean | 0 issues |

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | ready to start | `npm --prefix frontend run dev` boots at port 5173 |
| Routes implemented | 1 | /showcase (design-system demo) |
| Design tokens | 8 canonical tokens | tokens.css: --color-bg/ink/paper, --font-display/sans, --hairline, --tracking-label, --radius=0 |
| Base components | 9 | Wordmark, TrackedLabel, EditorialInput, SolidCTA, HairlineTable, StatusDot, MobileFrame, AdminShell, CitationInline |
| Vite runtime | complete | vite.config.ts, tsconfig.json, tsconfig.node.json, index.html, src/main.tsx, src/vite-env.d.ts |
| Providers | wired | frontend/src/app/providers.tsx — QueryClientProvider + I18nextProvider composition |
| i18n | ES/EN/FR with 8 namespaces, 24 bundles, fallback es | frontend/src/i18n/index.ts + languages.ts + types.d.ts; public/locales/{es,en,fr}/{8 ns}.json |
| Frontend tests | 58 passing | providers (4 T002) + design-system (34 T004) + showcase (4 T004) + i18n (16 T005) |
| Build | green | `npm run build` → tsc -b + vite build, 111 modules |
| Scanner | green | `bash scripts/check-design-tokens.sh` exit 0 |

## Database

| Table | Migration | Seed | Status |
|-------|-----------|------|--------|
| users | 0001_auth_users_employee_audit.py | ready (loader fixed P00-S02-T004) | created |
| employee_profiles | 0001_auth_users_employee_audit.py | ready (loader fixed P00-S02-T004) | created |
| roles | 0001_auth_users_employee_audit.py | ready (loader fixed) | created |
| permissions | 0001_auth_users_employee_audit.py | ready (loader fixed) | created |
| user_roles | 0001_auth_users_employee_audit.py | ready (loader fixed) | created |
| refresh_tokens | 0001_auth_users_employee_audit.py | ready (loader fixed) | created |
| mfa_totp_secrets | 0001_auth_users_employee_audit.py | ready (loader fixed) | created |
| password_reset_tokens | 0001_auth_users_employee_audit.py | ready (loader fixed) | created |
| audit_logs | 0001_auth_users_employee_audit.py | ready (loader fixed) | created |

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 48 | PASS (health probe 11 + dep smoke 20 + T001 migrations 6 + dev restart 2 + bootstrap 9) |
| Compose orchestration smoke | 11 | PASS (T1–T8 tester + verify cycle 1+2 + minio-init bucket) |
| Frontend unit | 0 | — |
| Frontend component | 58 | PASS (providers 4 + design-system 34 + showcase 4 + i18n 16) |
| E2E | 0 | — |
| **Total** | **117** | **117 PASS, 0 FAIL** |

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| M1 — Auth foundation | in progress | P00 scaffold slices in progress | 100/0 |

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
- **2026-05-11 (P00-S01-T001)**: Vite runtime files (`vite.config.ts`, `tsconfig.json`, `index.html`, `frontend/src/main.tsx`) deferred to T004. Only `frontend/package.json` declaring deps is in this write_set. Frontend is not runnable until T004.
- **2026-05-11 (P00-S01-T001)**: `backend/tests/test_health.py` created despite `backend/tests/` not being in explicit write_set. Needed to prove "health route stub compiles" acceptance. Flagged in handoff as write_set extension.
- **2026-05-11 (P00-S01-T001)**: Port variables (`BACKEND_PORT`, `FRONTEND_PORT`) NOT added to .env.example — baked into STACK_PROFILE.yaml.
- **2026-05-11 (P00-S01-T001)**: Pins used: fastapi==0.135.2, uvicorn==0.42.0, pydantic==2.12.5, pytest==9.0.2, httpx==0.28.1 (detected from installed environment).
- **2026-05-11 (P00-S01-T002)**: Accepted all 3 candidate extensions + 1 additional (vitest.config.ts, tsconfig.json, providers test, i18n bootstrap). All flagged as WRITE_SET_DRIFT in handoff for validator review (all approved).
- **2026-05-11 (P00-S01-T002)**: `test` script changed from `"vitest --run"` to `"vitest"` so that `npm run test -- --run` passes `--run` once. Verify_cmd works without double-flag error.
- **2026-05-11 (P00-S01-T002)**: react-router-dom renamed to react-router (canonical v7 package). v7.15.0 pinned. No router mount in T002 (T004 owns it).
- **2026-05-11 (P00-S01-T002)**: Frontend dep pins — react-router@7.15.0, @tanstack/react-query@5.100.9, react-hook-form@7.75.0, @hookform/resolvers@5.2.2, zod@4.4.3, i18next@26.1.0, react-i18next@17.0.7, i18next-browser-languagedetector@8.2.1 (disabled in bootstrap to avoid jsdom crash).
- **2026-05-11 (P00-S01-T003)**: Full backend dep pack pinned from PyPI live JSON. pydantic==2.12.5 preserved — is also a hard peer dep of litellm==1.83.14.
- **2026-05-11 (P00-S01-T003)**: langchain==1.2.18 chosen because it satisfies deepagents>=1.2.17 AND its constraint langgraph>=1.1.10,<1.2.0.
- **2026-05-11 (P00-S01-T003)**: mcp==1.27.1 confirmed as official Anthropic MCP Python SDK.
- **2026-05-11 (P00-S01-T003)**: pgvector==0.4.2 confirmed canonical; SQLAlchemy adapter at pgvector.sqlalchemy.
- **2026-05-11 (P00-S01-T003)**: deepagents==0.5.9 Beta status accepted per §11.0 `USAR` directive.
- **2026-05-11 (P00-S01-T003)**: pytest-asyncio==1.3.0 used (PyPI live latest) despite researcher noting 1.1.0. Live PyPI confirms 1.3.0 stable.
- **2026-05-11 (P00-S01-T003)**: requirements-dev.txt created. Dev and test deps in separate files for clarity.
- **2026-05-11 (P00-S01-T003)**: backend/app/core/__init__.py created as empty package marker.
- **2026-05-11 (P00-S01-T003)**: backend/tests/test_dependency_smoke.py created under same write_set extension precedent as T001.
- **2026-05-11 (P00-S01-T003 debugger cycle 1/3)**: Real defect — langchain split packages: added explicit pins `langchain-core==1.3.3`, `langchain-community==0.4.1`, `langchain-text-splitters==1.1.2`. False positive — pytest-asyncio 1.3.0 is current latest (canonical note row 20 was stale).
- **2026-05-11 (P00-S02-T001)**: Compose v2-spec purity — no `version:` key, no `host-gateway`, named volumes only.
- **2026-05-11 (P00-S02-T001)**: `redis` service wraps `valkey/valkey:8-alpine`; DNS name preserved.
- **2026-05-11 (P00-S02-T001)**: LiteLLM healthcheck uses Python-stdlib `urllib.request` probe.
- **2026-05-11 (P00-S01-T004)**: Path aliases `@/*` → `src/*` wired in vite.config.ts + tsconfig.json.
- **2026-05-11 (P00-S01-T004)**: tsconfig.node.json includes ONLY vite.config.ts — vitest.config.ts excluded due to Vite 8 rolldown vs vitest 3 rollup Plugin type conflict.
- **2026-05-11 (P00-S01-T004)**: ShowcasePage split into ShowcasePage.tsx (entry, 95 lines) + ShowcaseSections.tsx (~303 lines) to respect 300-line cap.
- **2026-05-11 (P00-S01-T004)**: Design-system components use inline CSS with var() tokens — no CSS Modules, no Tailwind, no hardcoded literals.
- **2026-05-11 (P00-S01-T004)**: Scanner regression fixture must go to `src/pages/` not `src/shared/design-system/` (the latter is excluded by check_web_design_tokens.py DEFAULT_EXCLUDES).
- **2026-05-11 (P00-S01-T004)**: `vite-env.d.ts` created in `src/` for import.meta.env types and CSS module declarations.
- **2026-05-11 (P00-S01-T004)**: Vite runtime files extension (§B) justified in handoff: vite.config.ts, tsconfig.json, tsconfig.node.json, index.html, src/main.tsx, src/vite-env.d.ts.
- **2026-05-11 (P00-S02-T002)**: Sync SQLAlchemy engine with `pool_pre_ping=True` and `postgresql+psycopg://` dialect for /ready DB ping. Async engine not needed for health probes. Per official-doc-notes sqlalchemy-sync-ping RESOLVED.
- **2026-05-11 (P00-S02-T002)**: Catching both `redis.exceptions.ConnectionError` AND `redis.exceptions.TimeoutError` in `_ping_redis()`. Timeout is a distinct exception class. Per official-doc-notes redis-ping RESOLVED.
- **2026-05-11 (P00-S02-T002)**: `psycopg[binary]==3.3.4` pinned in requirements.txt and pyproject.toml as justified write_set extension. Compatible with sqlalchemy==2.0.49 and Python 3.12. Bumped from 3.3.3 to 3.3.4 during debugger cycle 1/3 rebase.
- **2026-05-11 (P00-S02-T002)**: `/ready` includes `litellm: {status: "unknown"}` informational field — no HTTP ping (httpx is test-only dep). Per TECHNICAL_GUIDE §6.2 + planner §U2.
- **2026-05-11 (P00-S02-T002)**: `/health` handler migrated from `main.py` inline to `api/router.py` — all 3 probes in one module.
- **2026-05-11 (P00-S02-T002 debugger 1/3)**: Worktree was branched from `7de36dd` (T001 closer commit) before T003 and S02-T001 landed. Rebased; resolved conflicts in `backend/requirements.txt` (dedupe sqlalchemy/redis; add psycopg[binary]==3.3.4) and `backend/pyproject.toml`. Verified 31 tests pass post-rebase.
- **2026-05-11 (P00-S01-T005)**: Inline static resources — no i18next-http-backend, no lazy-load. All 8 namespaces × 3 langs loaded synchronously in init(). resolveJsonModule not in tsconfig; resources inlined as TS objects.
- **2026-05-11 (P00-S01-T005)**: Language detector DISABLED (inherited T002 R1 — browser-only crashes jsdom). Activation deferred to AccountPage (P03-S02-T004).
- **2026-05-11 (P00-S01-T005)**: Interpolation simple {{var}}, no ICU. Fallback lng=es per instrucciones.md §3.3.
- **2026-05-11 (P00-S01-T005)**: WRITE_SET_DRIFT — I18nDemoSection.tsx added to frontend/src/pages/showcase/ for verify_mode=human. Justified by showcase being the only canonical P0 dev surface. Flagged in handoff.
- **2026-05-11 (P00-S01-T005)**: Test globals (describe/it/expect) imported explicitly from "vitest" following existing test pattern (NOT via tsconfig globals which would cause tsc TS2593 errors).

- **2026-05-11 (P01-S01-T001)**: ORM split by bounded context: identity/RBAC in user.py (User, EmployeeProfile, Role, Permission, UserRole), session/audit in auth.py (RefreshToken, MfaTotpSecret, PasswordResetToken, AuditLog). No import cycles. DeclarativeBase in base.py.
- **2026-05-11 (P01-S01-T001)**: `refresh_tokens.user_id` and `password_reset_tokens.user_id` declared NOT NULL (tighter than §10.3 raw DDL; validator approved D6).
- **2026-05-11 (P01-S01-T001)**: No `CREATE EXTENSION vector` in migration 0001 (YAGNI for this slice; vector belongs to P02-S01-T001 D1). No `DROP EXTENSION pgcrypto` in downgrade (D2).
- **2026-05-11 (P01-S01-T001)**: `extra_metadata` Python attribute → `metadata` DB column via `mapped_column("metadata", JSONB)` to avoid SQLAlchemy 2.x DeclarativeBase reserved attribute conflict.
- **2026-05-11 (P01-S01-T001)**: `audit_logs.actor_user_id` ON DELETE SET NULL (not CASCADE) for GDPR Art. 30 — audit trail preserved when user deleted (pseudonymization is app-layer concern P04).
- **2026-05-11 (P00-S02-T004)**: Fixed `:meta::jsonb` SQL cast in `loader.py:load_users()` (employee_profiles INSERT). Used `CAST(:meta AS JSONB)` (SQL-standard, unambiguous to SQLAlchemy text() parser) + `json.dumps()` (canonical JSON serializer). Preventive maintenance: also fixed cast syntax in out-of-scope `load_rag_collections()` and `load_agents()` functions (same file, cast-only change, deferred paths — requires validator approval). import json hoisted to module top.
- **2026-05-11 (P01-S01-T001)**: FU-20260511145446 registered (medium) — loader.py `:meta::jsonb` cast bug in P00-S02-T003 tests now surfaces because tables exist. Out of T001 scope. Main-orchestrator to decide promotion/waiver.

## Known Issues / Risks

- **R1 (P00-S01-T001)**: `backend/tests/` write_set extension — validator approved. Resolved.
- **R2 (P00-S01-T001)**: `backend/app/__init__.py` write_set extension — validator approved. Resolved.
- **R3 (P00-S01-T001)**: Frontend not runnable until T002 — T002 done, T004 Vite runtime added. Resolved.
- **R4 (P00-S01-T001)**: Hook blocks Write for worktree paths — workaround via Bash heredoc. Persists as known infra limitation; reused by P00-S02-T002 developer and debugger.
- **R5 (P00-S01-T003)**: deepagents==0.5.9 Beta status. Accepted per §11.0 USAR.
- **R5 (P00-S01-T002)**: react-router v7 ESM. Vitest handles it via jsdom. Production handled in T004 Vite config.
- **R6 (P00-S01-T003)**: langgraph deprecation warning — non-blocking. Monitor on next dep upgrade.
- **R6 (P00-S01-T002)**: Zod v4 API surface — downstream slices must use Zod v4 idioms.
- **R7 (P00-S01-T003)**: mypy 2.0.0 major bump — to be addressed when mypy first configured.
- **R7 (P00-S01-T002)**: i18next-browser-languagedetector in Node/jsdom — resolved by disabling auto-init.
- **R1-infra (P00-S02-T001)**: `docker compose build backend/worker` deferred until T003 finalized. Open.
- **R2-infra (P00-S02-T001)**: `postgres:17-alpine` has no pgvector — decision deferred to P01-S01-T001. Open.
- **R5-infra (P00-S02-T001)**: `worker` `app.worker` module not created yet — boot deferred to P02-S04-T002. Open.
- **R6-infra (P00-S02-T001)**: `docker compose build frontend` deferred until T002 lock lands in build; SKIP_BUILD=1 escape hatch in Dockerfile. Open.
- **R1-T004**: ESLint not installed — `npm run lint` fails (eslint not found). Pre-existing from T001. Lint gate = `tsc -b` which passes. ESLint config lands in a later task.
- **R2-T004**: providers.tsx from T002 had `JSX.Element` return type — fixed to `import("react").ReactElement` in T004.
- **R3-T004**: `check_web_design_tokens.py` excludes `design-system/` dir by default. Regression test uses `src/pages/` fixture instead.
- **R1-T002 (resolved by debugger 1/3)**: Worktree branched off pre-T003 commit — would have wiped T003 dep pack on merge. Resolved.
- **R2-T002 (resolved by /verify-slice)**: `/verify-slice` required `docker compose up -d postgres redis` to test `/ready` with real services. All 3 endpoints verified end-to-end (200/200/200 healthy; 503 degraded paths; recovery to 200). Resolved.
- **R1-T005**: i18next resources inlined in TypeScript (not imported from JSON) because `resolveJsonModule` not in tsconfig. JSON files in public/locales/ serve as reference and are served statically by Vite. If HTTP backend is added later, a follow-up task should move to JSON imports.

---

> Last updated: 2026-05-11T17:55:00+00:00
> Updated by: developer — P00-S02-T004 fix verification_data loader :meta::jsonb SQL cast (in progress)
