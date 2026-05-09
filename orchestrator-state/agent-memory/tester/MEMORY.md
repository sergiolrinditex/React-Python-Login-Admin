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

