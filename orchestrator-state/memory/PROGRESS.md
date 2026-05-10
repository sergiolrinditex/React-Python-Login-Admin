# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 1 — Auth + Base Capabilities
- **Last completed slices**: P00-S01-T001..T005 (all done, committed), P00-S02-T001..T004 (all done, committed), **P00-S02-T005 (productive verification bundle — done, committed `ae3dfc7`)**, **P00-S02-T006 (dynamic LiteLLM model discovery endpoint — done, committed `0c2ea37`)**, **P01-S01-T001 (DB auth baseline — done, committed `99d555b`)**, **P01-S01-T002 (env var §11.1 alignment — done, committed `679f363`)**, **P01-S01-T004 (env_file path fix + DATABASE_URL port 5433 — done, committed `8503e00`)**, **P00-S02-T008 (deepagents Supervisor + topic-routing runtime — done, committed `9aacaca`)**, **P00-S02-T007 (AdminAiModelsPage discover wizard UI — done, committed `aaf9e84`)**, **P00-S02-T009 (httpx logger suppression — CWE-532 — done, committed `b055b00`)**, **P00-S02-T010 (fix admin_ai seed loader — done, committed `41a9092`)**, **P00-S02-T011 (dev .env ENCRYPTION_KEY hygiene — done, committed `d24e0d6`)**, **P01-S01-T003 (quote MAIL_FROM_NAME in .env.example — implementation done, pending verify-slice)**, **P01-S01-T005 (audit_logs 4 compliance cols — implementation done 2026-05-10T08:26Z, pending validator/tester + verify-slice)**, **P01-S02-T001 (POST /api/v1/auth/sign-up — implementation done 2026-05-10T09:00Z, pending validator/tester)**, **P00-S02-T013 (.env.example bash-source hygiene — implementation done 2026-05-10T11:42Z, pending validator/tester + verify-slice)**, **P00-S02-T012 (SQLAlchemy echo=False CWE-532 fourth layer — implementation done 2026-05-10T11:55Z, pending validator/tester + verify-slice)**
- **Next pending slices**: P01-S02-T002 (sign-in / JWT issuance) — after P01-S02-T001 verify-slice closes
- **Blockers**: none
- **Follow-ups pending**: FU-20260508225027 (RESOLVED); FU-20260509073000 (RESOLVED by P00-S02-T005, registry reconciled); FU-20260509130036 RESOLVED by P01-S01-T004. FU-X1 (dynamic LiteLLM model discovery) = **RESOLVED by P00-S02-T006**. FU-X2 (discovery wizard UI) = **RESOLVED by P00-S02-T007** (implementation done, pending verify-slice). FU-X3 (deepagents supervisor runtime) = **RESOLVED by P00-S02-T008**. FU-20260509220224 (httpx logger leak) = **RESOLVED by P00-S02-T009** (implementation done, pending verify-slice). **FU-20260509220235 (admin_ai seed loader column) = RESOLVED by P00-S02-T010** (implementation done, pending verify-slice). **FU-20260508230723 (quote MAIL_FROM_NAME in .env.example) = RESOLVED by P01-S01-T003** (implementation done, pending verify-slice). **FU-20260510071705 (.env.example bash-source <...> placeholders) = RESOLVED by P00-S02-T013** (implementation done, pending verify-slice). **FU-20260510044529 (SQLAlchemy echo=True leaks Fernet ciphertext) = RESOLVED by P00-S02-T012** (implementation done, pending verify-slice). Owed: rotate `VERIFICATION_GEMINI_API_KEY` in GCP (post-T005 hygiene, out of T009 scope). DeprecationWarning HTTP_422_UNPROCESSABLE_ENTITY→HTTP_422_UNPROCESSABLE_CONTENT: low-severity, tracked for follow-up.
- **Generated at**: 2026-05-10T11:55:00Z (P00-S02-T012 developer — SQLAlchemy echo=False CWE-532 defense-in-depth: backend/app/core/db.py line 81 echo=False permanent; 2 new regression tests; 160 pass + 12 skipped + 0 failures)

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
| Endpoints implemented | 5 live | GET /health, GET /live, GET /ready, POST /api/v1/admin/ai/providers/{id}/discover-models, **POST /api/v1/auth/sign-up** |
| Request-ID middleware | live | X-Request-ID echoed; uuid4 hex generated when missing; bound in structlog contextvars |
| Migrations applied | 2 | Revision 0001 (auth baseline: 9 tables, 22 indexes) + Revision 0003 (admin_ai: 3 tables: ai_providers, ai_provider_credentials, ai_models) |
| Seed data | CLI READY (table-tolerant) | `python -m app.seeds.bootstrap_verification_data --source data/verification [--only auth]`; exits 0 when tables missing (P00 state); exits 0 with upserts when tables exist |
| Admin AI discovery | P00-S02-T006 done | POST /api/v1/admin/ai/providers/{id}/discover-models — Gemini/OpenAI/LiteLLM clients, Fernet encryption, audit log, admin stub guard |
| Backend tests | 160 pass + 12 skipped + 0 failures | 39 smoke + 9 health + 4 logging + 11 seed + 12 auth migration + 6 seed-loader + 7 admin_ai integration (3 pass, 4 skip external-API) + **8 auth sign-up integration** (all pass) + **2 db engine echo regression** (T1 echo=False unit, T2 contrast echo=True vs echo=False, T3 skipped no GEMINI key); `email-validator==2.2.0` added to deps (Pydantic EmailStr requires it) |
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
| Routes implemented | 3 (/showcase, /admin/ai/models, /admin/ai/models/new) | /showcase + 2 admin-AI MVP routes wired in src/main.tsx (P00-S02-T007); full productive routes in P01-S03-T001 |
| Providers | AppProviders wired | QueryClientProvider + I18nextProvider in frontend/src/app/providers.tsx |
| Components | 8 shipped | Wordmark, TrackedLabel, StatusDot, EditorialInput, SolidCTA, HairlineTable, MobileFrame, AdminShell |
| Design tokens | Implemented | CSS custom properties in shared/styles/tokens.css + TS mirror in shared/styles/index.ts |
| i18n bundles | Implemented | 3 locales (es/en/fr) × 8 namespaces = 24 JSON files; fallbackLng: 'es'; eager loading |
| Frontend tests | 87 passing | +30 new (P00-S02-T007): 9 API client (discoverModels + auth helper) + 6 wizard step transitions + 8 DiffReviewTable component + 5 AdminAiModelsPage shell + 2 domain (via component) = 30 new admin_ai tests |

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

