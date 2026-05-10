# Tester Agent Memory

## Reusable lessons from P00-S01-T003 (2026-05-08)

### Python backend smoke tests — patterns

1. **Module-level eager init at import**: `db.py` exposed `engine = _get_engine()` at module level. This triggers engine creation at `from app.core.db import engine` — not a test failure, but a YAGNI smell the validator flags. Tester verifies it does not cause connection errors (it does not — SQLAlchemy defers pool to first query). But it IS premature speculation.

2. **structlog redaction check**: verify by actually logging with sensitive keys (`password`, `token`, `api_key`) and confirming `***REDACTED***` appears in output. This is quick and confirms the processor is wired.

3. **SecretStr confirmation**: import `Settings()` (or `Settings.model_construct()`) and confirm `isinstance(s.database_url, SecretStr)` — this is the real check that secrets cannot be accidentally logged.

4. **Verbose mode filter**: start server with `ENABLE_VERBOSE_LOGGING=false` → no DEBUG structlog lines. Then with `=true` → BEFORE/AFTER visible. Both checks are essential.

5. **ASGI test client for payload validation**: use `httpx.AsyncClient(transport=ASGITransport(app=app))` to test the health endpoint without starting a live server. Much faster and cleaner than spawning uvicorn.

6. **pip-audit scope**: system-bundled `setuptools` in venv shows CVEs but is not a project dep. This is expected and confirmed by `--skip hilo-people-backend` pattern. 0 CVEs in declared deps is the actual gate.

### tester NEXT_STATUS decision rule

- If all tests pass but validator issued `changes_requested` → `OUTCOME: pass, NEXT_STATUS: needs_debug`.
  - Rationale: tester owns lifecycle status but closer pre-check requires validator `approved`. Without `needs_debug`, the closer would reject the commit and the pipeline would stall without a debugger fix.
- If tests fail → `OUTCOME: fail, NEXT_STATUS: needs_debug`.
- If environment broken (Python missing, etc.) → `OUTCOME: blocked, NEXT_STATUS: blocked`.

### Evidence discipline

- Always prefix tester files with `tester-` to avoid overwriting developer evidence.
- Save both `.json` (parsed payload) and `.log` (curl output + HTTP status) for curl checks.
- Save server stderr to a separate file (uvicorn writes to stderr; curl output to stdout).

### venv reuse

Re-activating the developer's `.venv-t003` is correct. No need to create a new venv if the existing one has the right packages — just `pip install -U pip && pip install -e ".[dev]"` to confirm.

### Warnings that are non-blocking

- `InsecureKeyLengthWarning` from pyjwt in smoke test: expected — smoke key is `"secret"` (6 bytes). P01-S02-T001 will use a real key.
- `PendingDeprecationWarning` from python-multipart `importlib.import_module("multipart")`: watch on upgrade; import name changing to `python_multipart`.
- `LangChainPendingDeprecationWarning` from deepagents/langgraph: upstream ecosystem deprecation; no action for T003.

## Lessons from P00-S02-T003 (2026-05-09)

### Exit code capture with tee

`python ... 2>&1 | tee file.log; echo "exit=$?"` captures tee's exit code (usually 0), not Python's. Use this pattern instead:
```bash
python ... > file.log 2>&1
EXIT=$?
echo "exit=$EXIT" >> file.log
echo "exit=$EXIT"
```

### Docker / Rancher Desktop path

On this machine, Docker is via Rancher Desktop at `~/.rd/bin/docker`. Add to PATH:
```bash
export PATH="$HOME/.rd/bin:$PATH"
```

### DATA_DIR for seed CLI

The `data/verification/` bundle is at the **project root**, NOT under `backend/`. Always run the seed CLI from the project root, or use an absolute path. Tests in `conftest.py` correctly resolve via `Path(__file__).parent.parent.parent.parent / "data" / "verification"`.

### Seed loader closed-set design

The loader only processes specific named fixture files (e.g., `providers.json`, `models.json`). Extra JSON files placed in a namespace directory are IGNORED. The credential guard is validated at Pydantic schema parse time on the files the loader explicitly reads. Testing the guard by injecting an extra file (`evil.json`) does not work — inject into the actual consumed file (`providers.json`).

### Pre-existing test_ready_returns_200_when_db_ok failure

This test uses the app's DATABASE_URL env var (port 5432 in .env) while compose postgres runs on 5433. The test skip-guard checks TCP port 5433 (reachable), so the test runs but the app-level connection fails. This is a config mismatch from T002. Future tester: if still failing, note it as pre-existing; check git log on test_health.py.

