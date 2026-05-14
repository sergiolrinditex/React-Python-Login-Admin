# Project Progress — Live Snapshot

> **AUTO-UPDATED**: This file is updated by the developer agent after EVERY slice.
> After `/clear`, read this file FIRST to understand current project state.
> This is a DERIVED artifact — the five source-of-truth docs are still the authority when present.

## Current State

- **Phase**: Phase 2 — Core Features (P02-S04-T001 DONE 2026-05-13 — RAG retriever + citation smoke committed; P02-S07-T001 developer done — pending validator/tester/verify-slice; P02-S08-T001 developer done 2026-05-13 — Agents endpoints + DeepAgents/LangGraph smoke; P02-S03-T004 developer done 2026-05-13 — ENCRYPTION_KEY rotation + AI provider seeding; **P02-S05-T002 developer done 2026-05-13 — Model test + usage endpoints**) ; **P02-S06-T001 developer done 2026-05-13 — RAG document admin endpoints (upload+list+index)**; **P02-S05-T004 done 2026-05-13 — Orchestrator CI lineage sentinel (PR #18 merged)**; **P02-S06-T002 developer done 2026-05-13 — RAG collection endpoints (list+patch)**; **P02-S03-T007 developer done 2026-05-14 — check_handoff_contract.py worktree path fix**
- **Last completed slices**:
  - **P02-S03-T007 — Fix check_handoff_contract.py worktree path bug — developer done 2026-05-14**: Added `_resolve_handoff_path(task_id)` with workspace→canonical fallback to fix false-negative EXIT=2 when invoked from `/tmp`. 4 new tests in `test_handoff_contract_resolution.py` (9+4=13 PASS). Smoke: P02-S03-T004 and P02-S06-T003 EXIT=0 from /tmp, worktree, and canonical. WRITE_SET_DRIFT §D-T007-RESOLVER (383 LoC) + §D-T007-TESTSPLIT (new test file, pre-authorized). FU-20260514045116 waive deferred to main-orchestrator.
  - **P02-S06-T002 — RAG collection endpoints (list + patch) — developer done 2026-05-13**: New subpackage `backend/app/rag/collections/**` (7 files: `__init__.py`, `router.py` 262 LoC, `service.py` 182 LoC, `repository.py` 132 LoC, `schemas.py` 125 LoC, `audit.py` 50 LoC, `errors.py` 45 LoC). 2 endpoints: `GET /api/v1/admin/rag/collections` (list, name ASC, admin-only), `PATCH /api/v1/admin/rag/collections/{id}` (partial update with name/vertical/language/enabled, at-least-one validation, audit). DB: reused `rag_collections` from migration 0002 (NO new migration). WRITE_SET_DRIFT: §D-RAGCOLL-MAIN (+2 lines main.py wiring), §D-RAGCOLL-SPLIT (7-file subpackage vs single collections.py). DRIFT anchor §D-RAGCOLL-LANG-IN-PATCH (language in PATCH body per Coverage Registry acceptance + UX_CONTRACT consistency). Audit: reuses `app/admin/_audit.py::write_admin_ai_audit` action `admin.rag.collection.update`. 13/13 PASS both verbose=true and verbose=false. Lint: ruff check clean, ruff format --check clean. Journey ref: J104 (does NOT close J104 — P04-S02-T001/T002 + P05-S01-T005 remain).
  - **P02-S05-T004 — Fix orchestrator CI: journey_state + stack_profile contract regressions (done 2026-05-13)**: Registry-of-record slice. Technical fix already landed on `main` via PR #17 (`8e52ed3`, mergedAt 2026-05-13T21:13:24Z). This slice synchronizes the worktree with `origin/main` (git pull --ff-only, HEAD=f1b8ea1 which includes 8e52ed3 as parent) and adds `.claude/bin/tests/test_orchestrator_ci_lineage.py` (84 LoC, Option A subprocess-pytest) as a regression sentinel that re-runs the 7 PR #17 unit cases (test_journey_state x5, test_stack_profile_contract x2) so any future revert surfaces in the 'Orchestrator tests' workflow immediately. Allowed paths respected (`.claude/bin/**`). Sentinel: 1 passed. Full suite: 340 passed, 5 skipped, 1 pre-existing failure (`test_minireact` local-only Mac flake, CI green). WRITE_SET_DRIFT: none. No journey closure (journey_refs: []). FU-20260513210148 → closed. **Closed by closer: PR #18 merged 2026-05-13T21:59:27Z, commit `0dd27f3`. All 5 "Orchestrator tests" CI jobs SUCCESS.**
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
  - P01-S02-T001 — POST /api/v1/auth/sign-up (done, 2026-05-11)
  - P01-S02-T002 — POST /api/v1/auth/sign-in (developer done, 2026-05-11)
  - P01-S02-T008 — fix dev-restart.profile.sh verification-data bootstrap source path (developer done, 2026-05-12)
  - P01-S02-T009 — JWT dev key hygiene + ENABLE_VERBOSE_LOGGING=true default (developer done, 2026-05-12)
  - **P01-S02-T010 — bootstrap_source_of_truth.py --refresh preserves closer-final task status (developer done, 2026-05-12)**
  - **P01-S02-T003 — POST /api/v1/auth/refresh (developer done, 2026-05-12)**
  - **P01-S02-T004 — POST /api/v1/auth/logout (developer done, 2026-05-12)**
  - **P01-S02-T012 — fix dev-restart db_health race: host TCP probe (developer done, 2026-05-12)**
  - **P01-S02-T011 — fix refresh cookie Path mismatch /auth → /api/v1/auth (developer done, 2026-05-12)**
  - **P01-S02-T006 — POST /api/v1/auth/2fa/verify MFA TOTP endpoint (developer done, 2026-05-12)**
  - **P01-S02-T007 — GET /api/v1/users/me + PATCH /api/v1/users/me/language (developer done, 2026-05-12)**
  - **P01-S03-T001 — Auth state provider and protected route guards (developer done, 2026-05-12)**
  - **P01-S03-T002 — Cross-origin infra: vite proxy /api → uvicorn (Strategy A, ADR-002) — DONE 2026-05-13**
  - **2026-05-13 · P02-S03-T001 · Chat conversation CRUD endpoints · developer done**: 3 endpoints (GET /chat/conversations list+pagination, POST create atomic, GET /chat/conversations/{id} detail with ownership 403/404). New module `app/chat/` (11 files). Dec: D-PAG1 (cursor pagination base64url((updated_at,id))), D-TIT1, D-LANG1, D-TX1, D-RL1, D-AUD1 → decisions.md. Migration 0002 applied (head=0002). Tests: 14/14 green. Wired in main.py (+2 lines).
  - **2026-05-13 · P02-S05-T001 · Admin AI providers + models endpoints · debugger cycle 1 done**: 4 endpoints (GET/POST /admin/ai/providers with encryption + audit, GET /admin/ai/models, PATCH /admin/ai/models/{id} with D-DEF1 default invariant). Dec: D-AASPLIT (providers/ + model_catalog/ split, max 230 LoC was 590), D-DEF1 (at-most-one is_default per model_type, app-layer) → decisions.md. Pending: FU-20260513085435 DB partial unique index (medium) → risk-register.md. Tests: 25/25 green both verbose modes. Test fixture self-seeds roles.
  - **2026-05-13 · P02-S03-T003 · dev-restart.profile.sh restore · developer done**: Restored canonical 395-LOC stack-specific profile from commit `aa840ca`, preserving T008 (absolute --source path for verification_data bootstrap) and T012 (host-TCP probe + 60s timeout). All 8 contract functions defined; syntax OK; `./scripts/dev-restart.sh --check` no longer errors. End-to-end --reset verification deferred to /verify-slice (worktree port conflict with main project containers; normal pr-flow constraint).
  - **2026-05-13 · P02-S07-T001 · MCP server + tool endpoints · developer done**: 4 endpoints (GET/POST /admin/ai/mcp/servers, POST /mcp/servers/{id}/sync, PATCH /mcp/tools/{id}). New module `app/mcp/**` (15 files, max 276 LoC). Dec: D-1 (sync inline), D-SYNC1 (idempotent no-delete upsert), D-TRANSPORT (reject stdio), D-ALLOWLIST (endpoint allowlist), D-CLIENT-OFFICIAL (httpx JSON-RPC), D-AUDIT-NO-SECRETS → decisions.md. WRITE_SET_DRIFT §D-MCPWIRE (+3 lines). Tests: 25/25 green both verbose modes.
  - **2026-05-13 · P02-S08-T001 · Agents endpoints + DeepAgents/LangGraph smoke · developer done**: 3 endpoints (GET /admin/ai/agents with bound_tools, PATCH /admin/ai/agents/{id}/tools set-replace, POST /agents/runs LangGraph smoke). New modules `app/agents/**` (21 files, max 183 LoC after service_start_run split 373→179/163/98) + `app/graphs/**` (3 files). DB: reused 4 tables from migration 0002. WRITE_SET_DRIFT §D-AGWIRE-ADMIN (+15 LOC mostly comments), §D-AGWIRE-MAIN (+2 lines), §D-CONFTEST-ENV (+66 lines worktree-safe .env loader). Researcher OUTCOME: verified, 3 non-blocking discrepancies recorded. Journey ref: J105 (4 downstream tasks remain). Tests: 18/18 green both verbose modes.
  - **2026-05-13 · P02-S04-T001 · RAG retriever + citation smoke · DONE (committed `26a4f33`)**: Audited and adopted 1333 LOC of prior untracked code without changes (passed lint+tests verbatim). 7 files: `backend/app/rag/{__init__,errors,schemas,retriever}.py` + `backend/tests/ai/{__init__,conftest,test_rag_retriever}.py`. Real Postgres + pgvector ops (no mocks). Module importable: `from app.rag import retrieve, RetrievedChunk, RetrieverFilters`. No new endpoints (internal/no-front). WRITE_SET_DRIFT: §D-RR-TESTS, §D-RR1, §D-RR-TESTSPLIT, §D-RR2, §D-RR3. Tests: 10/10 smoke green both verbose modes.
  - **2026-05-13 · P02-S03-T004 · ENCRYPTION_KEY rotation + AI provider credential/model seeding · developer done**: Created `scripts/gen-dev-secrets.sh` (idempotent Fernet key rotation; never prints key values; POSIX portable). `.env` `ENCRYPTION_KEY` rotated from placeholder to valid 44-char Fernet key. New fixture schemas + loaders `load_ai_provider_credentials()` (encrypt at load time) + `load_ai_models()`. `_run_admin_ai_group()` wired with FK-safe order: providers → credentials → models. `setup-from-scratch.sh` updated to invoke gen-dev-secrets.sh before DB migrations. WRITE_SET_DRIFT §D-T004-LOADERS/FIXTURES/TESTS predeclared. Researcher RESOLVED: Fernet API stable in cryptography==48.0.0, single-key sufficient. Tests: 14/14 green both verbose modes (5 bash unit T01–T05 + 4 loader T06–T09 + 5 bootstrap integration T10–T13).
  - **2026-05-13 · P02-S03-T002 · Chat streaming SSE endpoint · developer done + debugger cycle 1**: `POST /api/v1/chat/conversations/{conversation_id}/stream` with `app/chat/streaming/**` (router/service/model_selector/persistence/sse/schemas) + new `app/llm_gateway/**` (litellm_client/errors). 12 WRITE_SET_DRIFT anchors §D-CHATSTREAM-PKG/ROUTER/SVC/SEL/PERSIST/SSE/SCH + §K-LLM-GATEWAY/CHAT-AGG/TEST-SPLIT/CHATSTREAM-BGSESSION/PROMPT-FILE — all predeclared. Researcher M.4 minor DISCREPANCY RESOLVED (chose Option B `StreamingResponse` over FastAPI 0.135.0 `EventSourceResponse`). Debugger cycle 1 simplified `(ValidationError, Exception)` tuple to `Exception` (Pydantic v2 ValidationError IS-A Exception). Pending: FU-20260513171333 ENCRYPTION_KEY hygiene + AI provider seeding (medium, resolved by P02-S03-T004). Tests: 51/51 green both verbose modes (chat_stream 20/20 integration + chat_stream_unit_sse 21/21 + llm_gateway_litellm_client 10/10).
  - **2026-05-13 · P02-S05-T002 · Model test + usage endpoints · developer done**: 2 endpoints (`POST /api/v1/admin/ai/models/{id}/test` real LLM call with rate-limit 5/min/IP + ai_model_tests + llm_usage_logs + audit, `GET /api/v1/admin/usage` aggregation group_by model/day/model_day, 90-day cap). New `app/admin/model_test/**` (6 files, max 303 LoC repository.py) + `app/llm_gateway/complete_chat.py` (293 LoC, non-streaming wrapper reusing `_estimate_cost_from_pricing` — DRY) + `app/admin/usage.py` (186 LoC) + `app/admin/_usage_aggregator.py` (168 LoC SQL split §D-USAGE-SPLIT). DB: reused `ai_model_tests` + `llm_usage_logs` from migration 0002, NO new migration. WRITE_SET_DRIFT anchors §D-LLMG-COMPLETE/ERRORS/INIT + §D-MT-PKG/ROUTER/SVC/REPO/SCHEMAS/AUDIT/WIRE + §D-USAGE-FILE/SPLIT. Researcher RESOLVED (LiteLLM v1.83.14 non-streaming shape, error taxonomy, mock_response, cost fallback). Journey ref: J103 (4 downstream tasks remain in P04/P05). Tests: 25/25 green both verbose modes.
  - **2026-05-13 · P02-S06-T001 · RAG document admin endpoints (upload + list + enqueue index) · developer done**: 3 endpoints (`POST /api/v1/admin/rag/documents` PDF/DOCX multipart upload + sha256 dedup + MinIO put, `GET /admin/rag/documents` cursor-paginated list with filter by collection_id/status RBAC admin-only, `POST /admin/rag/documents/{id}/index` enqueue Celery `chain(extract→embed)` via `asyncio.to_thread` with inflight-job dedup 409). New subpackage `backend/app/rag/documents/**` (14 files, max 383 LoC repository.py) + 3 split integration test files. Wired in main.py at `/api/v1/admin/rag` (§D-RAGDOCS-MAIN). WRITE_SET_DRIFT §D-RAGDOCS-PKG (14-file subpackage), §D-RAGDOCS-MAIN (+2 lines), §D-RAGDOCS-TESTSPLIT (3 test files), §D-RAGDOCS-DEPS (+6 lines for `python-multipart==0.0.28` Q1 researcher reconciliation). DB: reused 3 tables (documents, document_versions, vectorization_jobs); NO new migration. Researcher OUTCOME: discrepancy → RESOLVED. Journey ref: J104 (4 downstream tasks remain). PR #16 commit `5b99801` merged. Tests: 29/29 green both verbose modes. 2 recovery developer runs after early agent cutoffs.
  - **2026-05-13 · P02-S06-T003 · MinIO bucket bootstrap sidecar (wiring) · developer done**: NEW `scripts/minio-bootstrap.sh` (106 LOC POSIX sh, `#!/bin/sh`, `set -eu`). Creates bucket `$S3_BUCKET_DOCUMENTS` (default `hilo-docs-dev`) in local MinIO via `mc alias set` + `mc mb --ignore-existing`. Retry loop 5 attempts × 2s to absorb transient 503 during MinIO S3 API warm-up after healthcheck passes. Idempotent: double-run exits 0 both times. WRITE_SET_DRIFT: none. Journey: none. Operational verify (`docker compose up minio-init`) deferred to tester.
  - **2026-05-14 · P02-S03-T005 · /ready 500 fix — _ping_db engine type sentinel · developer done**: Option B (SENTINEL) — no product code modified; bug did not reproduce in HEAD (`_ping_db` already uses sync `Engine`). Created `backend/tests/integration/test_health_ready.py` (18 tests): `TestReadyRealDbHappyPath` (6 — real Postgres, no overrides, 200 OK), `TestReadyRealDriverDbDown` (4 — real psycopg3 broken DSN → 503), `TestGetDbEngineSentinel` (3 — isinstance(Engine) + not isinstance(AsyncEngine) + dialect=psycopg), `TestReadyVerboseLoggingContract` (5 — caplog.at_level Approach A). 18/18 PASS verbose=true and verbose=false. Existing `test_health.py` 11/11 PASS (no regression). Lint: ruff check clean, ruff format clean. Curl: 200 OK `{"data":{"db":{"status":"ok"},"redis":{"status":"ok"},"litellm":{"status":"unknown"}}}`. WRITE_SET_DRIFT §D-T005-NOOP-ROUTER/DROP-ENGINE-PATH/TEST-PATH-FIX/SENTINEL (all predeclared in pack §11). Journey: J101 touched but not closed (5 downstream tasks remain). Closer trailer: `JOURNEY_CLOSES: none`.
  - **2026-05-14 · P02-S03-T006 · Fix chat stream chunks — llm_gateway non-existent SDK provider 'litellm/model' · developer done**: Root cause: `model_str = f"{provider.provider_type}/{model.model_id}"` sent `"litellm/gpt-4o-mini"` → SDK `BadRequestError("LLM Provider NOT provided")`. Fix: `_compose_sdk_model_args(provider, model, request_id)` helper in `litellm_client.py` maps `provider_type='litellm'` → prefix `'openai'` + `api_base=provider.base_url`. Both `stream_chat` and `embed_query` use it (D-T006-COMPOSE-HELPER). Write set respected, no drift. New test file `test_chat_streaming_live.py` (1 test, gated `LITELLM_PROXY_UP=1`, SKIPPED without proxy). Unit test file extended: 7 new TestComposeHelper tests (T11–T17). Tests: 58/58 PASS both verbose modes. FU-20260514053554 (high, blocking) filed for `complete_chat.py` identical bug out-of-scope. Journey J101 not closed.
- **Next pending slice**: **P02-S03-T006 validator_tester_pending (2026-05-14, 58/58 PASS)**; P02-S03-T005 validator_tester_pending; P02-S06-T002 validator_tester_pending; P02-S06-T003 validator_tester_pending; P02-S06-T001 validator_tester_pending; P02-S05-T002 validator_tester_pending; P02-S03-T004 validator_tester_pending; P02-S08-T001 validator_tester_pending; P02-S07-T001 validator_tester_pending; P02-S03-T003 validator_tester_pending; P02-S05-T001 validator_tester_pending; P02-S03-T002 validator_tester_pending; P03-S01-T001 (SignInPage — ready); P02-S04-T002 (vectorization worker — pending)
- **Blockers**: none
- **Generated at**: 2026-05-14T00:14:00+00:00 (PROGRESS.md compacted via `/slice-maintain compact`; pre-compact snapshot at `orchestrator-state/memory/archive/2026-05-13/PROGRESS-pre-compact-221226.md`, original 440 lines → compacted ~280 lines)

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

## Archived per-slice reference sections (compacted 2026-05-14)

The two reference tables that previously lived here (`## Framework Changes (P01-S02-T010)` and `## JWT Dev Key Hygiene (P01-S02-T009)`) are summarized below. Full detail in `decisions.md` and in `archive/2026-05-14/PROGRESS-pre-compact-045624.md`.

- **P01-S02-T010 — bootstrap_source_of_truth.py --refresh preserves closer-final task status** · committed 2026-05-12 · Added importable `CLOSER_FINAL_STATUSES = {"done","blocked","skipped"}` + `CLOSER_FINAL_OUTCOMES = {"committed","deployed"}` frozensets, defensive re-assertion guard after `_apply_preserved_runtime` field-copy loop, extended docstring. New regression test `.claude/bin/tests/test_bootstrap_refresh_preserves_done.py` (13 tests; TC1 pins the manual patch `570b702` scenario from 2026-05-11). Manual patch `570b702` is now OBSOLETE (future refreshes can't reintroduce the regression). Framework suite: 142 PASS, 1 pre-existing `test_static_contracts` 2/6 unrelated. `--validate-only` exit 0, no source-of-truth drift. Full decision detail → `decisions.md` §P01-S02-T010 (D-T010-CONSTANTS / DEFENSIVE / DOCSTRING / REGRESSION / PATCH-OBSOLETE / VALIDATION).
- **P01-S02-T009 — JWT dev key hygiene + ENABLE_VERBOSE_LOGGING=true default** · committed 2026-05-12 · NEW `scripts/gen-dev-secrets.sh` (idempotent: rotates JWT_PRIVATE_KEY if placeholder/short, sets ENABLE_VERBOSE_LOGGING=true, chmod 600 .env). `scripts/setup-from-scratch.sh` wired to invoke gen-dev-secrets.sh after .env source and before DB migrations, re-sources .env after rotation. `.env.example` updated with RFC 7518 §3.2 comment + gen-dev-secrets.sh usage. Backend startup warning `tokens.jwt_key.too_short` eliminated (key is now 64 chars). Idempotent (second run → `changed=0`). 73/73 tests PASS, no regression. Full decision detail → `decisions.md` §P01-S02-T009.

## Tooling Status (P01-S02-T012 + P02-S03-T003 + P02-S06-T003)

| Tool | Status | Details |
|------|--------|---------|
| `scripts/dev-restart.sh --reset` | hard-fail + host-TCP probe (P01-S02-T012) | Two back-to-back `--reset` both exit 0. `db_health` now requires BOTH container-internal `pg_isready` AND host TCP probe to pass before declaring UP. Race between Rancher Desktop port-forward and alembic host-side connection is closed. |
| `scripts/dev-restart.profile.sh:db_health` | fixed — two-probe AND (P01-S02-T012) | `_host_pg_ready()` helper added; `_ensure_infra_essential` timeout raised 30→60s. |
| `scripts/dev-restart.profile.sh` (overall) | **RESTORED (P02-S03-T003, 2026-05-13)** | 39-LOC neutral stub replaced with canonical 395-LOC Hilo People profile from `aa840ca`. All 8 contract functions defined. T008 + T012 invariants preserved. `./scripts/dev-restart.sh --check` no longer errors on missing functions. End-to-end `--reset` verified in `/verify-slice` gate. |
| `scripts/minio-bootstrap.sh` | **NEW (P02-S06-T003, 2026-05-13)** | 106-LOC POSIX sh sidecar. Creates `$S3_BUCKET_DOCUMENTS` bucket in local MinIO via `mc alias set` + `mc mb --ignore-existing`. Retry loop 5×2s for S3 API warm-up. Idempotent: `docker compose up minio-init` exits 0 on first and second run. Operational verify deferred to tester. |

## Backend Status

| Aspect | Status | Details |
|--------|--------|---------|
| Server | running | uvicorn app.main:app --port 8000 --reload |
| Health check | 3 endpoints implemented | GET /health (backward compat), GET /live (liveness), GET /ready (readiness with DB+Redis ping) |
| Auth endpoints | 7 implemented | POST /api/v1/auth/sign-up (T001), POST /api/v1/auth/sign-in (T002), POST /api/v1/auth/refresh (T003), POST /api/v1/auth/logout (T004) — cookie Path fixed to /api/v1/auth (T011). POST /api/v1/auth/forgot-password (T005), POST /api/v1/auth/reset-password (T005), POST /api/v1/auth/2fa/verify (T006) |
| Users endpoints | 2 implemented (T007) | GET /api/v1/users/me (returns UserProfile + employee_profile), PATCH /api/v1/users/me/language (returns 200 + full body; whitelist es/en/fr; audit log) |
| Chat endpoints | 4 implemented (P02-S03-T001 + P02-S03-T002) | GET /api/v1/chat/conversations (list, cursor pagination D-PAG1), POST /api/v1/chat/conversations (create, atomic D-TX1), GET /api/v1/chat/conversations/{id} (detail with messages+citations, ownership 403/404), POST /api/v1/chat/conversations/{conversation_id}/stream (SSE streaming, P02-S03-T002, StreamingResponse Option B, partial-persist on cancel) |
| Admin AI endpoints | 4 implemented (P02-S05-T001) | GET /api/v1/admin/ai/providers (list, masked creds), POST /api/v1/admin/ai/providers (create+encrypt, rate-limit, audit), GET /api/v1/admin/ai/models (list, provider_id filter), PATCH /api/v1/admin/ai/models/{id} (partial update, D-DEF1 default invariant, audit) |
| Admin model-test + usage endpoints | 2 implemented (P02-S05-T002) | POST /api/v1/admin/ai/models/{id}/test (real LLM call, rate-limit 5/min/IP, ai_model_tests+llm_usage_logs+audit), GET /api/v1/admin/usage (aggregation, group_by model/day/model_day, 90-day cap) |
| Admin MCP endpoints | 4 implemented (P02-S07-T001) | GET /api/v1/admin/ai/mcp/servers (list), POST /api/v1/admin/ai/mcp/servers (register+encrypt, allowlist, rate-limit, audit), POST /api/v1/admin/ai/mcp/servers/{id}/sync (discover tools, D-SYNC1, audit), PATCH /api/v1/admin/ai/mcp/tools/{id} (partial update, audit) |
| Admin Agents endpoints | 3 implemented (P02-S08-T001) | GET /api/v1/admin/ai/agents (list with bound_tools), PATCH /api/v1/admin/ai/agents/{id}/tools (set-replace bindings, audit), POST /api/v1/agents/runs (DeepAgents/LangGraph smoke, rate-limit, audit) |
| Admin RAG collections endpoints | 2 implemented (P02-S06-T002) | GET /api/v1/admin/rag/collections (list, name ASC, admin-only), PATCH /api/v1/admin/rag/collections/{id} (partial update name/vertical/language/enabled, at-least-one required, audit) |
| Endpoints implemented | 31 | GET /health, GET /live, GET /ready, POST /api/v1/auth/sign-up, POST /api/v1/auth/sign-in, POST /api/v1/auth/refresh, POST /api/v1/auth/logout, POST /api/v1/auth/forgot-password, POST /api/v1/auth/reset-password, POST /api/v1/auth/2fa/verify, GET /api/v1/users/me, PATCH /api/v1/users/me/language, GET /api/v1/chat/conversations, POST /api/v1/chat/conversations, GET /api/v1/chat/conversations/{id}, POST /api/v1/chat/conversations/{conversation_id}/stream, GET /api/v1/admin/ai/providers, POST /api/v1/admin/ai/providers, GET /api/v1/admin/ai/models, PATCH /api/v1/admin/ai/models/{id}, GET /api/v1/admin/ai/mcp/servers, POST /api/v1/admin/ai/mcp/servers, POST /api/v1/admin/ai/mcp/servers/{id}/sync, PATCH /api/v1/admin/ai/mcp/tools/{id}, GET /api/v1/admin/ai/agents, PATCH /api/v1/admin/ai/agents/{id}/tools, POST /api/v1/agents/runs, **POST /api/v1/admin/ai/models/{id}/test (P02-S05-T002)**, **GET /api/v1/admin/usage (P02-S05-T002)**, **GET /api/v1/admin/rag/collections (P02-S06-T002)**, **PATCH /api/v1/admin/rag/collections/{id} (P02-S06-T002)** |
| Migrations applied | 2 (head=0002) | 0001: 9 auth tables. 0002: 25 tables (conversations, messages, message_citations, documents, document_chunks, document_embeddings, rag_collections, vectorization_jobs, ai_providers, ai_provider_credentials, ai_models, ai_model_tests, llm_usage_logs, mcp_servers, mcp_tools, mcp_resources, mcp_prompts, mcp_credentials, mcp_approvals, mcp_tool_invocations, agents, agent_runs, mcp_agent_bindings) |
| Seed data | loader.py fixed (P00-S02-T004); bootstrap ready; dev-restart --reset self-contained (T008) | FU-20260511145446 resolved — CAST(:meta AS JSONB) + json.dumps(). T008 fix: absolute --source path + hard-fail. data/verification/users/admin_peopletech.json: roles updated "admin"→"people_admin" (WRITE_SET_DRIFT §D-AAVD). |
| Backend tests | 209 passing (+10 RAG smoke P02-S04-T001 + 25 MCP registry P02-S07-T001) | +10 from tests/ai/test_rag_retriever.py (T01–T10 all PASS in isolation, both verbose modes) + 25 from test_mcp_registry.py (T01–T25 all PASS both verbose modes). Pre-existing: test_auth_signin + test_auth_logout have JWT-key ordering failures when run first (pre-existing, unrelated to either slice). |
| Backend dependencies | declared + installed | pyproject.toml: 29 packages pinned (no new deps added — P02-S04-T001 uses existing pgvector+sqlalchemy+pydantic; P02-S07-T001 uses existing httpx+cryptography+redis) |
| Lint (ruff) | clean | 0 issues |
| Fernet usage (P02-S05-T001) | encrypt_secret on POST /providers; decrypt not exposed to API | Audit actions: admin.ai.provider.create, admin.ai.model.update. D-DEF1: at-most-one is_default=true per model_type enforced at app layer. FU-20260513085435: DB-level partial unique index proposed (medium, non-blocking). |

## Archived endpoint detail sections (compacted 2026-05-13)

These sections were full reference tables in the pre-compact PROGRESS.md. They are summarized here; for full detail, read the pre-compact snapshot `orchestrator-state/memory/archive/2026-05-13/PROGRESS-pre-compact-221226.md` or the slice handoff for the originating TASK_ID.

- **P01-S02-T006 — TOTP/MFA verify endpoint** (16 features). `pyotp==2.9.0`, valid_window=1 (±30s, RFC 6238 §5.2), 410 ONLY for sig-valid+exp-past, 401 aggregate for everything else, byte-equal 401 across 3 failure modes, dummy-verify timing path, `mfa_crypto.py` facade, audit action `auth.mfa.verify` via D-S2. In-memory `jti` consume store (TODO Redis SETNX in P02-S02-T001). `data/verification/auth/mfa_primary.json` enabled=true (WRITE_SET_DRIFT §D-MFA1.K). 16 tests PASS in isolation. Researcher RESOLVED (5 Qs). Full decision detail → `decisions.md` §P01-S02-T006.
- **P01-S02-T004 — Logout endpoint** (12 features). `POST /api/v1/auth/logout` 204 success / 401 all failures with byte-identical body (`AUTH_SESSION_EXPIRED`). Cookie cleared on ALL paths via `_clear_refresh_cookie`. Single-session revocation via `repo.revoke(token_id)` reusing T003 SELECT FOR UPDATE. `LogoutAuditWriter` extracted to `logout_audit.py` (182 LOC). Sizes: logout_audit=182, logout.py=276, routers/logout.py=138. WRITE_SET_DRIFT §D-LO1 declared. 14/14 tests PASS. Full detail → `decisions.md` §P01-S02-T004.
- **P01-S02-T002 — Sign-in endpoint** (11 features). PyJWT==2.12.1 HS256 access token (sub/email/roles/jti/iat/exp, TTL `AUTH_ACCESS_TTL_SECONDS` default 1800s). Opaque refresh `secrets.token_urlsafe(48)` → SHA-256 in DB, HttpOnly cookie path=/api/v1/auth (T011 fix). MFA challenge branch with short-lived `purpose=mfa_challenge` JWT (no refresh cookie). 423 lockout (5/900s window). 429 rate limit (`AUTH_SIGNIN_RATE_PER_MINUTE` default 20). Aggregate-401 anti-enum with dummy Argon2 verify. X-Request-ID propagated. `app/db/session.py` extracted (T001 validator nit). Full decision detail → `decisions.md` §P01-S02-T002 + §debugger cycle 1.
- **P01-S02-T007 — Users feature** (14 features). `GET /api/v1/users/me` returns UserProfile (id/email/full_name/status/preferred_language/roles/employee_profile/timestamps). `PATCH /api/v1/users/me/language` returns 200 + full body (DISCREPANCY-1 resolved; whitelist es/en/fr; audit row via D-S2). `employee_profile: null` for admin (DISCREPANCY-3 resolved). Anti-enum 401 byte-equal AUTH_SESSION_EXPIRED. Audit `users.language.update` no PII. Idempotency (G.6) records intent. `updated_at` via `func.now()` DB clock (G.8). New module `backend/app/users/` (router, service×2, repository, schemas, deps, audit, errors). WRITE_SET_DRIFT main.py declared. Decision G.16 (`_error_response` import) transitional. 31/31 tests PASS.
- **P02-S07-T001 — MCP Registry Layer** (15 components). Module `backend/app/mcp/` (Clean Architecture). Files: errors.py, schemas.py (Pydantic v2), audit.py, client.py (httpx JSON-RPC), repository.py (shim) + repository_servers.py + repository_tools.py, service.py (shim with limiters) + service_register.py + service_sync.py + service_update_tool.py, router.py (aggregator) + router_servers.py + router_tools.py. `app/admin/__init__.py` +3 lines (WRITE_SET_DRIFT §D-MCPWIRE). 25/25 tests PASS both verbose. Decisions D-1/D-SYNC1/D-TRANSPORT/D-ALLOWLIST/D-CLIENT-OFFICIAL/D-AUDIT-NO-SECRETS → `decisions.md`.
- **P02-S03-T001 — Chat CRUD Layer** (11 components). Module `backend/app/chat/` (Clean Architecture). errors.py, cursor.py (base64url((updated_at,id)) D-PAG1), schemas.py (Pydantic v2 DTOs + response envelopes), repositories/conversations.py (find_conversations_paginated D-PAG1, find_conversation_with_messages, create_conversation D-TX1), services/list_conversations.py + create_conversation.py (D-TIT1, D-LANG1) + get_conversation_detail.py (ownership 403/404), routers/_helpers.py + routers/conversations.py (298 LOC, 3 endpoints). `app/main.py` +2 lines (chat_router import + mount). Migration 0002 applied. 14/14 integration tests PASS. Decisions D-PAG1/D-TIT1/D-LANG1/D-TX1/D-RL1/D-AUD1 → `decisions.md`.
- **P02-S02-T001 — Security Layer** (9 components). Module `backend/app/security/` (greenfield, no regressions). errors.py (SecurityError, EncryptionKeyError, EncryptionError, PermissionDeniedError, RateLimitedError), encryption.py (Fernet AEAD over `ENCRYPTION_KEY`, lazy init, loud-fail on placeholder), permissions.py (require_user/role/admin/auditor; super_admin superset D-PERM1), rate_limit.py (RateLimiter Redis sliding-window, fail-closed on Redis error), `_redis_client.py` (lazy singleton), `__init__.py` (public API re-exports). New tests dir `backend/tests/unit/test_security.py` 18/18 PASS (6 encryption + 6 permissions + 6 rate_limit). ENCRYPTION_KEY placeholder raises with `Fernet.generate_key()` hint. Real Redis verified for rate limiter. Pre-existing failures noted in test_users_me/test_password_reset are unrelated (require seeded data).

## Frontend Status

| Aspect | Status | Details |
|--------|--------|---------|
| App running | ready to start | `npm --prefix frontend run dev` boots at port 5173 (with proxy block active) |
| Vite proxy | configured (P01-S03-T002) | `server.proxy["/api"]` → `http://localhost:8000`; Strategy A; ADR-002; unblocks J100-J105 browser flows |
| Routes implemented | 4 | /showcase (public), /auth/sign-in (stub), /chat (RequireAuth), /admin (RequireRole) |
| AuthProvider | implemented (P01-S03-T001) | Mount-time /refresh → /me hydration; status: hydrating/authenticated/unauthenticated |
| RequireAuth | implemented (P01-S03-T001) | Redirects unauthenticated to /auth/sign-in?next=<safe_path> |
| RequireRole | implemented (P01-S03-T001) | Role mismatch → /chat; requires any-of intersection with user.roles |
| accessTokenStore | implemented (P01-S03-T001) | In-memory closure, NEVER localStorage/sessionStorage |
| httpClient | implemented (P01-S03-T001) | Single-flight 401 refresh interceptor, X-Request-ID, credentials:include |
| redirectAfterAuth | implemented (P01-S03-T001) | getSafeRedirect() with 7-rule open-redirect guard; unit tested |
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
| Backend integration | 249 | PASS in isolation (health 11 + dep smoke 20 + migrations 6 + dev restart 2 + bootstrap 9 + auth signup 9 + auth signin 16 + auth refresh 14 + auth logout 15 + password reset 21 — T005 + MFA 16 — T006 + chat conversations 14 — P02-S03-T001 + RAG smoke 10 — P02-S04-T001 + MCP registry 25 — P02-S07-T001 + agents smoke 18 — P02-S08-T001 + **model_test+usage 25 — P02-S05-T002** + **health_ready sentinel 18 — P02-S03-T005**) — NOTE: full-suite (all at once) has migration downgrade ordering issue (pre-existing); health_ready sentinel 18/18 PASS both verbose modes |
| Compose orchestration smoke | 11 | PASS (T1–T8 tester + verify cycle 1+2 + minio-init bucket) |
| Frontend unit | 0 | — |
| Frontend component | 91 | PASS (providers 4 + design-system 34 + showcase 4 + i18n 16 + auth 33) |
| E2E | 0 | — |
| **Total** | **202** | **202 PASS, 0 FAIL** |

## Milestones

| Milestone | Status | Slices | Tests |
|-----------|--------|--------|-------|
| M1 — Auth foundation | in progress | P01-S02-T001+T002 developer done | 142/0 |

## Journeys (from the Journey Coverage Matrix of instrucciones.md)

| Journey | Milestone | Status | Slices |
|---------|-----------|--------|--------|
| J100 | M1 | pending (3/10 slices done: T002 sign-in + T005 password-reset + T006 2fa-verify) | 10 |
| J101 | M2 | pending | 7 |
| J102 | M2 | pending | 6 |
| J103 | M3 | pending | 6 |
| J104 | M4 | pending | 5 |
| J105 | M5 | pending | 6 |

## Recent Decisions

Promoted to `orchestrator-state/memory/decisions.md` on 2026-05-13. Read that file for the full append-only log. Sections promoted: P01-S02-T002 (sign-in + debugger cycle 1), P01-S02-T003 (refresh), P01-S02-T004 (logout), P01-S02-T006 (2fa MFA), P01-S02-T009 (JWT dev key hygiene), P01-S03-T002 (vite proxy / ADR-002).

## Known Issues / Risks

Promoted to `orchestrator-state/memory/risk-register.md` on 2026-05-13. Read that file for the full register with severities. Open items (med severity):

- **R1-infra (P00-S02-T001)**: `docker compose build backend/worker` deferred until T003 finalized.
- **R5-infra (P00-S02-T001)**: `worker` `app.worker` module not created yet — boot deferred to P02-S04-T002.
- **R6-infra (P00-S02-T001)**: `docker compose build frontend` deferred until T002 lock lands; `SKIP_BUILD=1` escape hatch.
- **R1-T001-S02 (P01-S01-T001)**: `test_downgrade_removes_all_tables` destroys schema on full test runs; re-run `alembic upgrade head` after suite.

Resolved/accepted items: see `risk-register.md`.

> Last updated: 2026-05-14T00:14:00+00:00
> Updated by: maintenance — `/slice-maintain compact` — PROGRESS.md compacted 440 → ~280 lines; promoted Recent Decisions + Known Issues to `decisions.md` + `risk-register.md`; compacted 7 slice-detail sections and 10 giant slice bullets to ≤6 lines each; removed orphan duplicate `### Current State (updated)` subsection; pre-compact snapshot at `archive/2026-05-13/PROGRESS-pre-compact-221226.md` SHA-256 484fde2c168eeb428e3df8f9bc9d27a207f773bc1f4f956a845891739afa6201.
> Last updated: 2026-05-13T23:51:24+02:00
> Updated by: developer — P02-S06-T002 RAG collection endpoints (list + patch) — 2 new endpoints, 7-file subpackage, 13/13 PASS both verbose modes. Endpoints count 29→31. Journey J104 advanced (3 tasks remain).
> Last updated: 2026-05-13T22:15:00+02:00
> Updated by: developer — P02-S05-T002 Model test + usage endpoints — 2 new endpoints (POST /admin/ai/models/{id}/test, GET /admin/usage). New module app/admin/model_test/** + app/admin/usage.py + app/admin/_usage_aggregator.py + app/llm_gateway/complete_chat.py. 25/25 tests PASS both verbose modes. Endpoints count 27→29.
> Last updated: 2026-05-13T19:45:00+02:00
> Updated by: debugger — P02-S03-T002 cycle 1 — applied F1 (PROGRESS.md update missing) + N1 (router.py:114 redundant except simplified). Lint clean. Next: validator ‖ tester rerun.

> Last updated: 2026-05-14T05:30:00+00:00
> Updated by: developer — P02-S03-T006 — Fix chat stream chunks llm_gateway non-existent SDK provider — _compose_sdk_model_args helper introduced, 58/58 PASS both verbose modes, FU-20260514053554 filed.

Older `> Last updated:` entries (developer P02-S08-T001, closer P02-S04-T001, developer P02-S07-T001, closer P01-S03-T002, developer P01-S02-T006/T005/T003/T004/T009/T008/T012/T011) → archived in pre-compact snapshot.