Migrations applied: 0001 (auth baseline) + 0002 (audit_logs compliance cols) + 0003 (admin_ai tables). Head = `0003` (chain: 0001→0002→0003). Round-trip verified for 0002+0003: full round-trip (head→downgrade -1→downgrade -1→upgrade head) exits 0. Migration 0003 updated to point down_revision="0002" (was "0001") — keeps single linear head.

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
| audit_logs | 0001+0002 | users(id) SET NULL | EXISTS — 0002 added 4 compliance cols (ip INET, user_agent TEXT, request_id TEXT, resource TEXT) all nullable; pre-existing rows back-compat |
| ai_providers | 0003 | — (no FK to users) | EXISTS |
| ai_provider_credentials | 0003 | ai_providers(id) CASCADE | EXISTS |
| ai_models | 0003 | ai_providers(id) CASCADE | EXISTS |

Explicit indexes from 0001 (8 + PKs/UQs = 22 total):
- `refresh_tokens_user_id_idx`, `refresh_tokens_active_expires_idx` (partial WHERE revoked_at IS NULL)
- `user_roles_role_id_idx`
- `password_reset_tokens_user_id_idx`, `password_reset_tokens_expires_idx`
- `audit_logs_actor_created_idx`, `audit_logs_created_idx`, `audit_logs_entity_idx`

Additional indexes from 0003 (admin_ai):
- `ix_ai_provider_credentials_provider_id` (FK join on fetch_credential)
- `ix_ai_provider_credentials_expires_at` (partial WHERE NOT NULL, for TTL queries)
- `ix_ai_models_provider_id` (FK join)
- `uq_ai_models_provider_id_model_id` (UNIQUE — prevents duplicate discovery)