### OUTCOME/NEXT_STATUS when validator says changes_requested

Per MEMORY.md rule: `OUTCOME: pass, NEXT_STATUS: needs_debug`. The debugger must apply the fix, then re-run validator+tester. The closer requires validator `approved` before committing.

## Lessons from P01-S01-T001 (2026-05-09)

### Alembic migration testing pattern

- The `.env` file may have `DATABASE_URL` pointing to port 5432 (or other mismatch), but tests MUST use the compose port (5433 in this project). Always override `DATABASE_URL` explicitly when running alembic/pytest:
  ```bash
  export DATABASE_URL="postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@localhost:5433/hilopeople_dev"
  ```
- The test files themselves use `_ALEMBIC_ENV` dict with port 5433 hardcoded — this is correct and overrides any `.env` mismatch.

### Alembic stdlib logging vs structlog

- Alembic's `[loggers]` section in `alembic.ini` controls stdlib logging for `alembic.runtime.migration` events (INFO/WARN). These appear even with `ENABLE_VERBOSE_LOGGING=false`.
- Task pack §8 explicitly exempts migration files from BEFORE/AFTER structlog requirements. The alembic.runtime.migration INFO events are the expected log output for verbose=false mode.
- env.py adds structlog BEFORE/AFTER at `run_migrations_online`, `run_async_migrations`, `_get_engine` — these only appear with verbose=true.

### DB-down negative test pattern

- Stop postgres: `docker compose stop postgres`
- Run pytest: should produce ERRORS (not SKIPs) — tests that use `skipif(not _db_reachable())` will skip on TCP check, but tests that succeed at the TCP check (port still responds during grace period) will error at the DB level with ConnectionResetError/asyncpg errors.
- The key requirement: NO SILENT PASS with DB down. Either SKIP (if `_db_reachable()` returns False) or ERROR. Both are acceptable.

### Backend /ready 503 pre-existing issue

- Backend running process may have `DATABASE_URL=...@localhost:5432/hilopeople_dev` while compose postgres is on 5433. This causes `/ready` to return 503 with InvalidPasswordError.
- This is pre-existing (FU-20260508225027). Do NOT classify as a T001 tester finding.
- Integration tests are not affected — they override DATABASE_URL explicitly.

### docker compose exec -T psql note

- `docker compose exec -T postgres psql -U hilopeople -d hilopeople_dev ...` works when the user is `hilopeople` and the database is `hilopeople_dev` (not `hilopeople`). The `POSTGRES_DB` in compose is `hilopeople_dev`.
- The `-T` flag is required in non-interactive mode (piped/captured output).

## Lessons from P01-S01-T004 (2026-05-09)

### Running uvicorn may have stale config from before the fix

If the tester kills a running uvicorn and cold-boots a fresh one, the new process picks up the updated config.py. An old still-running process will NOT hot-reload config.py changes (only Pydantic model definitions reload, not module-level constants like `_ENV_FILE`). Always do a clean kill + cold-boot to verify acceptance #3 (cold-boot test).

### dev-restart.sh --reset seed non-blocking WARN is expected

`bootstrap_verification_data failed (non-blocking)` WARN during `dev-restart.sh --reset` is expected at P01 stage because the seed loader tries to insert a `role` column that doesn't exist in migration 0001 (tracked as FU-20260509073000). This is NOT a tester finding — the script uses `|| warn` and the exit code is still 0. Accept this WARN; do not mark acceptance #4 as fail.

### pydantic-settings env_file cwd-relative pattern

When testing a pydantic-settings env_file fix: always verify `_ENV_FILE` value printed at runtime equals the absolute project-root path, AND that `.exists()` returns True, from BOTH `cd backend/` and project root. Use a quick Python one-liner to check without starting the full server.

### Password leak check pattern (DSN split)

When config.py uses `split("@", 1)[1]` to extract host:port from a DSN, verify by:
1. grep logs for the actual password string — should NOT appear
2. grep logs for `://.*:.*@` pattern — should NOT appear
3. Both verbose-on and verbose-off logs must pass the check

## Lessons from P00-S02-T005 (2026-05-09)

### ENCRYPTION_KEY for Fernet — env setup for tests

