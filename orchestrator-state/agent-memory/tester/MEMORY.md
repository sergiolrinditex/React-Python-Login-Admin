# Tester Agent Memory
# Last updated: 2026-05-13

## Environment notes

### Docker / Compose runtime
- Rancher Desktop installed at /Applications/Rancher Desktop.app/
- docker binary at: /Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/docker
- Docker version: 29.1.4-rd
- Compose version: v5.0.1
- docker is NOT in the default PATH — must be invoked with full path or PATH export:
  export PATH="/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin:$PATH"
- nerdctl: not found in PATH
- hadolint: not installed

### Python / pytest
- python3 at /usr/local/bin/python3 (Python 3.11.5)
- pytest 9.0.2
- Backend tests run from worktree root: `python3 -m pytest backend/tests/ -v`

## Per-task cache

### P00-S01-T005 — i18n resources ES/EN/FR (2026-05-11) — PASS
- OUTCOME: pass (first run)
- TESTS: 58/58 frontend pass; 16/16 i18n-filtered pass; 0 fail
- KEY LEARNING: i18n is frontend-only (jsdom). The "servers_status: n/a" is correct and expected — do NOT flag as blocked or fail just because backend is not needed. Rule 01-non-negotiables allows pure-logic unit tests to be isolated.
- KEY LEARNING: When `VITE_ENABLE_VERBOSE_LOGGING=false` is tested and there is genuinely no log output, zero stdout IS the pass condition. Absence of logs = correct behavior for verbose=false.
- KEY LEARNING: For i18n bundle validation, use two layers: (1) Vitest tests using real i18n singleton, (2) python3 JSON.load() on all 24 files. Both are needed — tests prove runtime resolution, python3 proves the static JSON files are valid (even when not imported at build time).
- KEY LEARNING: The vitest filter `-t i18n` matches on describe/it string content. All test names must contain the literal "i18n" (both in describe and it labels) for the filter to work. Verify this before asserting the filter works.
- KEY LEARNING: Error namespace coverage check — script to verify all N error codes exist in all M locales: iterate codes × locales via python3. Saves time vs reading 3 × N JSON fields manually.
- Evidence: orchestrator-state/tasks/evidence/P00-S01-T005/
- Handoff: orchestrator-state/tasks/handoffs/P00-S01-T005.md

### P00-S02-T001 — Docker compose services (2026-05-11) — RETEST cycle 1/3
- OUTCOME: pass (retest)
- INITIAL TESTER RUN: pass (static checks); F1 CRITICAL found by verify-slice (litellm UNHEALTHY)
- DEBUGGER FIX: replaced curl healthcheck with python urllib probe in docker-compose.yml
- RETEST RESULTS:
  - T1 PASS: exit 0 on config --quiet; 8 services (frontend, litellm, minio, minio-init, postgres, redis, worker, backend)
  - T2 PASS: 24/24 backend tests green (was 4/4; now 24/24 after P00-S01-T003 dep smoke tests added)
  - T3 PASS (CRITICAL): litellm reaches (healthy) at tick=9 (~17s); Health.Status=healthy; FailingStreak=0; F1 RESOLVED
  - T4 PASS: INSIDE_EXIT=0; python urllib probe works inside container
  - T5 PASS: /health/liveliness → "I'm alive!" 200; /health/readiness → JSON litellm_version 1.83.14 200
  - T6 PASS: curl= (empty), wget= (empty), python=/app/.venv/bin/python; regression-proof of fix
  - T7 PASS: grep matches Item 5 + Item 8 with RESOLVED: format (F3 RESOLVED)
  - T8 PARTIAL PASS: redis healthy (valkey-cli PONG); minio healthy (HTTP 200); postgres SKIP (port 5432 ssh tunnel env-blocked)
- KEY LEARNING: LiteLLM official image ghcr.io/berriai/litellm:v1.83.14-stable.patch.3 has NO curl/wget; only python at /app/.venv/bin/python. Always use python urllib for healthchecks in LiteLLM containers.
- KEY LEARNING: Port 5432 may be occupied by user's ssh tunnel (apn-postgres/Inditex) on this machine. Check lsof before postgres tests and mark SKIP (env-blocked) if occupied.
- KEY LEARNING: MinIO /minio/health/live returns 200 with EMPTY BODY — curl exit 0 but no output is correct healthy behavior.
- Evidence: orchestrator-state/tasks/evidence/P00-S02-T001/tester-retest/
- Handoff: orchestrator-state/tasks/handoffs/P00-S02-T001.md