Extensions: `pgcrypto` (gen_random_uuid), `vector` (pgvector) — both idempotent CREATE IF NOT EXISTS.

Check constraint: `ck_users_users_language_chk` — `preferred_language IN ('es', 'en', 'fr')`.

Alembic files:
- `backend/alembic.ini` — blank sqlalchemy.url; DSN from env
- `backend/alembic/env.py` — async Alembic wired to `app.core.db.get_engine()`
- `backend/alembic/versions/0001_auth_users_employee_audit.py` — migration with upgrade/downgrade (IMMUTABLE — commit 99d555b)
- `backend/alembic/versions/0002_audit_logs_add_compliance_cols.py` — NEW P01-S01-T005: 4 nullable cols on audit_logs
- `backend/alembic/versions/0003_admin_ai_providers_models.py` — migration with upgrade/downgrade (P00-S02-T006; down_revision updated 0001→0002 to maintain linear chain)

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

## Productive Verification Bundle (P00-S02-T005)

### Bundle type: productive

- Owner emails: `s.lopezrap+employee@gmail.com` (employee, MFA-enabled) / `s.lopezrap+admin@gmail.com` (admin, no MFA)
- Real keys live in `.env.local` (gitignored), referenced in JSON via `*_env` fields (e.g. `api_key_env: "VERIFICATION_GEMINI_API_KEY"`)
- 3 PDFs generated via stdlib (no reportlab dep): `politica_vacaciones_2026_es.pdf`, `vigilancia_normativa_q1_2026_es.pdf`, `boe_cambio_q1_2026_es.pdf`
- Schema additions: `agent_type`, `framework`, `parent_agent_name`, `subagent_topics` in AgentSeed; new `AiModelSeed` fields `name`, `capability`, `is_active`, `auto_discovered`; `api_key_env`/`api_key_backup_env` in AiProviderSeed; `access_token_env` in McpServerSeed; `backup_codes_argon2` in MfaPrimarySeed
- Auth loader SQL rewritten to match §10.3 schema: `status`, `password_hash`, `preferred_language` (not legacy `role`, `is_active`, `mfa_enabled`)
- Acceptance #3 reword: J100..J105 e2e UI verification deferred to per-journey gates (screens/APIs not yet built)
- Orphan file `data/verification/rag/documents/politica_vacaciones_es.json` deleted (legacy synthetic)
- `.env.example` has 5 `VERIFICATION_*` placeholder lines

### Pending follow-ups (closer will register)
- FU-X1: Dynamic LiteLLM model discovery endpoint, severity medium, linked to P02-S05
- FU-X2: Discovery wizard UI (AdminAiModelsPage), severity medium, linked to P04-S01-T002
- FU-X3: deepagents Supervisor pattern + topic routing runtime, severity medium, linked to P02-S08

## Tests Summary

| Level | Count | Status |
|-------|-------|--------|
| Backend unit (seeds) | 16 | PASS (P00-S02-T005 new: MfaPrimarySeed, AiProviderSeed, AiModelSeed, McpServerSeed, AgentSeed, resolve_env_var) |
| Backend integration | 57 | PASS (was 49 + 8 new auth sign-up tests); 17 skipped (external-API gates + expected skips) |
| Backend smoke | 39 | PASS (dependency smoke) |
| Frontend unit | 7 | PASS (tokens TS mirror + component tests) |
| Frontend component | 9 | PASS (providers smoke + showcase) |
| i18n | 10 | PASS (P00-S01-T005) |
| E2E | 0 | — |
| **Total backend** | **152 pass + 17 skipped** | **0 failures** |

Note: Backend total 152 tests (39 smoke + 113 integration). 152 pass, 17 skipped, 0 failures. Frontend Vitest: 87 tests.

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

