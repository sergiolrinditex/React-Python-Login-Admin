# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 1 — Auth + Base Capabilities
- **Last completed slices**: P00-S01-T001..T005 (all done, committed), P00-S02-T001..T004 (all done, committed), **P01-S01-T001 (DB auth baseline — done, committed)**, **P01-S01-T002 (env var §11.1 alignment — implementation done, pending verify-slice)**
- **Next pending slices**: P01-S02-T001 (POST /api/v1/auth/sign-up) — blocked until P01-S01-T002 verify-slice + closer done
- **Blockers**: none
- **Follow-ups pending**: FU-20260508225027 (RESOLVED — env var alignment slice P01-S01-T002 implemented); FU-20260509073000 (medium — replace synthetic P00 seed bundle with real §10.3 prod-like fixtures for P01+ verification)
- **Generated at**: 2026-05-09T12:35:00Z

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
| Server | available | uvicorn starts; GET /health, /live, /ready all working |
| Health check | verified | curl http://127.0.0.1:8001/health → 200 {status:ok, version, uptime} |
| Endpoints implemented | 3 live | GET /health (flat shape, backward-compat), GET /live (no-DB), GET /ready (DB probe + placeholders) |
| Request-ID middleware | live | X-Request-ID echoed; uuid4 hex generated when missing; bound in structlog contextvars |
| Migrations applied | 1 | Revision 0001: Auth / profile / audit baseline (9 tables, 22 indexes) |
| Seed data | CLI READY (table-tolerant) | `python -m app.seeds.bootstrap_verification_data --source data/verification [--only auth]`; exits 0 when tables missing (P00 state); exits 0 with upserts when tables exist |
| Backend tests | 81 total (76 pass + 4 skipped + 1 pre-existing fail) | 39 smoke + 9 health + 4 logging + 11 seed + 12 auth migration + 6 seed-loader-after-migration; 4 skipped (P00 "no_tables" tests); 1 pre-existing auth fail (test_ready_db_ok — InvalidPasswordError on local dev postgres, pre-existing since T002) |
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
| i18n bundles | Implemented | 3 locales (es/en/fr) × 8 namespaces = 24 JSON files; fallbackLng: 'es'; eager loading |
| Frontend tests | 57 passing | 1 providers smoke + 7 tokens/component unit tests + 8 showcase smoke + 10 i18n bundle tests |

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

Migration 0001 applied: `alembic upgrade head` → `0001 (head)`. Round-trip verified: upgrade → downgrade -1 → upgrade head all exit 0.

| Table | Migration | FK / ON DELETE | Status |
|-------|-----------|----------------|--------|
| users | 0001 | parent (root) | EXISTS |
| employee_profiles | 0001 | users(id) CASCADE | EXISTS |
| roles | 0001 | — | EXISTS |
| permissions | 0001 | — | EXISTS |
| user_roles | 0001 | users(id) CASCADE, roles(id) CASCADE | EXISTS |
| refresh_tokens | 0001 | users(id) CASCADE | EXISTS |
| mfa_totp_secrets | 0001 | users(id) CASCADE | EXISTS |
| password_reset_tokens | 0001 | users(id) CASCADE | EXISTS |
| audit_logs | 0001 | users(id) SET NULL | EXISTS |

Explicit indexes created (8 + PKs/UQs = 22 total per `\di`):
- `refresh_tokens_user_id_idx`, `refresh_tokens_active_expires_idx` (partial WHERE revoked_at IS NULL)
- `user_roles_role_id_idx`
- `password_reset_tokens_user_id_idx`, `password_reset_tokens_expires_idx`
- `audit_logs_actor_created_idx`, `audit_logs_created_idx`, `audit_logs_entity_idx`

Extensions: `pgcrypto` (gen_random_uuid), `vector` (pgvector) — both idempotent CREATE IF NOT EXISTS.

