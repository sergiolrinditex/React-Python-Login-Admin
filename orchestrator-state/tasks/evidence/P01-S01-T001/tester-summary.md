# Tester Evidence Summary — P01-S01-T001

**Tester run timestamp**: 2026-05-09T11:00:00Z
**Venv used**: backend/.venv-t003
**DATABASE_URL tested against**: postgresql+asyncpg://hilopeople:***@localhost:5433/hilopeople_dev

## Pre-flight Status

| Check | Result |
|-------|--------|
| postgres compose service | HEALTHY (Up 3h+ before/after run) |
| GET /health | 200 {"status":"ok","version":"0.1.0"} |
| GET /live | 200 {"status":"alive"} |
| GET /ready | 503 — PRE-EXISTING (port mismatch in running backend: 5432 vs compose 5433, tracked as FU-20260508225027) — not a T001 regression |

## Test Results

### 1. Alembic round-trip migration
- `alembic upgrade head` → exit 0
- `alembic downgrade -1` → exit 0
- `alembic upgrade head` → exit 0
- After downgrade: only `alembic_version` table remains (correct per R4 risk)
- After re-upgrade: 10 tables (alembic_version + 9 auth tables)
- Evidence: `tester-alembic-roundtrip.log`

### 2. DDL verification (post-upgrade)

| Check | Result |
|-------|--------|
| Tables count | 10 (alembic_version + 9 auth tables) |
| Extension pgcrypto | 1.4 — PRESENT |
| Extension vector | 0.8.2 — PRESENT |
| Indexes total | 22 (8 explicit + PK/UQ auto) |
| users CHECK constraint | ck_users_ck_users_users_language_chk ('es','en','fr') |
| audit_logs metadata column | JSONB NOT NULL DEFAULT '{}' |
| audit_logs actor_user_id | FK ON DELETE SET NULL |
| employee_profiles user_id | FK ON DELETE CASCADE |
| refresh_tokens partial index | WHERE revoked_at IS NULL — PRESENT |

Evidence: `tester-ddl-verification.log`

### 3. pytest integration tests

| Test file | Tests | Result |
|-----------|-------|--------|
| test_auth_migration.py | 12 | 12 PASSED |
| test_seed_loader_after_migration.py | 6 | 6 PASSED |
| **Total T001-targeted** | **18** | **18 PASSED** |
| **Full backend suite** | **81** | **77 PASS, 4 skipped (expected pre-existing)** |

Evidence: `tester-pytest-integration.log`, `tester-full-suite.log`

### 4. Logging mode verification

| Mode | Result |
|------|--------|
| ENABLE_VERBOSE_LOGGING=true | Full BEFORE/AFTER flow visible (configure_logging, run_migrations_online, _get_engine, run_async_migrations — all shown with debug timestamps) |
| ENABLE_VERBOSE_LOGGING=false | Only alembic.runtime.migration INFO from stdlib handler (expected per task pack §8 exemption — alembic.ini [loggers] controls stdlib logging separately) |
| PII/secrets check | NO passwords, tokens, api_keys in verbose logs. "host redacted" appears in engine creation log line. |

Evidence: `tester-logs-verbose-true.log`, `tester-logs-verbose-false.log`

### 5. DB-down failure mode (negative test)

- Stopped postgres: `docker compose stop postgres`
- Ran `pytest tests/integration -k "auth_migration" --tb=line`
- Result: 12 ERRORS (ConnectionResetError / alembic upgrade failure) — NO silent skips
- Restarted postgres: tests return to 18/18 PASS
- Evidence: `tester-postgres-down-failure.log`

### 6. Additional observations

- **Note on .env vs test env**: The running backend process uses `DATABASE_URL=...@localhost:5432/hilopeople_dev` (from `.env`). This causes the `/ready` probe to fail (InvalidPasswordError — postgres is on 5433). This is pre-existing and tracked as FU-20260508225027. Tests explicitly override `DATABASE_URL` to port 5433 via `_ALEMBIC_ENV`, so tests are NOT affected by this env drift.
- **No regressions introduced**: Full backend suite was 77 pass / 4 skipped before T001; it is 77 pass / 4 skipped after T001.
- **Verification data contract**: T001 has no endpoint or UI surface. Schema introspection via psql + direct asyncpg SQL assertions are the contract-compliant productive verification method (per task pack §14).

## Evidence Files

| File | Content |
|------|---------|
| `tester-alembic-roundtrip.log` | Full round-trip output (upgrade → downgrade → upgrade) |
| `tester-ddl-verification.log` | Full DDL psql output (\dt, \d users, \d audit_logs, \di, extensions) |
| `tester-pytest-integration.log` | 18-test integration run with -v |
| `tester-full-suite.log` | Full backend suite (77 pass, 4 skipped) |
| `tester-logs-verbose-true.log` | ENABLE_VERBOSE_LOGGING=true run |
| `tester-logs-verbose-false.log` | ENABLE_VERBOSE_LOGGING=false run |
| `tester-postgres-down-failure.log` | DB-down negative test (12 errors, 0 silent skips) |
| `tester-summary.md` | This file |

## Verdict

**OUTCOME: pass** — All mandatory checks green. No critical findings.