- **P01-S02-T001 (2026-05-10)**: POST /api/v1/auth/sign-up implementation. FILES TOUCHED (7): `backend/app/features/auth/__init__.py` (new), `backend/app/features/auth/errors.py` (new — typed domain errors), `backend/app/features/auth/schemas.py` (new — SignUpRequest/Response/AuthErrorCode), `backend/app/features/auth/repository.py` (new — insert_user/employee_profile/audit_log), `backend/app/features/auth/service.py` (new — sign_up use case), `backend/app/features/auth/routes.py` (new — APIRouter POST /sign-up), `backend/app/main.py` (auth_router wired), `backend/app/core/config.py` (corporate_email_domains field + list property), `backend/pyproject.toml` + `backend/requirements.txt` (email-validator==2.2.0), `.env.example` (CORPORATE_EMAIL_DOMAINS placeholder). KEY DECISIONS: (1) `email-validator==2.2.0` is NOT a transitive dep of pydantic-core — must be declared explicitly for Pydantic EmailStr; (2) Argon2id PasswordHasher() with library defaults (m=65536, t=3, p=4 — OWASP-2024 compliant); (3) T005 native audit_log columns (ip, user_agent, request_id, resource) written directly — no JSONB stash needed; (4) 409 non-leaky: AUTH_EMAIL_TAKEN + "Email no disponible" — does not confirm whether email exists; (5) Corporate email allowlist permissive when empty (dev mode); (6) mfa_required=True always; T001 does NOT insert into mfa_totp_secrets (TOTP secret generated at enrollment time — task-pack D3); (7) autouse `reset_db_engine_singleton` fixture resets `app.core.db._engine=None` between tests — critical for pytest-asyncio event loop isolation (asyncio_mode=auto creates new loop per test); (8) ASGITransport pattern (not deprecated AsyncClient(app=app)). Evidence: 8/8 integration tests pass under both ENABLE_VERBOSE_LOGGING values; 152 total backend pass; ruff clean; curl evidence in orchestrator-state/tasks/evidence/P01-S02-T001/.
- **P00-S02-T009 (2026-05-10)**: httpx logger suppression — CWE-532 third-layer defense. FILES TOUCHED (2): backend/app/core/logging.py (3 lines + docstring), backend/tests/test_logging.py (5 new tests). KEY DECISIONS: (1) Named-logger approach chosen over event_hooks/Filter/custom transport — smallest change, no write_set widening, idempotent inside existing guard; (2) Both "httpx" and "httpcore" loggers pinned to WARNING UNCONDITIONALLY — not inside if/else verbose branches — so the guard applies even if root level ever changes; (3) MockTransport reproduces the leak vector faithfully — httpx logs the REQUEST URL before transport runs, so a fake transport still proves the fix; (4) async test functions used for T1/T3/T4 (pytest-asyncio asyncio_mode=auto required, same as test_admin_ai_discover_models.py); (5) _restore_logging_state_with_httpx() extends the existing pattern to also reset httpx/httpcore logger levels (cross-test isolation); (6) T5 (real Gemini) skipif-gated on VERIFICATION_GEMINI_API_KEY — same guard as T006's discover-models real test; (7) Do NOT modify test_admin_ai_discover_models.py (owned by T006). Evidence: 8 pass + 1 skipped (deterministic); ruff+mypy clean; 107 pass + 1 skipped in full suite (no regressions); leak-before-fix.txt shows AIzaSyFAKE in httpx INFO line; leak-after-fix.txt shows 0 AIza characters. Acceptance instrucciones §2 #8 satisfied: "Los logs no imprimen secretos, tokens ni contenido sensible completo."
- **P01-S01-T004 (2026-05-09)**: Fixed two bugs surfaced by FU-20260509130036. FILES TOUCHED (2): backend/app/core/config.py, .env.example. Also updated local .env (gitignored, per-dev — not committed). KEY DECISIONS: (1) pydantic-settings 2.14.1 `env_file=".env"` is cwd-relative; fixed by anchoring to absolute `Path(__file__).resolve().parents[3] / ".env"` — parents[3] = project root for config.py at backend/app/core/config.py; (2) DATABASE_URL default changed 5432→5433 (hilo-postgres compose mapping "5433:5432"; port 5432 occupied by sibling project); (3) Mode A vs Mode B documented clearly in .env.example; (4) `database_url` remains SecretStr — only host:port/dbname logged in verbose mode (never the password); (5) alembic/env.py and dev-restart.profile.sh required NO changes — they propagate via get_engine()→get_settings() chain; (6) local .env updated by developer in this run (gitignored — part of verification workflow). Evidence: 77 pass + 4 skipped + 0 fail; ruff+mypy clean on 32 files; ENABLE_VERBOSE_LOGGING=true shows env_file path + db_host_port (no password); ENABLE_VERBOSE_LOGGING=false shows no DEBUG logs; test_ready_returns_200_when_db_ok: FAIL→PASS.
- **P01-S01-T002 (2026-05-09)**: Atomic 4-file env var rename to align with TECHNICAL_GUIDE §11.1. FILES TOUCHED (4): config.py, .env.example, docker-compose.yml, logging.py. KEY DECISIONS: (1) jwt_secret (HMAC single) reshaped into jwt_private_key + jwt_public_key (RS256 asymmetric per §10.2 + §11.1); both SecretStr; no startup validator added — deferred to P01-S02-T001; (2) provider_encryption_key → encryption_key; (3) litellm_proxy_base_url → litellm_base_url; docker-compose.yml backend+worker environment blocks both updated in same slice to avoid wiring regression; (4) s3_bucket_rag_documents → s3_bucket_documents; default value kept (infra bucket naming is ops concern); (5) max_upload_mb default 50 → 25 (§11.1 policy change); (6) mcp_allowlist_domains default "" → "localhost" (§11.1 dev); (7) DEFAULT_LANGUAGE/MAX_UPLOAD_MB/MCP_ALLOWLIST_DOMAINS uncommented in .env.example; (8) _REDACTED_KEYS in logging.py updated: jwt_secret + provider_encryption_key removed (orphaned), jwt_private_key + jwt_public_key + encryption_key added; (9) Public key stored as SecretStr (defense-in-depth; consuming code uses .get_secret_value()); (10) pre-existing ruff I001+F401 in test_dependency_smoke.py are out of scope — unchanged. Evidence: ruff clean (0 new errors), mypy clean (32 files), 76 pass + 4 skip + 1 pre-existing auth fail = 81 total (no regression), Settings loads without ValidationError, _REDACTED_KEYS assertions pass, /health 200.
- **P01-S01-T001 (2026-05-09)**: DB auth baseline. Alembic 1.18.4 async env bootstrapped (asyncio.run + run_sync pattern). 9 tables created per §10.3 verbatim. KEY DECISIONS: (1) D1 — audit_logs implements §10.3 shape (actor_user_id, action, entity_type, entity_id, metadata, created_at); ip/user_agent/request_id deferred to follow-up (01-non-negotiables conflict tracked); (2) JSONB must be imported from `sqlalchemy.dialects.postgresql` not from `sqlalchemy` directly; (3) TYPE_CHECKING guards for circular ORM references (user.py↔auth.py); (4) Python attribute `metadata_col` → DB column `"metadata"` via positional arg to avoid shadowing `Base.metadata`; (5) pytest-asyncio asyncio_mode=auto creates new event loop per test — AsyncEngine cannot be shared across tests; use `_fresh_conn()` asynccontextmanager per test; (6) P00 "no_tables" seed tests now skipped when real schema exists (FU-20260509073000); (7) Check constraint name: `ck_users_users_language_chk` (follows naming convention pattern); (8) partial index `refresh_tokens_active_expires_idx WHERE revoked_at IS NULL` for janitor sweep efficiency; (9) Extensions declared in migration but NOT dropped on downgrade (DROP EXTENSION would affect other schemas). Evidence: 18/18 T001-targeted tests pass; 77/81 total backend pass, 4 skipped expected; ruff+mypy clean; round-trip upgrade→downgrade→upgrade verified.