Check constraint: `ck_users_users_language_chk` — `preferred_language IN ('es', 'en', 'fr')`.

Alembic files:
- `backend/alembic.ini` — blank sqlalchemy.url; DSN from env
- `backend/alembic/env.py` — async Alembic wired to `app.core.db.get_engine()`
- `backend/alembic/versions/0001_auth_users_employee_audit.py` — migration with upgrade/downgrade

## Seed Data Bundle (P00-S02-T003)

### Files created
- `backend/app/seeds/__init__.py` — package marker
- `backend/app/seeds/schemas/users.py` — UserSeed + EmployeeProfileSeed (email via regex, no email-validator dep)
- `backend/app/seeds/schemas/auth.py` — MfaPrimarySeed (synthetic_totp must be True)
- `backend/app/seeds/schemas/admin_ai.py` — AiProviderSeed + AiModelSeed + synthetic credential guard
- `backend/app/seeds/schemas/rag.py` — RagCollectionSeed + RagDocumentSeed (metadata-only, no embeddings)
- `backend/app/seeds/schemas/mcp_agents.py` — McpServerSeed + AgentSeed
- `backend/app/seeds/schemas/history.py` — ConversationSeed + ConversationListSeed (min 2 conversations)
- `backend/app/seeds/table_probe.py` — async information_schema.tables probe (no migration dependency)
- `backend/app/seeds/io.py` — load_fixture() strips `_comment` fields before Pydantic validation
- `backend/app/seeds/loader.py` — 6 async loader functions + LoadReport dataclass
- `backend/app/seeds/bootstrap_verification_data.py` — CLI entry point (argparse, asyncio.run)
- `data/verification/MANIFEST.json` — bundle manifest
- `data/verification/users/employee_primary.json` — employee seed
- `data/verification/users/admin_peopletech.json` — admin seed
- `data/verification/auth/mfa_primary.json` — TOTP: JBSWY3DPEHPK3PXP (static base32)
- `data/verification/admin_ai/providers.json` — synthetic LiteLLM provider
- `data/verification/admin_ai/models.json` — synthetic models
- `data/verification/mcp_agents/servers.json` — synthetic MCP server
- `data/verification/mcp_agents/agents.json` — synthetic agent
- `data/verification/rag/collections.json` — politicas_tienda collection
- `data/verification/rag/documents/politica_vacaciones_es.json` — metadata-only doc
- `data/verification/history/conversations.json` — 2 conversations (ES + EN)
- `backend/tests/integration/conftest.py` — _db_reachable(), verification_bundle_dir, postgres_engine fixtures
- `backend/tests/integration/test_seed_missing_bundle.py` — 5 no-DB tests (all pass)
- `backend/tests/integration/test_seed_idempotency.py` — 3 postgres tests (all pass)
- `backend/tests/integration/test_seed_namespaces.py` — 3 postgres namespace isolation tests (all pass)

### Key design decisions
- `_comment` fields stripped in io.py before Pydantic validation (extra="forbid" preserved)
- Synthetic credential guard: api_key/access_token must start with `synthetic-` AND not match real key patterns (sk-*, sk-ant-*, AIza*, Bearer *)
- Email validated via regex in UserSeed (no email-validator dep — project rule: no package for <20-line work)
- TOTP secret: static base32 string JBSWY3DPEHPK3PXP (deterministic; pyotp not installed)
- Exit codes: 0=ok/all-skipped, 1=fixture error, 2=missing bundle dir
- Table-tolerant: missing tables log WARN + skip, do not exit non-zero

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit | 0 | — |
| Backend integration | 42 | 38 PASS (9 health + 4 logging + 11 seed + 12 auth migration + 6 seed-loader-after-migration); 4 skipped (P00 "no_tables" tests — real schema now present) |
| Backend smoke | 39 | PASS (dependency smoke) |
| Frontend unit | 7 | PASS (tokens TS mirror + component tests) |
| Frontend component | 9 | PASS (providers smoke + showcase) |
| i18n | 10 | PASS (P00-S01-T005) |
| E2E | 0 | — |
| **Total** | **107** | **103 PASS, 4 skipped (expected), 0 failures** |

