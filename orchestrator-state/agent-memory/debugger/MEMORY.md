# Debugger memory — bugs, root causes, solutions, gotchas

## P00-S01-T001 (2026-05-08) — Stale dependency pins on bootstrap manifests

- **Symptom**: `/verify-slice` flagged 13 of 14 declared dependency pins (PyPI + npm) as significantly behind current stable. `01-non-negotiables.md#dependencies` requires actually-current pins.
- **Root cause**: developer pinned to "current stable at bootstrap time" using stale memory; the official-docs-researcher safety-net pass at developer-time only flagged FastAPI and did not catch the rest. By the time the slice reached verify-slice, pins were 1–2 majors behind across the board.
- **Fix applied**: text-only diff in `backend/pyproject.toml` and `frontend/package.json` — same write set ("package manifests") declared by the TASK_ID. No installs, no other files touched. Bumped: fastapi 0.115.12→0.136.1, uvicorn 0.34.2→0.46.0, ruff 0.11.10→0.15.12, mypy 1.16.0→2.0.0, pytest 8.3.5→9.0.3, pytest-asyncio 0.25.3→1.3.0, react 18.3.1→19.2.6, vite 6→8, vitest 3→4, typescript 5.8.3→6.0.3, etc.
- **Pattern**: at scaffolding phase, deps are DECLARED but NOT installed. Pin-bump fix is low-risk because real install/compat verification happens 2 slices later (T002 = npm install, T003 = pip install + dependency_smoke). Major-version compat (pytest 9, pytest-asyncio 1.x, mypy 2.x, vite 8, react 19, ts 6) is the install-slice's problem.
- **Recurring gotcha**: `01-non-negotiables.md#dependencies` says "Pin exact versions" — it does NOT say "pin to whatever you remember was stable last quarter". Trust ONLY a registry query at the moment of writing the manifest, never training-data memory for AI/ML or fast-moving JS ecosystems.
- **Anti-pattern**: re-querying registries inside debugger when verify-slice already provided verified values. Apply the verified diff verbatim — re-querying wastes a debug cycle and risks drift between debug pass and the verify report.
- **Acceptance commands at this slice (T001 scope)**:
  1. `python3 -c "import tomllib; tomllib.loads(open('backend/pyproject.toml','rb').read().decode())"` → exit 0.
  2. `python3 -c "import json; json.load(open('frontend/package.json'))"` → exit 0.
  3. `bash scripts/setup-from-scratch.sh --check` → exit 0 (only `.env no existe` warn is expected).
  4. `python3 -m py_compile backend/app/__init__.py backend/app/main.py` → exit 0.

## P00-S01-T003 (2026-05-08) — Eager module-level engine + docstring drift

- **Symptom**: validator `OUTCOME: changes_requested` (tester was already `pass`). Two findings: (a) `backend/app/core/db.py` exported `engine: AsyncEngine = _get_engine()` at module top-level, contradicting its own docstring claim of "no import-time side effects" and forcing tests to use `Settings.model_construct()` as a workaround; (b) `config.py` docstring claimed `pydantic 2.13.4` while the actual pin (forced by litellm transitive constraint) is `2.12.5`.
- **Root cause (a)**: speculative "future-proofing for Alembic in P01-S01-T001" added a module-level export that ran the factory at import time. The function does not connect to the DB, but it does build the engine, instantiate the pool object, read settings, etc. — all of these are import-time side effects that the docstring promised the module would NOT have. YAGNI violation: the consumer (Alembic env) does not exist yet, and when it lands it can call a public accessor.
- **Root cause (b)**: developer wrote the docstring before resolving the pin conflict, then forgot to update it after litellm forced the downgrade. Pure documentation drift.
- **Fix applied**: replace `engine: AsyncEngine = _get_engine()` (last line of file) with a public `get_engine() -> AsyncEngine` lazy accessor that delegates to the existing memoized `_get_engine()`. Docstring for the module updated to describe `get_engine()` instead of `engine`. Single character fix in `config.py` docstring. **Tests untouched** — they only imported `get_session`, never the deleted `engine` symbol.
- **Pattern — lazy-singleton in Python at module level**: when a module needs to expose a "singleton" expensive resource (DB engine, HTTP client, Redis connection, LLM client), prefer this triple:
  ```python
  _resource: T | None = None  # private cache, NOT a public symbol

  def _get_resource() -> T:  # private builder + memoizer
      global _resource
      if _resource is None:
          _resource = build_expensive_thing()
      return _resource

  def get_resource() -> T:  # public lazy accessor
      """Public lazy accessor — first call builds, all calls return same."""
      return _get_resource()
  ```
  Never `resource: T = _get_resource()` at module top-level. That builds the resource at import time and breaks (a) tests that need to override config before first use, (b) cold-start performance, (c) the documented invariant that "import is side-effect-free".