### Historical entries (compacted 2026-05-10)

> Compacted from 8 prior P00-S02 / P00-S01 slice entries. Substantive decisions promoted to `decisions.md`; non-blocking risks promoted to `risk-register.md`. Snapshot of original PROGRESS.md preserved at `orchestrator-state/memory/archive/2026-05-10/PROGRESS-pre-compact-2026-05-10T001108.md`.

- **2026-05-09 · P00-S02-T005 · Productive verification bundle delivery · committed**
  Bundle type productive: real owner emails, `*_env` JSON refs to `.env.local`, 3 PDFs via stdlib, AgentSeed extra fields (agent_type/framework/parent_agent_name/subagent_topics), AiModelSeed reshape (name/capability/is_active/auto_discovered), auth loader SQL aligned to §10.3, orphan synthetic doc removed.
  Dec: bundle_type-aware loaders; auth SQL §10.3; AgentSeed extras → promoted to decisions.md.
  Pending: FU-X1 (LiteLLM model discovery) RESOLVED by P00-S02-T006; FU-X2 (discovery wizard UI) ACTIVE; FU-X3 (deepagents Supervisor) RESOLVED by P00-S02-T008.
  Tests: 104 pass + 5 skipped (backend); ruff+mypy clean on app/+tests/; .env.local gitignored.
  Seeds preserved: TOTP `JK5ZSKVT3IFUQYHDCTWIMUMA6BBXUE2T` (productive, dev-rotable); `JBSWY3DPEHPK3PXP` (synthetic, line ~218).