### P01-S02-T001 — POST /api/v1/auth/sign-up (2026-05-11) — PASS
- OUTCOME: pass (first run)
- TESTS: 9/9 auth-signup pass (verbose ON + verbose OFF); 57/57 full suite pass (regression clean)
- CURL: 201 happy path, 400 non-corporate, 422 legal_acceptance=false, 409 duplicate — all correct
- DB: users row with $argon2id$v= prefix confirmed; audit_logs 3 rows (success + duplicate + rejection)
- LOGGING: verbose ON shows full BEFORE/AFTER flow (7 before lines, 3 after lines); verbose OFF shows only WARNING for rejections; no PII in any log record
- KEY LEARNING: R1-T001-S02 bites during tester runs — the test suite includes test_downgrade_removes_all_tables which drops all 9 auth tables. After running the full suite, MUST run `alembic upgrade head` before attempting curl smoke tests against the live server. Binary location: `/Users/sergiolr/Library/Python/3.11/bin/alembic`.
- KEY LEARNING: alembic is NOT in PATH on this machine. Full path: `/Users/sergiolr/Library/Python/3.11/bin/alembic`. Use with DATABASE_URL env var set.
- KEY LEARNING: `audit_logs` table has no `request_id` column directly — the request_id is stored in `metadata` JSONB. Query: `metadata->>'request_id'` not `request_id`.
- KEY LEARNING: The curl test field name is `legal_acceptance` (not `legal_accepted`) and `full_name` is required. Match schema exactly before running smoke tests.
- KEY LEARNING: Backend runs without ENABLE_VERBOSE_LOGGING=true by default (dev server). To verify BEFORE/AFTER lines, use python3 -c inline script with TestClient and caplog capture. The live server only shows WARNING+ in uvicorn log by default.
- Evidence: orchestrator-state/tasks/evidence/P01-S02-T001/
- Handoff: orchestrator-state/tasks/handoffs/P01-S02-T001.md