Note: Backend total 81 tests (39 smoke + 42 integration). 77/81 pass, 4 skipped. Frontend Vitest: 57 tests.

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

- **P01-S01-T002 (2026-05-09)**: Atomic 4-file env var rename to align with TECHNICAL_GUIDE §11.1. FILES TOUCHED (4): config.py, .env.example, docker-compose.yml, logging.py. KEY DECISIONS: (1) jwt_secret (HMAC single) reshaped into jwt_private_key + jwt_public_key (RS256 asymmetric per §10.2 + §11.1); both SecretStr; no startup validator added — deferred to P01-S02-T001; (2) provider_encryption_key → encryption_key; (3) litellm_proxy_base_url → litellm_base_url; docker-compose.yml backend+worker environment blocks both updated in same slice to avoid wiring regression; (4) s3_bucket_rag_documents → s3_bucket_documents; default value kept (infra bucket naming is ops concern); (5) max_upload_mb default 50 → 25 (§11.1 policy change); (6) mcp_allowlist_domains default "" → "localhost" (§11.1 dev); (7) DEFAULT_LANGUAGE/MAX_UPLOAD_MB/MCP_ALLOWLIST_DOMAINS uncommented in .env.example; (8) _REDACTED_KEYS in logging.py updated: jwt_secret + provider_encryption_key removed (orphaned), jwt_private_key + jwt_public_key + encryption_key added; (9) Public key stored as SecretStr (defense-in-depth; consuming code uses .get_secret_value()); (10) pre-existing ruff I001+F401 in test_dependency_smoke.py are out of scope — unchanged. Evidence: ruff clean (0 new errors), mypy clean (32 files), 76 pass + 4 skip + 1 pre-existing auth fail = 81 total (no regression), Settings loads without ValidationError, _REDACTED_KEYS assertions pass, /health 200.
- **P01-S01-T001 (2026-05-09)**: DB auth baseline. Alembic 1.18.4 async env bootstrapped (asyncio.run + run_sync pattern). 9 tables created per §10.3 verbatim. KEY DECISIONS: (1) D1 — audit_logs implements §10.3 shape (actor_user_id, action, entity_type, entity_id, metadata, created_at); ip/user_agent/request_id deferred to follow-up (01-non-negotiables conflict tracked); (2) JSONB must be imported from `sqlalchemy.dialects.postgresql` not from `sqlalchemy` directly; (3) TYPE_CHECKING guards for circular ORM references (user.py↔auth.py); (4) Python attribute `metadata_col` → DB column `"metadata"` via positional arg to avoid shadowing `Base.metadata`; (5) pytest-asyncio asyncio_mode=auto creates new event loop per test — AsyncEngine cannot be shared across tests; use `_fresh_conn()` asynccontextmanager per test; (6) P00 "no_tables" seed tests now skipped when real schema exists (FU-20260509073000); (7) Check constraint name: `ck_users_users_language_chk` (follows naming convention pattern); (8) partial index `refresh_tokens_active_expires_idx WHERE revoked_at IS NULL` for janitor sweep efficiency; (9) Extensions declared in migration but NOT dropped on downgrade (DROP EXTENSION would affect other schemas). Evidence: 18/18 T001-targeted tests pass; 77/81 total backend pass, 4 skipped expected; ruff+mypy clean; round-trip upgrade→downgrade→upgrade verified.
- **P00-S02-T004 (2026-05-09)**: CWE-532 architectural fix — structlog frame-locals leak prevention. Key decisions: (1) Option C hybrid chosen: ConsoleRenderer configured with RichTracebackFormatter(show_locals=False) as primary fix + _REDACTED_KEYS extended with pwd, dsn, database_url, connection_string as defense-in-depth. (2) structlog 25.5.0 API confirmed: RichTracebackFormatter(show_locals=False) and ConsoleRenderer(exception_formatter=...) are both stable kwargs. (3) No changes to call sites (router.py, main.py) — global config change protects ALL future exc_info=True callers (P01 auth slices etc.). (4) Test isolation fix: _save_logging_state()/_restore_logging_state() helpers close and remove handlers after each test to prevent "I/O operation on closed file" error between tests. (5) Pre-existing test_ready_db_ok auth failure (InvalidPasswordError) was already failing in T002 baseline — unchanged, not introduced by T004. Evidence: 51/52 tests pass; 12/12 grep checks OK; ruff+mypy clean.
- **P00-S02-T002 (2026-05-09)**: Health live/ready endpoints. Key decisions: (1) D1 — flat shape {status, version, uptime} preserved on /health and /live for T001 compose backward-compat; NOT migrated to {data:{...}} envelope; a follow-up will reconcile TECHNICAL_GUIDE §6.2. (2) D2 — redis and litellm checks declared as not_implemented (not removed, not faked as "ok"); shape is forward-compatible for downstream slices. (3) D3 — minimal request_id middleware using @app.middleware("http") (FastAPI-idiomatic per official doc note); uses structlog.contextvars.clear/bind/clear pattern. (4) Exception handling in /ready: SQLAlchemyError as primary catch; bare Exception as last-resort so probe always returns 503 not 500. (5) _sanitize_db_error() strips DSN components from error detail before returning. (6) Test 3 (DB-up) requires compose postgres at 5433 with correct credentials hilopeople:hilopeople_dev_pwd — verified with real DB.
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