- **2026-05-09 · P00-S02-T004 · CWE-532 architectural fix · committed**
  Global structlog config: `ConsoleRenderer` + `RichTracebackFormatter(show_locals=False)` as primary fix; `_REDACTED_KEYS` extended (pwd, dsn, database_url, connection_string).
  Dec: hybrid Option C — global show_locals=False + extended redaction → promoted to decisions.md. Lifts T002 "no exc_info=True" cultural restriction → promoted to risk-register.md as resolved.
  Pending: -.
  Tests: 51/52 pass; 12/12 leak grep checks OK; ruff+mypy clean.

- **2026-05-09 · P00-S02-T002 · Health live/ready endpoints · committed**
  Endpoints: `/health`, `/live`, `/ready` with flat `{status, version, uptime}` shape; redis/litellm reported as `not_implemented` (forward-compatible). Request-ID middleware via `@app.middleware("http")` + structlog contextvars. `_sanitize_db_error()` strips DSN.
  Dec: flat shape preserved (NOT migrated to envelope); not_implemented over fake-ok → promoted to decisions.md.
  Pending: TECHNICAL_GUIDE §6.2 envelope reconciliation (deferred follow-up).
  Tests: 47→48 pass; test #9 `test_ready_db_down_does_not_leak_dsn_in_logs` is regression guard.

- **2026-05-09 · P00-S02-T001 · Docker compose stack (Rancher-ready) · committed**
  7 services: postgres pg18 :5433, redis 8-alpine :6379, minio, litellm v1.83.14-stable :4000 (start_period 120s), backend, worker (healthcheck disabled), frontend (gated). Multi-stage non-root images, stdout-only logs, named volumes, no privileged.
  Dec: image pins (pgvector pg18-bookworm, redis 8-alpine, litellm v1.83.14-stable, nginx-unprivileged 1.29-alpine, python:3.13-slim-bookworm), postgres :5433 host port → promoted to decisions.md.
  Pending: LiteLLM cold start, worker Celery healthcheck (P02-S04-T002), postgres :5433 alembic guard → promoted to risk-register.md.
  Tests: compose stack verified healthy 6/6 non-gated services.

- **2026-05-08 · P00-S01-T003 · Backend dep stack installed · committed**
  Pins: `pydantic==2.12.5` (forced by litellm==1.83.14), `redis==6.4.0` (forced by celery→kombu<6.5). core/ package: config.py (pydantic-settings), logging.py (structlog+redaction), db.py (async engine).
  Dec: pyjwt[crypto] over python-jose; asyncpg-only (no psycopg2); hatchling editable install via `[tool.hatch.build.targets.wheel]` → promoted to decisions.md.
  Pending: -.
  Tests: 39/39 smoke GREEN; ruff+mypy clean; uvicorn /health=200.