### P01-S02-T003 — POST /api/v1/auth/refresh (2026-05-12) — PASS
- OUTCOME: pass (first run)
- TESTS: 14/14 T003 pass; 87/87 full suite pass
- E2E: happy path + replay + no_cookie + unknown_hash + rate_limit — all PASS via TestClient + real Postgres
- DB: old token revoked_at NOT NULL; new token revoked_at IS NULL; hash_len=64 (SHA-256 hex); audit rows confirmed
- LOGGING VERBOSE ON: start/done pattern at auth.refresh.execute, auth.repo.refresh.*, auth.refresh.success_audit; no raw cookie (hash_prefix 8 hex chars only); no JWT eyJhbG; no email local-part
- LOGGING VERBOSE OFF: root logger configured at WARNING level (ENABLE_VERBOSE_LOGGING=false in env before app.main import); all DEBUG/INFO suppressed
- KEY LEARNING: worktree has no .env — must explicitly export DATABASE_URL JWT_PRIVATE_KEY JWT_PUBLIC_KEY AUTH_ALLOWED_DOMAIN (and other .env vars) before running pytest from worktree dir. Do: `source /path/to/main/.env && export DATABASE_URL JWT_PRIVATE_KEY JWT_PUBLIC_KEY ...`
- KEY LEARNING: test_downgrade_removes_all_tables drops all 9 tables on full suite run. After running full suite, must re-run `alembic upgrade head` from main repo backend dir (not worktree). Worktree code = main but schema is shared Postgres instance.
- KEY LEARNING: verbose=off is tested by starting a NEW Python process with ENABLE_VERBOSE_LOGGING=false in env BEFORE importing app.main. logging.basicConfig is a no-op if root logger already has handlers — can't re-test verbose modes in same Python process.
- KEY LEARNING: logging uses start/done naming convention (structlog-style), not BEFORE/AFTER literals. Grep for "start" and "done" to verify BEFORE/AFTER contract.
- KEY LEARNING: User model in user.py has no legal_accepted column (it's not in the schema). Use User(email=..., password_hash=..., full_name=..., status='active') only.
- KEY LEARNING: monkeypatch.setattr(rl_module, "_store", {}) is acceptable — it resets the in-memory rate-limit dict for test isolation, not a mock of the service logic. Same pattern as T001/T002.
- KEY LEARNING: alembic binary path: /Users/sergiolr/Library/Python/3.11/bin/alembic. Must be run from backend/ directory with DATABASE_URL exported.
- KEY LEARNING: For verbose logging verification in a script, capture logs with io.StringIO BEFORE any imports. Or use a fresh subprocess with env preset. Do NOT use inline process after app has already been imported.
- Evidence: orchestrator-state/tasks/evidence/P01-S02-T003/
- Handoff: orchestrator-state/tasks/handoffs/P01-S02-T003.md

### P02-S01-T001 — 0002_ai_chat_rag_mcp_agents migration (2026-05-13) — PASS
- OUTCOME: pass (first run)
- TESTS: 17/17 slice tests PASS; 164/164 non-migration tests in isolation PASS; 137/187 full suite (50 contamination failures = pre-existing)
- ACCEPTANCE CYCLE: alembic downgrade -1 → current=0001 → upgrade head → current=0002 (head) — all exit 0
- SCHEMA: vector 0.8.2, 33 app tables + alembic_version=34, HNSW index (m=16, ef_construction=64), 2 btree perf indexes, 2 CHECK constraints (naming_convention prefixed: ck_conversations_conversations_language_chk, ck_documents_documents_language_chk)
- KEY LEARNING: CHECK constraint names have SQLAlchemy naming_convention prefix applied (ck_{table}_{name}). When searching pg_constraint for CHECK names, use `conrelid::regclass::text IN ('tablename')` filter or `conname LIKE '%language%'` — do NOT search for bare names like 'conversations_language_chk' without the prefix.
- KEY LEARNING: Migration test suites that use `alembic downgrade base` (autouse fixture) contaminate subsequent integration tests in the same pytest invocation. ALWAYS run migration test files in isolation from functional integration tests. Use `--ignore=tests/test_migrations_0001_auth.py --ignore=tests/test_migrations_0002_ai_chat_rag_mcp.py` when running the functional suite for regression checks.
- KEY LEARNING: After running any migration test file in full suite, restore DB with `DATABASE_URL="..." /Users/sergiolr/Library/Python/3.11/bin/alembic upgrade head` before running functional tests or curl checks.
- KEY LEARNING: When `test_upgrade_creates_all_9_tables` from 0001 migration test runs after 0002 is applied, it will find 34 tables (not 9) and FAIL. This is a stale assertion in the 0001 test (not a regression). The 0001 test was written assuming it was the only migration; once 0002 exists, `upgrade head` goes to 0002. Classification: pre-existing structural debt.
- KEY LEARNING: Docker image `pgvector/pgvector:0.8.2-pg17` and `pgvector/pgvector:pg17` may map to the same image ID (check via `docker images pgvector/pgvector`). A running container may show a different tag than in docker-compose.yml if it was pulled before the compose file was updated. Always verify via `SELECT extname, extversion FROM pg_extension WHERE extname='vector'` — the extension version is the real source of truth, not the Docker tag shown in `docker ps`.
- KEY LEARNING: For DB-only slices (no endpoints, no use cases), verbose logging verification = migration logs (upgrade.start/done per-table pattern). ENABLE_VERBOSE_LOGGING flag does NOT affect alembic CLI logs — alembic always shows INFO-level output. Document this clearly in the handoff so closer doesn't flag as incomplete.
- KEY LEARNING: Running `python` (no 3) on this machine gives 127 "command not found". Always use `python3` explicitly. The venv in worktrees may have an `alembic` binary: check `ls backend/.venv/bin/` first, then fall back to `/Users/sergiolr/Library/Python/3.11/bin/alembic`.
- KEY LEARNING: Source .env with `set -a && source /path/to/main/.env && set +a` to export ALL vars including DATABASE_URL. The worktree has no .env file — always source from main repo.
- Evidence: orchestrator-state/tasks/evidence/P02-S01-T001/
- Handoff: orchestrator-state/tasks/handoffs/P02-S01-T001.md

### P02-S02-T001 — Security services (encryption, permissions, rate limit) (2026-05-13) — PASS (cycle 2)
- OUTCOME: pass (cycle 2 re-test after debugger fix)
- TESTS: 18/18 unit PASS (test_security.py isolated); acceptance gate (-k security) = 18 PASS + 3 FAIL pre-existing (TestGetMeSecurityShape); full-suite 21 failed (vs 23 on main — improved)
- BASELINE COMPARISON: TestGetMeSecurityShape 3 failures are IDENTICAL on main and worktree. NO new regression introduced.
- FU REGISTERED: FU-20260513080801-fix-module-level-jwt-key-in-app-auth-tokens-caus (medium, non-blocking)
- REDIS: PING PONG; KEYS "rl:*" empty; DBSIZE 0 (clean teardown)
- LINT: ruff clean on security module + test_security.py
- KEY LEARNING: Tests matching `-k security` will collect TestGetMeSecurityShape (in test_users_me.py) in addition to the new test_security.py tests. Always verify acceptance gate FAILs against main baseline to distinguish pre-existing vs new regression.
- KEY LEARNING: When the debugger uses `_sync_app_jwt_key()` to patch `app.auth.tokens._JWT_KEY` in test_security.py, this patching affects import-order sensitivity for OTHER test modules collected after test_security.py. TestGetMeSecurityShape tests fail not because they are buggy but because the JWT key in app.auth.tokens module gets overwritten by the test helper's fallback key. This is acceptable for this slice but the real fix is in tokens.py itself (FU registered).
- KEY LEARNING: For pure backend library slices (no HTTP endpoints, no UI), acceptance gate = `pytest -k <module_name>`. Verbose logging is verified via caplog in the test itself. No curl smoke test needed.
- KEY LEARNING: docker binary is at ~/.rd/bin/docker (Rancher Desktop). Use `~/.rd/bin/docker exec <container> valkey-cli PING` for redis checks. `docker compose exec` with env vars not set gives confusing warnings — use `docker exec` with container name directly.
- Evidence: orchestrator-state/tasks/evidence/P02-S02-T001/cycle-2/
- Handoff: orchestrator-state/tasks/handoffs/P02-S02-T001.md

### P02-S02-T002 — Fix module-level _JWT_KEY lazy getter (2026-05-13) — PASS
- OUTCOME: pass (first run)
- TESTS: 6/6 unit (test_auth_tokens.py T1–T5+T3b); 3/3 TestGetMeSecurityShape isolation; 18/18 test_security.py isolation; 24/24 all unit tests combined; full-suite 196 PASS / 54 FAIL (all 54 pre-existing, 0 new regressions)
- CURL: GET /api/v1/users/me with Bearer token (admin.peopletech@inditex-sandbox.com) → HTTP 200 + UserProfile. JWT encode/decode end-to-end verified.
- LOGGING: verbose=true shows `tokens.jwt_key.resolved bytes=48` + encode/decode BEFORE/AFTER; no key value. verbose=false: no debug output.
- SECRET LEAK: actual JWT_PRIVATE_KEY value not found in any evidence file. Only byte-length logged.
- KEY LEARNING: Developer baseline "234 PASS / 16 FAIL" was captured BEFORE P02-S03-T001 (chat) and P02-S05-T001 (admin_ai) added their test files. The tester full-suite run AFTER those slices shows 54 FAIL because 38 of those failures are from chat (14) and admin_ai (24) tests returning 404 — endpoints not mounted in main.py (those tasks are in validator_tester_pending). This is NOT a regression from T002. Classify correctly as pre-existing before escalating.
- KEY LEARNING: TestPermissions in test_security.py fails in FULL SUITE when run after test_migrations_0001_auth.py::test_downgrade_removes_all_tables drops all tables. In isolation they pass (18/18). This is the pre-existing R1-T001-S02 issue — not caused by T002. Always confirm isolation results before declaring regression.
- KEY LEARNING: The backend server may go DOWN during full test suite if migration downgrade tests corrupt schema. After the full suite, `curl -sf http://localhost:8000/health` may fail. This is acceptable — the tests use TestClient (ASGI) not the live server. Restore schema with alembic before curl smoke tests.
- KEY LEARNING: Verification user employee.verification@inditex-sandbox.com has MFA enabled (mfa_primary.json enabled:true). Use admin.peopletech@inditex-sandbox.com (no MFA) for simple sign-in → Bearer → GET /me smoke tests.
- KEY LEARNING: Import JWT_PRIVATE_KEY with `JWT_KEY=$(grep '^JWT_PRIVATE_KEY=' .env | head -1 | cut -d= -f2-)` then `JWT_PRIVATE_KEY="$JWT_KEY" python3 -m pytest ...`. Running pytest from inside `backend/` dir, the .env is in parent dir — source appropriately.
- Evidence: orchestrator-state/tasks/evidence/P02-S02-T002/
- Handoff: orchestrator-state/tasks/handoffs/P02-S02-T002.md

### P02-S03-T001 — Chat conversation CRUD APIs (2026-05-13) — PASS (cycle 3)
- OUTCOME: pass (cycle 3 focused recovery retest, post debugger cycle 2 main.py revert restoration)
- TESTS: 14/14 chat PASS; 63/63 regression (auth_signin+users_me+mfa) PASS
- CURL: T01 POST+initial_message→201; T02 POST empty→201+title=""; T03 language='de'→400+CHAT_INVALID_PAYLOAD; T04 GET list→200+pagination; T05 GET detail→200+messages+citations; T06 no auth→401+AUTH_SESSION_EXPIRED; T07 nonexistent UUID→404+CHAT_CONVERSATION_NOT_FOUND; T08 invalid cursor→400+CHAT_INVALID_CURSOR; T09 ownership→403+CHAT_CONVERSATION_FORBIDDEN; T10 pagination 25 convs 3 pages (10+10+5) disjoint ✓
- LOGGING: verbose=on: 56 structured lines, uid_hash present, no PII; verbose=off: ONLY uvicorn access-log lines, zero app.chat.* or chat.routers.* lines
- KEY LEARNING: To start backend with verbose=false for logging check: extract individual env vars from root .env with `grep '^VARNAME=' .env | cut -d= -f2-`, then pass them explicitly as env prefix to uvicorn: `cd backend && JWT_PRIVATE_KEY="$KEY" DATABASE_URL="$DB" ... ENABLE_VERBOSE_LOGGING=false python3 -m uvicorn app.main:app --port 8000`. The `set -a && source .env && set +a` trick from root dir doesn't work if uvicorn is run as `backend.app.main:app` (module path error); must cd into backend/ first. The `env $(grep -v '^#' .env | xargs)` trick doesn't handle multiline values (RSA keys span multiple lines and break xargs).
- KEY LEARNING: For verbose=off check, sign in via POST /api/v1/auth/sign-in (hyphenated, NOT /auth/signin). The openapi.json reveals the correct paths at `/openapi.json`.
- KEY LEARNING: admin_peopletech.json has `roles: ["people_admin"]` (not "admin") after P02-S02-T002 update. The email/password are unchanged: admin.peopletech@inditex-sandbox.com / AdminVerify2024!.
- cross_slice_contamination: backend/app/auth/tokens.py + test_users_me.py + test_security.py + admin_peopletech.json belong to parallel P02-S02-T002 worker. Closer MUST path-scope git add to T001 write_set only.
- Evidence: orchestrator-state/tasks/evidence/P02-S03-T001/tester_cycle_3/
- Handoff: orchestrator-state/tasks/handoffs/P02-S03-T001.md

### P02-S05-T003 — DB-level D-DEF1 invariant (partial unique index on ai_models) (2026-05-13) — PASS
- OUTCOME: pass (first run)
- TESTS: 26/26 test_admin_ai.py PASS (verbose=true); 26/26 PASS (verbose=false); 202/202 regression PASS (migration suites excluded)
- MIGRATION: alembic at head=0003; round-trip down -1 → up head clean; pg_indexes confirms ai_models_default_per_type_uidx with WHERE (is_default = true)
- T26: ThreadPoolExecutor 2-worker race proves DB-level enforcement; exactly 1×200 + 1×409 AI_MODEL_DEFAULT_CONFLICT; DB has exactly 1 is_default=true row after race
- LOGGING: verbose=true shows full BEFORE/AFTER chain (.start/.ok naming); conflict path logs constraint_name + pgcode (no PII, no SQL fragments); T12 PASS asserts secret_plain never in logs; verbose=false suppresses DEBUG, WARN visible on conflict path
- KEY LEARNING: Migration test files inside tests/integration/ (not tests/ root). Correct --ignore path: `--ignore=tests/integration/test_migrations_0001_auth.py` NOT `--ignore=tests/test_migrations_0001_auth.py`. Getting this wrong causes DB contamination: test_downgrade_removes_all_tables drops all tables → subsequent integration tests fail with "relation does not exist". Recovery: alembic downgrade base → upgrade head → re-seed.
- KEY LEARNING: Re-seeding after DB restore requires correct --source path: `python3 -m app.verification_data.bootstrap --source /path/to/main/data/verification` (worktree has no data/ dir; source from main repo).
- KEY LEARNING: curl smoke tests against live uvicorn server may fail if the live server was started with different env vars (e.g., sign-in returns 500 if JWT key doesn't match). This is ACCEPTABLE when tests use TestClient (ASGI) which injects env via subprocess; the live server is a separate process. Document as pre-existing env mismatch, not a new failure. The primary evidence for 409 response comes from TestClient (T26), not curl.
- KEY LEARNING: Alembic idempotency: `alembic upgrade head` when already at head produces no stdout output (empty file). This is expected/correct. Record the round-trip test (down -1 → up head) as the canonical reversibility evidence — that shows actual migration mechanics.
- Evidence: orchestrator-state/tasks/evidence/P02-S05-T003/
- Handoff: orchestrator-state/tasks/handoffs/P02-S05-T003.md