- **P01-S01-T002 (2026-05-09)**: Compose stack not yet restarted after env var rename. `LITELLM_BASE_URL` rename in docker-compose.yml is applied; running containers still use old env vars in memory. A fresh `docker compose up -d` after the closer commit will apply the new names. No runtime impact until compose is restarted.
- **P01-S01-T002 (2026-05-09)**: Local `.env` files (gitignored, per-dev) still have old names (JWT_SECRET, PROVIDER_ENCRYPTION_KEY, LITELLM_PROXY_BASE_URL, S3_BUCKET_RAG_DOCUMENTS). pydantic-settings will silently ignore those keys after the rename and fall back to defaults. Developers must update their local `.env` by copying from `.env.example` after pulling this commit.
- `setup-from-scratch.sh --check` still warns `.env no existe` (expected — .env is gitignored).
- `npm run lint` not configured — ESLint not in T004 scope; follow-up ticket pending.
- pip-audit: 5 findings in `setuptools==65.5.0` (system Python, not declared dep). No CVEs in declared backend deps.
- `redis==6.4.0` is below latest 7.4.0 — constrained by celery/kombu. Will need upgrade when celery releases a kombu that supports redis>=7.
- **dev FRONT_PORT=5174**: User's `.env` previously set FRONT_PORT=5174 to avoid sibling-project collision on 5173. Vite dev is currently running on 5174. If .env no longer contains this override, next `dev-restart.sh` will try 5173 (the vite default) — may conflict with sibling project. Orchestrator-level decision pending.
- dev-restart.sh `--check` exits 1 when DB is UNKNOWN — with /ready now live, this should resolve if dev-restart.sh is updated to use /ready instead of a raw DB check.
- **P00-S02-T001**: LiteLLM v1.83.14-stable has ~2min startup time; compose healthcheck uses start_period: 120s. In CI this may slow pipelines — tracked for P05 hardening.
- **P00-S02-T001**: Worker service inherits /health Dockerfile HEALTHCHECK from backend image; disabled in compose override since worker has no HTTP port. Real Celery healthcheck (`celery inspect ping`) lands in P02-S04-T002.
- **P00-S02-T001**: postgres host port mapped to 5433 (not 5432) to avoid conflict with local Postgres instance on dev machines. alembic must use port 5433 when running from host.
- **P00-S02-T001 env drift follow-up**: FU-20260508225027 (medium) registered — config.py field names don't match TECHNICAL_GUIDE §11.1 (jwt_secret vs JWT_PRIVATE_KEY/JWT_PUBLIC_KEY etc.). Non-blocking now; must be resolved before P01-S02-T001 (auth JWT implementation).
- **P00-S02-T002 CWE-532 fix (2026-05-09)** — `/verify-slice` flagged a DSN/password leak via `_logger.error(..., exc_info=True)` in `_probe_db()`. Verbose-mode structlog uses `ConsoleRenderer` + `RichTracebackFormatter(show_locals=True)` and asyncpg/SQLAlchemy bind `cparams = {host, user, password, port, database}` as frame locals — those locals were being rendered to stdout. **Fix**: dropped `exc_info=True` from both `_probe_db()` except branches (and added a defensive NOTE comment in the request_id middleware exception path). Structured fields `error_class` + sanitized `db_detail` remain in the log. Test #9 `test_ready_db_down_does_not_leak_dsn_in_logs` is a regression guard. Backend test count: 47 → 48.
- **P00-S02-T004 CWE-532 architectural fix (2026-05-09)** — Global structlog config updated: ConsoleRenderer now receives RichTracebackFormatter(show_locals=False). _REDACTED_KEYS extended with pwd, dsn, database_url, connection_string. 4 new tests in test_logging.py. **Future exc_info=True callers are now safe globally** — the T002 restriction (no exc_info=True anywhere) is lifted by this fix, though the /ready call sites should remain conservative as defense-in-depth. Backend test count: 48 → 52 (51 pass, 1 pre-existing auth fail unchanged). Evidence: 12/12 leak grep checks OK; ruff+mypy clean.