- `.env` may have `ENCRYPTION_KEY=<change-me>` (placeholder string). `.env.local` may have only the `VERIFICATION_*` keys.
- When a test needs Fernet encryption (e.g., MFA TOTP seed), it will fail with `BundleLoadError: ENCRYPTION_KEY is not a valid Fernet key` if the placeholder is sourced.
- Pattern: generate ephemeral Fernet key for test run:
  ```bash
  VALID_FERNET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  ENCRYPTION_KEY="$VALID_FERNET_KEY" pytest ...
  ```
- A missing `skipif` guard for `ENCRYPTION_KEY` validity in test 7 of `test_seed_productive_bundle.py` is a quality gap — register as follow-up if found.

### validate_with_bundle_type vs model_validate(context=...)

- When a schema uses custom class method `validate_with_bundle_type()` instead of Pydantic 2's `model_validator` with context, calling `model_validate(data, context={'bundle_type': 'productive'})` does NOT trigger the guard.
- Always use the intended entry point (`validate_with_bundle_type`) when testing bundle-type validation.
- The unit tests in `test_schemas.py` correctly test via `validate_with_bundle_type`; the tester's defense-in-depth check must use the same path.

### Defense-in-depth test for real key rejection

- The correct test: call `AiProviderSeed.validate_with_bundle_type({..., 'api_key': 'sk-...'}, bundle_type='productive')` — should raise `ValueError`.
- DO NOT test via `model_validate` with pydantic context for this pattern — the guard is not wired to pydantic's context mechanism.

### OUTCOME/NEXT_STATUS with validator changes_requested (data-only issue)

- Validator `changes_requested` for a 1-line data fix (not code) → tester still emits `OUTCOME: pass, NEXT_STATUS: needs_debug`.
- Rationale: closer requires validator `approved`, so debugger must apply the fix + re-run validator+tester. The tests themselves pass; the gate is the validator approval.

### seed CLI argument: --source is relative to cwd

- `python -m app.seeds.bootstrap_verification_data --source data/verification` resolves `data/verification` relative to cwd.
- When running from project root: `--source data/verification` (correct).
- When running from `backend/`: `--source ../data/verification` (required).
- Always run from project root for consistency with STACK_PROFILE.yaml `seed_cmd`.

## Lessons from P00-S02-T010 (2026-05-10)

### pytest binary location

- The project has TWO backend venvs: `.venv` (no pytest) and `.venv-t003` (has pytest). Always use `.venv-t003/bin/pytest`.
- This was created by the developer for T003 with all test deps. It is the canonical test runner.

### asyncpg for DB inspection without psql

- psql is not installed on this machine. Use asyncpg directly:
  ```python
  conn = await asyncpg.connect('postgresql://user:pass@127.0.0.1:5433/dbname')
  rows = await conn.fetch('SELECT ...')
  ```
- The asyncpg module is installed in `.venv-t003`.

### Fernet token in SQLAlchemy echo — pre-existing CWE-532

- When `ENABLE_VERBOSE_LOGGING=true`, db.py sets `echo=settings.enable_verbose_logging`, causing SQLAlchemy to log SQL parameters including Fernet-encrypted tokens (ciphertext, starting with `gAAAAA`).
- These are NOT plaintext API keys — they are encrypted ciphertext. But they violate defense-in-depth (CWE-532 posture).
- This is a pre-existing architectural issue, not introduced by T010. Always register as a low-severity follow-up if no existing FU covers it.
- Follow-up registered: FU-20260510044529 (low severity, blocking=False).

### Fernet key for tester runs

- Always generate a fresh tester-only Fernet key per run:
  ```bash
  ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  ```
- Confirm the key is exactly 44 chars (URL-safe base64 of 32 bytes).
- Export only in shell session — NEVER write to file, NEVER commit.

### Worktree test runs need PYTHONPATH

- When running tests from a worktree, set `PYTHONPATH=<worktree>/backend` so `app.*` imports resolve.
- The pyproject.toml in the worktree references the local backend package.
- Use the main repo's `.venv-t003` (not a worktree venv) since all deps are there.

### Pre-existing failure: test_ready_returns_200_when_db_ok

- This test reliably fails in full suite due to event-loop ordering (asyncpg `RuntimeError: Event loop is closed`).
- Confirmed pre-existing since P00-S02-T002. Do NOT count as a T010 failure.
- In full suite: 1 fail + 10 skipped is expected; any NEW fail is the regression signal.

### Total test count evolution

- Pre-T010: 136 total (per PROGRESS.md)
- Post-T010: 152 total (6 new T010 tests + 10 others from parallel slices)
- Pattern: count increases as parallel slices add tests; the "known fail" count stays at 1 event-loop test.