- **Pattern — SQLAlchemy async testing without a live DB**: smoke tests should `from app.core.db import get_session` and assert the symbol is callable. Do NOT call `get_session()` (it requires a live engine + pool). Do NOT call `_get_engine()` from tests unless the test fixture injects a working DSN (e.g. SQLite in-memory aiosqlite). The smoke pattern is import-only, exercise-real-symbol-elsewhere.
- **Pattern — pin-version drift in docstrings**: any docstring or comment that names a version number is a future debt. Either omit the version (`Dependencies: pydantic-settings, pydantic`) or accept that you must update both `pyproject.toml` AND every docstring/comment when bumping. There is no `ruff` rule that catches this; only manual review or grep audits do. For T003 this caught 1 drift; future audits should `grep -rn "pydantic 2\." backend/app/` etc. before the validator does.
- **Anti-pattern that caused this**: docstring written aspirationally ("This module does NOT connect at import time") while code does have an import-time side effect of building the engine. If the docstring describes a contract, the code must enforce it. Use a quick `python -c "import app.core.db; print('ok')"` with a deliberately broken DATABASE_URL to verify the contract (it should still print 'ok' if there are no import-time side effects beyond settings read).

## P00-S02-T002 (2026-05-09) — CWE-532 leak via structlog Rich traceback frame locals

- **Symptom**: `/verify-slice` flagged a BLOCKER security finding. Hitting `/ready` with a bad DSN (port 5499, no listener) under `ENABLE_VERBOSE_LOGGING=true` produced an stdout log file containing `hilopeople_dev_pwd × 14`, `localhost × 18`, `5499 × 16`, `postgresql+asyncpg × 5`. Response body itself was sanitized correctly; the leak was ONLY in stdout/stderr logs. Validator+tester missed it because (a) validator audited only the structured event_dict keys, (b) tester's DB-down test used a hand-crafted `OperationalError("simulated connection failure")` whose monkeypatched call site has clean frame locals.
- **Root cause**: `_logger.error("...", error_class=..., exc_info=True)` in `_probe_db()`'s except branches. In verbose mode, `app/core/logging.py` configures structlog with `structlog.dev.set_exc_info` + `structlog.dev.ConsoleRenderer()`. ConsoleRenderer's default exception formatter is Rich's `RichTracebackFormatter`, which has `show_locals=True` by default. asyncpg/SQLAlchemy bind `cparams = {host, user, password, port, database}` and `ConnectionParameters(...)` as frame locals on the connect path — Rich renders those locals verbatim to the output stream.
- **Fix applied**: drop `exc_info=True` from both except branches in `_probe_db()`. Add structured field `db_detail=detail` (sanitized via `_sanitize_db_error()`) so operators still get a usable error message. Defense in depth: same comment in `app/main.py` request_id middleware exception path (the path didn't use `exc_info=True` already, but the pattern is poison and easy to reintroduce). NO changes to `app/core/logging.py` — that file is out of scope for the debugger fix; the global `RichTracebackFormatter(show_locals=False)` tuning is tracked in follow-up `FU-20260509044829-disable-structlog-rich-traceback-show-locals-glo`.
- **Pattern — `exc_info=True` is POISON when ConsoleRenderer + RichTracebackFormatter are used with default `show_locals=True`**. Any function in any except branch that handles exceptions whose stack contains sensitive locals (DSN, password, JWT, API key, request payload with PII) WILL leak those locals to logs in verbose mode. The structlog `_redaction_processor` does NOT redact traceback locals — it only operates on the event_dict. Solution: either (a) drop `exc_info=True` everywhere and rely on structured fields + class name (the defensive default for prod), OR (b) configure `RichTracebackFormatter(show_locals=False)` globally and document it.
- **Pattern — regression test for CWE-532 traceback-locals leak**: build a fake engine/client whose call path raises an exception while binding the secret values as **frame locals** (not in the exception message). Capture stdout/stderr via `capsys`, assert the secret values are NOT present. To force `configure_logging(verbose=True)` past its idempotent guard: `core_logging._configured = False; core_logging.configure_logging(verbose=True); ... ; finally: core_logging._configured = prev`. This test FAILS with `exc_info=True` and PASSES without it — a true behavioral regression test.
- **Anti-pattern — "richer logs are always better"**: developers add `exc_info=True` because it gives them a stack trace in dev. But once `ConsoleRenderer` + Rich tracebacks are in the chain, `exc_info=True` is a credentials-leak time bomb. The structured `error_class=type(exc).__name__` field is enough for prod observability; debugging can use `logger.exception()` deliberately in known-safe code paths after auditing what locals exist in that stack frame. Default to OFF.
- **Validator/tester gotcha**: a mock-based DB-down test that constructs `OperationalError("clean message")` directly will NEVER catch this bug — the monkeypatched call has clean locals. Real reproduction requires either (a) a fake engine whose connect() builds and raises with the secrets as locals, or (b) hitting a real DB-down with `ENABLE_VERBOSE_LOGGING=true` and grepping the log file. Add the former to your test suite for any error-path that touches infra (DB, Redis, S3, LLM provider).
- **Acceptance commands at this slice (T002 debugger fix scope)**:
  1. `pytest tests/test_health.py -v` → 9/9 PASS (with `DATABASE_URL` overridden to compose port 5433).
  2. `pytest tests/ -v` → 48/48 PASS.
  3. `ruff check app/main.py app/api tests/test_health.py` → clean.
  4. `mypy app/api app/main.py tests/test_health.py` → clean.
  5. Live verbose=true uvicorn against `DATABASE_URL=postgresql+asyncpg://baduser:topsecret_pwd_xyz_8f3c1@hostxyz:54399/dbxyz` + `curl /ready` → 503 + log file count of `topsecret_pwd_xyz_8f3c1` MUST be 0.
  6. Negative test sanity: temporarily re-add `exc_info=True`, run test #9 → MUST FAIL.