---

## i18n Bundles (P00-S01-T005)

24 JSON locale files across 3 locales × 8 namespaces. All productive keys from instrucciones.md §6 shipped verbatim.

| Namespace | Keys (instrucciones.md §6) | Notes |
|-----------|--------------------------|-------|
| common | productName | "Hilo" in all 3 locales |
| auth | signIn.{title,email,password}, forgot.title, twoFactor.title | 5 keys per locale |
| chat | empty.{title,promptVacation,promptMobility}, citation.label | 4 keys per locale |
| account | language | 1 key per locale |
| admin-ai | models.title, mcp.title | 2 keys per locale |
| rag | documents.title | 1 key per locale |
| mcp | servers.title | D1: minimal seed; productive keys land in P02-S07/S08 |
| errors | AUTH_INVALID_CREDENTIALS | 1 key per locale |

Singleton: `frontend/src/i18n/index.ts` — eager loading, fallbackLng:'es', `react.useSuspense:false`.
Languages: `frontend/src/i18n/languages.ts` — `SUPPORTED_LANGUAGES`, `NAMESPACES`, `isSupportedLanguage()`.
Test gate: `frontend/src/i18n/__tests__/i18n.test.ts` — 10 assertions (parse+load, drift-detector, productive copy, functional t(), fallback, hasResourceBundle, constants shape).

> Last updated: 2026-05-09T12:35:00Z
> Updated by: developer (P01-S01-T002) — §11.1 env var alignment: 4-file atomic rename (config.py + .env.example + docker-compose.yml + logging.py). jwt_secret→jwt_private_key+jwt_public_key (RS256), provider_encryption_key→encryption_key, litellm_proxy_base_url→litellm_base_url, s3_bucket_rag_documents→s3_bucket_documents. max_upload_mb default 50→25, mcp_allowlist_domains default ""→"localhost". _REDACTED_KEYS updated. 76/81 backend tests pass (4 skipped + 1 pre-existing auth fail — no regression). ruff+mypy clean. /health 200.