- **2026-05-08 · P00-S01-T002 · Frontend runtime deps + AppProviders · committed**
  10 runtime + 10 dev deps installed (exact pins, no ^~). AppProviders wired (QueryClientProvider + I18nextProvider). React 19.2.6 + react-router-dom 7.15.0 + zod 4.4.3.
  Dec: react-router-dom v7 thin re-export of react-router; zod v4 breaking changes documented → promoted to decisions.md.
  Pending: -.
  Tests: 1 smoke test.

- **2026-05-09 · P00-S01-T004 · Path-A bootstrap completion + design system · committed**
  Vite config co-located, Vitest separate (vitest.config.ts). Tokens via CSS custom properties (tokens.css) + TS string mirror (shared/styles/index.ts). 8 design-system components shipped. `MobileFrame` (TECHNICAL_GUIDE wins).
  Dec: tokens architecture (CSS vars + TS string mirror, not values); MobileFrame name; tsconfig.node.json composite:true; jsdom getAttribute().toContain pattern → promoted to decisions.md.
  Pending: ESLint not configured (follow-up).
  Tests: 47 GREEN; build passing.

- **P00-S01-T001 · Bootstrap mínimo · committed**
  Pinned versions from debugger 2026-05-08. No further detail in original entry.

## Known Issues / Risks

