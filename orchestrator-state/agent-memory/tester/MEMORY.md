# Tester Agent Memory
# Last updated: 2026-05-11

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