- **P01-S01-T002 (2026-05-09)**: Compose stack not yet restarted after env var rename. `LITELLM_BASE_URL` rename in docker-compose.yml is applied; running containers still use old env vars in memory. A fresh `docker compose up -d` after the closer commit will apply the new names. No runtime impact until compose is restarted.
- **P01-S01-T002 (2026-05-09)**: Local `.env` files (gitignored, per-dev) still have old names (JWT_SECRET, PROVIDER_ENCRYPTION_KEY, LITELLM_PROXY_BASE_URL, S3_BUCKET_RAG_DOCUMENTS). pydantic-settings will silently ignore those keys after the rename and fall back to defaults. Developers must update their local `.env` by copying from `.env.example` after pulling this commit.
- **P01-S01-T004 (2026-05-09)**: Developers with an existing local `.env` must update DATABASE_URL port from 5432 to 5433 to match the hilo-postgres compose mapping. The `.env.example` now documents both Mode A (localhost:5433 native dev) and Mode B (postgres:5432 in-compose). Also, old key names (JWT_SECRET etc.) in local `.env` are still silently ignored (pydantic-settings `extra="ignore"`). Run `bash scripts/dev-restart.sh --reset` after updating `.env`.
- `setup-from-scratch.sh --check` still warns `.env no existe` (expected — .env is gitignored).
- `npm run lint` not configured — ESLint not in T004 scope; follow-up ticket pending.
- pip-audit: 5 findings in `setuptools==65.5.0` (system Python, not declared dep). No CVEs in declared backend deps.
- `redis==6.4.0` is below latest 7.4.0 — constrained by celery/kombu. Will need upgrade when celery releases a kombu that supports redis>=7.
- **dev FRONT_PORT=5174**: User's `.env` previously set FRONT_PORT=5174 to avoid sibling-project collision on 5173. Vite dev is currently running on 5174. If .env no longer contains this override, next `dev-restart.sh` will try 5173 (the vite default) — may conflict with sibling project. Orchestrator-level decision pending.
- dev-restart.sh `--check` exits 1 when DB is UNKNOWN — with /ready now live, this should resolve if dev-restart.sh is updated to use /ready instead of a raw DB check.
- **P00-S02-T001 ops risks (compacted 2026-05-10)**: LiteLLM ~2min cold start (start_period 120s, P05 hardening), worker Celery healthcheck deferred to P02-S04-T002, postgres host port :5433 must be used by alembic from host. Full detail promoted to `orchestrator-state/memory/risk-register.md`.
- **P00-S02-T001 env drift follow-up**: FU-20260508225027 (medium) registered — config.py field names don't match TECHNICAL_GUIDE §11.1 (jwt_secret vs JWT_PRIVATE_KEY/JWT_PUBLIC_KEY etc.). RESOLVED by P01-S01-T002 (atomic 4-file rename). Kept here for chronological context.
- **CWE-532 leak fixes (2026-05-09)** — DSN/password leak via `exc_info=True` rendering asyncpg `cparams` frame locals was fixed locally in P00-S02-T002 (dropped `exc_info=True` in `_probe_db()`) and globally in P00-S02-T004 (`RichTracebackFormatter(show_locals=False)` + extended `_REDACTED_KEYS`). RESOLVED. Full detail promoted to `orchestrator-state/memory/decisions.md` and `risk-register.md` (2026-05-10 compact). Test #9 `test_ready_db_down_does_not_leak_dsn_in_logs` is the regression guard.
- **P00-S02-T011 (2026-05-10) — Fernet master-key rotation**: Original ENCRYPTION_KEY was leaked into `orchestrator-state/tasks/ledger.jsonl` (3 lines, full 44-char key) because the developer pasted the literal in three Bash commands and the PostToolUse hook captures Bash commands verbatim. Debugger rotated the key (in-process Python, never echoed), redacted the ledger (recovered from rotation backup after a recursive-leak truncation incident, scrubbed using base64-of-base64 reconstruction so the literal never re-enters the bash log), added `.gitignore` rule for `orchestrator-state/dev-logs/*`, removed plaintext persistence in `scripts/dev-restart.profile.sh`, and re-seeded the auth bundle with the new key. RESOLVED. Side effect: 3 `ai_provider_credentials` rows in `hilopeople_dev` are now undecryptable (encrypted with old key) — they will be reseeded clean at next `./scripts/dev-restart.sh --reset`. Updated `developer/MEMORY.md` + `debugger/MEMORY.md` with the secret-hygiene-in-bash-commands lesson (allowed: Edit tool, `python3 -c '...'` heredoc, `KEY=$(...)` substitution; forbidden: `EXPORT KEY=<literal>`, `cat <<EOF` with key, `python3 -c "k='<literal>'"`). Follow-up candidate (out-of-scope, not promoted): hook-side base64 redactor in `hook_update_ledger.py` to scan recorded commands for Fernet-shape patterns and redact at write time.
- **P01-S01-T005 (2026-05-10) — test logger bypassed verbose-toggle (debugger cycle 1, RESOLVED)**: `backend/tests/integration/test_audit_logs_compliance_cols.py` used `structlog.get_logger(__name__)` at module top without calling `configure_logging()`. pytest does NOT import `app.main` (which is the production wiring point), so structlog ran with default no-level-gate config and INFO lines leaked under `ENABLE_VERBOSE_LOGGING=false`. Debugger fix (Option B, smallest blast radius): bootstrap `configure_logging()` at module import inside the test file using the same env-var read pattern as `app/main.py:40-44`. Verified: verbose=false → 0 structlog INFO lines; verbose=true → BEFORE/AFTER INFO visible; 4/4 tests still PASS; 15+4 regression tests still PASS. **Regression risk**: any future integration test that emits structlog logs from test bodies must follow the same bootstrap pattern; sibling tests today (`test_auth_migration.py`, `test_admin_ai_discover_models.py`) avoid the bug only because they don't emit structlog from tests, while `test_auth_signup.py` T8 does its own `_configured` reset around `configure_logging(verbose=True)`. Greppable enforcement candidate for future planner: `grep -rn 'structlog.get_logger' backend/tests/` should remain ≈0 in steady state — always use `from app.core.logging import get_logger` instead. Lesson archived in `debugger/MEMORY.md` under P01-S01-T005.

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

> Last updated: 2026-05-09T15:30:00Z
> Updated by: developer (P00-S02-T005) — Productive verification bundle delivery: 1-line fix to test_seed_namespaces.py (bundle_type="productive"), orphan deletion (politica_vacaciones_es.json), 104 backend tests passing (5 skipped expected), ruff+mypy clean on app/+tests/.
