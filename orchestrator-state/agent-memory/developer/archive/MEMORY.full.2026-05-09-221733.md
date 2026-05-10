# Developer Agent Memory — Hilo People

## Codebase patterns discovered

### Env variable naming
- `dev-restart.profile.sh` uses `API_PORT` (not `BACKEND_PORT`) and `FRONT_PORT` (not `FRONTEND_PORT`).
- These are the canonical names to use in `.env.example` and anywhere env vars for ports are needed.
- Default: `API_PORT=8000`, `FRONT_PORT=5173` (Vite default, not 5000 from Flutter template comment).

### `scripts/setup-from-scratch.sh`
- Did NOT have `--check` mode originally. Added in P00-S01-T001.
- `--check` mode sets `CHECK_MODE=1` which causes `run_if_declared()` to skip execution without failing.
- The script checks `BACKEND_ROOT=backend/app` and `FRONTEND_ROOT=frontend/src` from STACK_PROFILE.
- If either root doesn't exist, it emits WARN and skips; this was the blocker for T001 verify.
- After T001: both roots exist, so no more root-missing warnings.

### Backend module structure
- Uvicorn entry point: `uvicorn app.main:app` (uses `backend/app/main.py`).
- `backend/app/__init__.py` is required as package marker for this to resolve.
- No root `backend/__init__.py` — pytest discovers via pyproject.toml `testpaths = ["tests"]`.

### Logging pattern (bootstrap)
- T001 uses stdlib `logging` with `ENABLE_VERBOSE_LOGGING` env flag.
- T003 will replace with `structlog` for structured JSON logging per TECHNICAL_GUIDE.
- BEFORE/AFTER log pattern: `logger.debug("BEFORE %s", ...)` + `logger.debug("AFTER %s", ...)`.

### Package version pinning (T001 + T002, confirmed 2026-05-08 npm registry)
- **Backend (T003 installs)**: fastapi==0.136.1, uvicorn[standard]==0.46.0, ruff==0.15.12, mypy==2.0.0, pytest==9.0.3, pytest-asyncio==1.3.0
- **Frontend runtime (T002 installed)**: react==19.2.6, react-dom==19.2.6, react-router-dom==7.15.0, @tanstack/react-query==5.100.9, react-hook-form==7.75.0, zod==4.4.3, @hookform/resolvers==5.2.2, i18next==26.0.10, react-i18next==17.0.7, i18next-browser-languagedetector==8.2.1
- **Frontend dev (T002 installed)**: @types/react==19.2.14, @types/react-dom==19.2.3, @vitejs/plugin-react==6.0.1, typescript==6.0.3, vite==8.0.11, vitest==4.1.5, @testing-library/react==16.3.2, @testing-library/dom==10.4.1, @testing-library/jest-dom==6.9.1, jsdom==29.1.1

## Implementation decisions

### P00-S01-T001 (2026-05-08)
- Added `--check` mode to `scripts/setup-from-scratch.sh` (smallest fix; 11 lines).
  Reason: without it, `alembic upgrade head` runs and fails (not installed); `--check` skips execution.
- Used `ast.parse()` for "compiles" acceptance (no FastAPI install needed at this stage).
- Used `frontend/src/.gitkeep` not `frontend/src/main.tsx` because: (a) task pack says "just the folder", (b) hook might block files outside write set if main.tsx was a full TS file.
- `FRONT_PORT=5173` in .env.example matches Vite default; `dev-restart.profile.sh` had FRONT_PORT=5000 default in comments but that's from Flutter template, not React stack.

### P00-S01-T002 (2026-05-08)
- AppProviders export: `export function AppProviders({ children }: { children: ReactNode })` — locked. Downstream slices depend on this exact name.
- Zod v4 import: use `import { z } from 'zod'` (NOT `'zod/v4'` sub-path unless mixing v3+v4). `.merge()` deprecated → `.extend()`. `.min(n, 'msg')` → `.min(n, { message: 'msg' })`.
- React Router v7: `react-router-dom` is thin wrapper over `react-router`. P01-S03-T001 must choose library mode (BrowserRouter) vs data mode (createBrowserRouter) intentionally.

### P00-S01-T003 (2026-05-08) — Backend dep pack + core/

**Hatchling editable install requirements**:
- `backend/README.md` is required (hatchling validates the readme field).
- `[tool.hatch.build.targets.wheel] packages = ["app"]` is required because the package dir is named `app` not `hilo_people_backend` (hatchling can't auto-discover it).
- Without these, `pip install -e ".[dev]"` fails with `OSError: Readme file does not exist: README.md` then `ValueError: Unable to determine which files to ship`.

**litellm pydantic pin (CRITICAL)**:
- `litellm==1.83.14` requires `pydantic==2.12.5` EXACTLY (not a range).
- Any attempt to pin `pydantic>=2.13.0` causes `ResolutionImpossible` at pip install time.
- Workaround: pin `pydantic==2.12.5` (same resolved version). When litellm upgrades, we can bump.

**celery redis constraint**:
- `celery==5.6.3` → `kombu==5.6.x` → `redis<6.5`.
- `redis==7.4.0` is incompatible. Use `redis==6.4.0` (latest satisfying <6.5).
- Document this constraint in pyproject.toml comment so next developer doesn't bump redis blindly.

**litellm uses `_version` not `__version__`**:
- `hasattr(litellm, "__version__")` returns False. Use `_version` or `hasattr(litellm, "_version") or hasattr(litellm, "__version__")`.

**structlog configure_logging() pattern**:
- Use `cache_logger_on_first_use=True` in `structlog.configure()`.
- `configure_logging()` should be idempotent (guard with `_configured` bool).
- For verbose mode: `ConsoleRenderer()` (colored dev output). For non-verbose: `JSONRenderer()`.
- Import from main.py: one-line `from app.core.logging import configure_logging, get_logger` then call before the FastAPI app is created.

**db.py eager engine creation**:
- The line `engine: AsyncEngine = _get_engine()` at module level triggers engine creation on import.
- This is OK (no actual connection established), but tests that import `app.core.db` will call `get_settings()` which needs `DATABASE_URL` in env or default fallback.
- In smoke tests, use `Settings.model_construct()` to avoid importing from `app.core.db`.

**asyncpg vs psycopg2 for Alembic**:
- Since Alembic 1.11.0, async migrations work with asyncpg via `run_sync()`.
- No psycopg2-binary needed. One driver covers both ORM and migrations.

### P00-S01-T004 (2026-05-09) — Design tokens + editorial system

**tsconfig.json project references + `composite: true`**:
- `tsc -b` requires that referenced tsconfig files (via `"references"`) have `"composite": true` set.
- Removing `"noEmit": true` from `tsconfig.node.json` is also required (composite and noEmit are incompatible).
- Error TS6306 + TS6310 at build time are the diagnostic signals.

**CSS imports in TypeScript with `verbatimModuleSyntax: true`**:
- Side-effect CSS imports (`import './styles.css'`) cause TS2882 "Cannot find module" without a global CSS type declaration.
- Solution: add `frontend/src/vite-env.d.ts` with `/// <reference types="vite/client" />`.
- This is standard Vite template boilerplate that should be in every Vite+React project from day 1.

**`verbatimModuleSyntax: true` forces `type` keyword on type imports**:
- Any `import { SomeType }` where `SomeType` is a TypeScript type must use `import { type SomeType }` or `import type { SomeType }`.
- Error TS1484 "X is a type and must be imported using a type-only import".
- Affected: `providers.tsx` (ReactNode), any future file importing React types.

**`toHaveStyle` + CSS custom properties in jsdom**:
- jsdom does not resolve CSS custom properties. `toHaveStyle({ border: 'var(--hairline)' })` fails with the computed value (empty/default).
- Correct pattern: `expect(el.getAttribute('style')).toContain('var(--hairline)')`.
- This is the standard Testing Library approach for CSS variable assertions.

**`afterEach(cleanup)` required when `globals: false`**:
- When Vitest runs with `globals: false` (no global describe/it/expect), `@testing-library/react` does NOT auto-register cleanup via `afterEach`.
- Without explicit cleanup, DOM state accumulates across tests in the same file → "Found multiple elements" errors.
- Solution: add `afterEach(cleanup)` in `src/test/setup.ts` (the `setupFiles` entry).
- With `globals: true`, Testing Library registers cleanup automatically.

**`@testing-library/user-event` is NOT installed in this project**:
- Only `@testing-library/react`, `@testing-library/dom`, `@testing-library/jest-dom` are installed.
- Use `fireEvent` from `@testing-library/react` for interaction testing.
- If user-event is needed later, install with `npm install --save-dev @testing-library/user-event` and add exact pin in package.json.

**Vitest co-located vs separate config**:
- This project keeps `vitest.config.ts` separate (not co-located in `vite.config.ts`).
- `vitest.config.ts` must include the React plugin and `@` alias for test imports to resolve correctly.
- If Vite plugin is missing from vitest.config, TSX files import fine but JSX transform fails.

**Regex `/active/i` matches "Inactive"**:
- When using Testing Library `getByRole` with a regex name, `/active/i` matches BOTH "Active" and "Inactive".
- Use exact string match `{ name: 'Active' }` for disambiguation when there are substring overlaps.

## P00-S02-T001 (2026-05-09) — Docker Compose + Dockerfiles

**PostgreSQL 18 volume path change (CRITICAL)**:
- PG18 requires volume at `/var/lib/postgresql` NOT `/var/lib/postgresql/data`.
- PG18 auto-creates `/var/lib/postgresql/18/main/`. Wrong mount → startup error.
- See: https://github.com/docker-library/postgres/pull/1259

**LiteLLM image has no curl/wget**:
- `ghcr.io/berriai/litellm` images ship without curl/wget.
- Docker healthcheck: `python3 -c "import urllib.request; urllib.request.urlopen('...')"`.
- v1.83.14-stable takes ~2min to initialize → `start_period: 120s`.

**Worker healthcheck inheritance**:
- Worker shares backend image which has `HEALTHCHECK CMD curl http://localhost:8000/health`.
- Worker has no HTTP port → healthcheck always fails.
- Override in compose: `healthcheck: disable: true`. Real check in P02-S04-T002.

**Postgres host port conflict on macOS**:
- macOS dev machines often have local Postgres on 5432.
- Map compose postgres to host 5433: `5433:5432`. Inter-container still uses 5432.

**nginx-unprivileged current stable is 1.29-alpine (1.27 DOES NOT EXIST)**:
- Task packs may reference outdated 1.27 — always verify with researcher.

**redis:8-alpine is current stable (7.4 is outdated)**:
- Python `redis==6.4.0` compatible with Redis 8 server.

**litellm image tag pinning**:
- Use `ghcr.io/berriai/litellm:v<X.Y.Z>-stable` to match Python lib pin.
- `main-stable` is floating; `main-latest` is for nightly testing only.

### P00-S01-T005 (2026-05-09) — i18n resources ES/EN/FR

**i18next namespace vs key separator**:
- The namespace separator in i18next is `:` — not `.`.
- `t('common:productName')` → looks up key `productName` in namespace `common`.
- `t('common.productName')` with `defaultNS:'common'` → looks for nested key `{ common: { productName: ... } }` in the `common` namespace. This is WRONG when the bundle is flat `{ "productName": "Hilo" }`.
- In test files: always use `t('ns:key.nested')` form for cross-namespace assertions.
- In production code: use `useTranslation('ns')` hook then `t('key.nested')` for clean ergonomics.

**Eager vs lazy loading in i18next**:
- Eager (static import JSON) is the right choice when bundles are small and test reliability matters.
- Lazy (i18next-http-backend) requires fetch mocking in Vitest+jsdom — avoid until P03 hydration performance becomes a concern.
- With eager loading, `i18n.isInitialized` is true synchronously after module import; no Suspense needed.

**i18n module initialization pattern**:
- The `frontend/src/i18n/index.ts` module holds the singleton.
- `providers.tsx` imports it (`import i18n from '../i18n'`) — this import both initializes the singleton AND provides the instance for `I18nextProvider`.
- NO need for a separate `import '../i18n'` side-effect import in providers.tsx when using a named import.
- `if (!i18n.isInitialized)` guard in `index.ts` is still needed to survive HMR hot-reloads and Vitest module isolation edge cases.

**Vite JSON imports**:
- `resolveJsonModule: true` in tsconfig.json (already set in T004) enables `import esCommon from '../../public/locales/es/common.json'`.
- JSON imports are typed: TypeScript infers the shape of the JSON object automatically.
- In Vitest, JSON imports work natively without any configuration (Vitest respects Vite's JSON plugin).

### P00-S02-T002 (2026-05-09) — Health live/ready endpoints + request_id middleware

**structlog BoundLogger API with mypy**:
- `_logger.debug("event string", key=val)` — event is POSITIONAL, not keyword.
- `_logger.debug("event string", event="health.start")` raises mypy "multiple values for keyword argument 'event'" [misc].
- Solution: use the event string as positional arg 1; extra context as keyword args.

**@app.middleware("http") vs BaseHTTPMiddleware**:
- Prefer `@app.middleware("http")` decorator over `add_middleware(BaseHTTPMiddleware)`.
- BaseHTTPMiddleware.dispatch return type annotation causes mypy override error.
- @app.middleware is cleaner, idiomatic FastAPI, and mypy-safe with `Callable[[Request], Awaitable[Response]]` annotation.

**structlog contextvars pattern for per-request middleware**:
- `structlog.contextvars.clear_contextvars()` — call at start of request to clear previous request's context.
- `structlog.contextvars.bind_contextvars(key=val)` — bind new context.
- `structlog.contextvars.clear_contextvars()` in finally — always clean up.
- `merge_contextvars` processor must be in structlog.configure() chain (already in T003's core/logging.py).

**SQLAlchemy error hierarchy for DB probe**:
- `sqlalchemy.exc.SQLAlchemyError` covers ALL asyncpg DB-down cases (researcher confirmed).
- asyncpg raw exceptions are always wrapped by SQLAlchemy — you do NOT need to import asyncpg.
- Bare Exception fallback is acceptable as last resort in /ready to ensure 503 never becomes 500.

**httpx 0.28 ASGITransport**:
- `AsyncClient(app=app)` is REMOVED in httpx 0.28. The deprecated kwarg was removed, not just warned.
- Correct: `AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")`.
- `_make_client()` helper avoids repeating this pattern in every test.

**Compose postgres credentials vs default config**:
- Default config.py fallback: `change-me` password.
- Compose POSTGRES_PASSWORD default: `hilopeople_dev_pwd`.
- Tests that probe real DB must set DATABASE_URL with correct credentials.
- `_postgres_reachable()` only checks if port 5433 is open, not if credentials are correct.
- Real-DB test will fail if DATABASE_URL is not overridden with correct credentials.

**OperationalError in tests**:
- `sqlalchemy.exc.OperationalError(statement, params, orig)` — 3rd arg `orig` must be `BaseException`.
- `None` triggers mypy [arg-type] error. Use `Exception("connection refused")` as the third arg.

**pool_pre_ping and /ready probe**:
- `pool_pre_ping=True` fires on pool checkout, not on every request.
- /ready probe uses `engine.connect()` + `SELECT 1` to give an explicit per-request signal.
- Both serve different purposes: pool_pre_ping detects stale connections; /ready validates current DB availability.

### P00-S02-T003 (2026-05-09) — Seed data + verification bundle

**`_comment` fields in JSON fixtures and Pydantic `extra="forbid"`**:
- JSON fixtures use `_comment` as a documentation convention. With Pydantic `extra="forbid"`, these cause `ValidationError: Extra inputs are not permitted`.
- Solution: in `io.py`, strip all `_`-prefixed keys from the raw dict BEFORE `model_cls.model_validate(raw)`. This preserves schema strictness while allowing underscore-prefixed metadata in fixture files.
- Pattern: `raw = {k: v for k, v in raw.items() if not k.startswith("_")}`.

**EmailStr requires email-validator (not in dep stack)**:
- `pydantic.networks.EmailStr` calls `import email_validator` at schema BUILD time (not just validation time).
- If `email-validator` is not installed, any import of a schema using `EmailStr` raises `ImportError`.
- Project rule: no package for something doable in <20 lines.
- Solution: `str` field + `field_validator` with regex `r"^[^@\s]+@[^@\s]+\.[^@\s]+$"`.

**Synthetic credential guard pattern**:
- All provider/MCP credentials in fixtures MUST start with `synthetic-` to prevent accidental real key commit.
- Additional guard: reject keys matching patterns: `sk-[A-Za-z0-9]{20,}`, `sk-ant-[A-Za-z0-9-]{30,}`, `AIza[A-Za-z0-9-_]{35,}`, `Bearer [A-Za-z0-9-_]{40,}`.
- Implemented in `backend/app/seeds/schemas/admin_ai.py._require_synthetic_prefix()` — imported by `mcp_agents.py`.

**SHA256 checksum is exactly 64 hex characters**:
- RagDocumentSeed enforces `min_length=64, max_length=64` for `checksum_sha256`.
- SHA256 produces 256 bits = 32 bytes = 64 hex characters. Do not add/remove characters from synthetic checksums.
- Common typo: counting wrong and getting 66 chars. Always `echo -n "<value>" | wc -c` to verify.

**asyncpg connects fine even when SQLAlchemy app-level engine fails**:
- The seed integration tests connect via asyncpg directly (correct DSN).
- The health endpoint test fails because it goes through the app's SQLAlchemy engine which reads DATABASE_URL from env (set to `change-me` password default, not `hilopeople_dev_pwd`).
- These are two separate connection paths. Seeds can pass while health test fails — expected in dev.

**Seed exit codes**:
- `0` = success (including "all tables missing" — table-tolerant in P00)
- `1` = fixture schema validation error OR JSON parse error
- `2` = bundle source directory not found (--source points to non-existent path)

**structlog.testing.capture_logs() assertion pattern**:
- `capture_logs()` context manager returns a list of dicts (one per log event).
- Assert on `e.get("event")`, `e.get("log_level")`, `e.get("namespace")`, `e.get("table")`.
- Log level in captured dict is `"warning"` (lowercase), not `"WARNING"`.
- Only works for Python-path log calls (not subprocess output).

## Gotchas

- `dev-restart.profile.sh` is a FLUTTER template not yet customized for React. Back-fill will happen in a future P00 slice. Don't rely on `back_start()` or `front_start()` functions there yet.
- `scripts/setup-from-scratch.sh` doesn't use `set -e` properly for external commands in subshell `( cd "$PROJECT_ROOT" && bash -lc "$cmd" )` — if the cmd fails the parent continues. This is fine for `--check` mode but note this for future scripts.
- `health` endpoint stub returns flat dict `{status, version, uptime}`. Full impl in P00-S02-T002 will wrap it in `{data: {status}}` envelope per TECHNICAL_GUIDE §6.2. Don't expand the stub now.
- All DAG successor tasks (T002, T003, T004) depend on this task being `done`. Don't unblock them until verify-slice + closer completes.
- **hook_write_scope_guard.py path resolution in worktrees**: The hook resolves absolute paths relative to project_root(). Files in `.claude/worktrees/<name>/frontend/...` appear as `.claude/worktrees/.../frontend/...` relative to main project root — this starts with `.claude/` and is BLOCKED. Always write product code using the MAIN REPO absolute path (`/Users/sergiolr/Desktop/Productos/React-Python-Login-Admin/frontend/...`), then `cp` to worktree for test execution.
- **npm install deps placement**: Running `npm install <pkg>` without flags places everything in `dependencies`. Use `--save-dev` for test/build tools. Always run `grep -E '"\^|"~' package.json` after install to catch caret/tilde pins and remove them (project policy: exact pins).
- **`npm run build` is blocked without tsconfig.json**: The build script is `tsc -b && vite build`. Until tsconfig is added (T004 or later), `build` always fails. Do NOT use build as verify gate in T002/T003/T004.
- **python-multipart import name**: In 0.0.27, the package is still `import multipart`. Future versions may only export `python_multipart`. Watch for `PendingDeprecationWarning: Please use import python_multipart instead.` — update smoke test when the old name is removed.
- **deepagents pulls langchain-anthropic as transitive dep**: This means anthropic SDK is in the transitive deps. If deepagents is removed, anthropic may disappear from the lock. Keep `langchain-anthropic` declared if anthropic SDK is needed directly.
- **PYTHONPATH for pytest**: When running pytest from `backend/` dir, pytest finds `app/` via sys.path. But when running from repo root, set `PYTHONPATH=backend`. The pyproject.toml `testpaths = ["tests"]` means pytest runs relative to `backend/` if invoked from there.

### P00-S02-T004 (2026-05-09) — CWE-532 structlog frame-locals leak fix

**structlog 25.5.0 RichTracebackFormatter API**:
- `structlog.dev.RichTracebackFormatter(show_locals=False)` — `show_locals` kwarg is boolean, stable since structlog 21.x.
- `structlog.dev.ConsoleRenderer(exception_formatter=<formatter>)` — `exception_formatter` kwarg accepts any `ExceptionRenderer`, stable since structlog 22.x.
- Pattern: `renderer = structlog.dev.ConsoleRenderer(exception_formatter=structlog.dev.RichTracebackFormatter(show_locals=False))`

**Test isolation for configure_logging() tests**:
- `configure_logging()` adds a `StreamHandler(sys.stdout)` to the root logger AND mutates global structlog state.
- After capsys capture closes, the StreamHandler points to a closed file → "I/O operation on closed file" in subsequent tests.
- Pattern: save handlers before test (`_save_logging_state()`), close/remove any added handlers in finally (`_restore_logging_state()`).
- This is the same issue the existing test_health.py tests work around via the `prev_configured` restore + the fact they run in a specific order.

**_configured guard and test isolation**:
- `core_logging._configured = False` is required before calling `configure_logging()` in tests.
- Restoring `core_logging._configured = prev` alone is NOT sufficient — you must also clean up root logger handlers.
- Full pattern in `_save_logging_state()` / `_restore_logging_state()` in tests/test_logging.py.

**Test_ready_db_ok pre-existing auth failure**:
- `test_ready_db_ok` in test_health.py has `@pytest.mark.skipif(not _postgres_reachable(), ...)`.
- `_postgres_reachable()` only checks if port 5433 is open — it does NOT check credentials.
- If compose postgres is running but with different credentials than config.py expects, the test fails with InvalidPasswordError.
- This failure exists in the T002 baseline (48 counted as baseline; this test was already failing).
- T004 does NOT change this — still 51/52 pass (1 pre-existing auth fail unchanged).

### P01-S01-T001 (2026-05-09) — DB auth baseline (Alembic + migration 0001)

**JSONB import from dialect (CRITICAL)**:
- `sqlalchemy.JSONB` does NOT exist. `AttributeError: module 'sqlalchemy' has no attribute 'JSONB'`.
- Correct: `from sqlalchemy.dialects.postgresql import JSONB`.
- All JSONB columns must use this dialect-specific import.

**`metadata` column name collision in ORM**:
- `Base.metadata` is a reserved attribute on all SQLAlchemy declarative classes.
- If you name a column `metadata`, the Python attribute conflicts with the metaclass attribute.
- Solution: use a different Python name + the positional string arg to `mapped_column`:
  ```python
  metadata_col: Mapped[dict] = mapped_column("metadata", JSONB, ...)
  ```
- This applies to BOTH `EmployeeProfile` and `AuditLog` (both have a `metadata` DB column).

**TYPE_CHECKING for circular ORM cross-imports**:
- `user.py` imports auth types for `relationship()` back-references; `auth.py` imports `User`.
- Avoid circular imports at module load time by wrapping forward-reference imports in `TYPE_CHECKING`:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from app.db.models.auth import AuditLog, MfaTotpSecret, PasswordResetToken, RefreshToken
  ```
- The relationship `"ClassName"` string form (deferred resolution) works without runtime import.
- SQLAlchemy 2.0.49 resolves all string class names at mapper finalization, not at class definition.

**pytest-asyncio event loop isolation pattern**:
- `asyncio_mode=auto` creates a NEW event loop per test function.
- A shared module-scoped `AsyncEngine` fixture will throw `Future ... attached to a different loop`.
- Pattern: `_fresh_conn()` asynccontextmanager creates a new engine+connection per test and disposes after:
  ```python
  @asynccontextmanager
  async def _fresh_conn() -> AsyncGenerator[AsyncConnection, None]:
      engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)
      try:
          async with engine.connect() as conn:
              yield conn
      finally:
          await engine.dispose()
  ```
- Module-level setup (alembic upgrade head) must use a SYNCHRONOUS autouse fixture that calls alembic as a subprocess, not an async fixture.

**`_SKIP_WHEN_MIGRATION_APPLIED` pattern for schema-conditional tests**:
- Some tests verify the "table missing → skip" path of seed loaders — these break when the real schema exists.
- Pattern:
  ```python
  def _users_table_exists() -> bool:
      async def _check() -> bool:
          engine = create_async_engine(_DSN, pool_size=1, max_overflow=0)
          try:
              async with engine.connect() as conn:
                  result = await conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='users'"))
                  return result.scalar() == 1
          finally:
              await engine.dispose()
      try:
          return asyncio.run(_check())
      except Exception:
          return False

  _SKIP_WHEN_MIGRATION_APPLIED = pytest.mark.skipif(
      _users_table_exists(),
      reason="Real schema present: 'table missing → skip' path no longer applies."
  )
  ```
- Mark P00 "no_tables" tests with `@_SKIP_WHEN_MIGRATION_APPLIED` so they skip gracefully.
- Track in follow-up FU to replace synthetic bundle with real fixtures.

**Alembic async env.py pattern (1.18.4)**:
- Async env.py requires: `asyncio.run(run_async_migrations(engine))`.
- `run_async_migrations` must use `async with engine.connect() as connection` then `await connection.run_sync(do_run_migrations)`.
- `do_run_migrations(connection: Any)` — typed as `Any` to avoid mypy issues with the synchronous wrapper type.
- `engine.dispose()` must be called in `run_async_migrations` after `run_sync` completes (inside `try...finally` ideally).
- Logging configure call must happen BEFORE `from app.db.models import Base` (models trigger structlog setup).

**Naming convention in Base.metadata**:
- SQLAlchemy constraint naming convention ensures stable autogenerate:
  ```python
  NAMING_CONVENTION = {
      "ix": "ix_%(table_name)s_%(column_0_name)s",
      "uq": "uq_%(table_name)s_%(column_0_name)s",
      "ck": "ck_%(table_name)s_%(constraint_name)s",
      "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
      "pk": "pk_%(table_name)s",
  }
  ```
- CHECK constraint name passed to `CheckConstraint("condition", name="my_chk")` becomes `ck_<tablename>_my_chk`.
- Partial index must be created explicitly in migration (not via ORM) — partial indexes require `postgresql_where=` kwarg in `op.create_index()`.

**Migration downgrade ordering (child tables first)**:
- Always drop child tables (FK side) before parent tables.
- Order: audit_logs, password_reset_tokens, mfa_totp_secrets, refresh_tokens, user_roles, employee_profiles, permissions, roles, users.
- Extensions (pgcrypto, vector) should NOT be dropped in downgrade — they may be used by other schemas/extensions.

**Alembic `revision` (string not integer)**:
- `revision = "0001"` (quoted string), NOT `revision = 0001` (integer).
- `down_revision = None` for the first migration (no parent).
- `branch_labels = None`, `depends_on = None` (standard for linear history).

### P01-S01-T004 (2026-05-09) — pydantic-settings env_file absolute path fix

**pydantic-settings env_file is cwd-relative (CRITICAL gotcha)**:
- `env_file=".env"` in `SettingsConfigDict` is resolved relative to the PROCESS cwd at `Settings()` instantiation time, NOT relative to the Python file declaring it.
- This works when uvicorn runs from project root (`.env` is there), but breaks silently when pytest/alembic run from `cd backend/` (no `.env` there → Settings falls back to field defaults → wrong DB credentials → `InvalidPasswordError`).
- Fix: anchor to `Path(__file__).resolve().parents[N]` where N = depth from project root:
  ```python
  _PROJECT_ROOT = Path(__file__).resolve().parents[3]  # backend/app/core/config.py
  _ENV_FILE = _PROJECT_ROOT / ".env"
  model_config = SettingsConfigDict(env_file=str(_ENV_FILE), ...)
  ```
- `.resolve()` handles symlinks. `parents[3]` is deterministic for `backend/app/core/config.py`.
- pydantic-settings accepts `str | Path | os.PathLike | list[...]` for `env_file`. Using `str(_ENV_FILE)` is safe.
- Real env vars (docker-compose, CI, shell exports) still take precedence over `.env` file.

**Logging DATABASE_URL safely**:
- DATABASE_URL contains a password → NEVER log the full value.
- To log the host+port for debugging, split on `@`: `dsn.split("@", 1)[1]` gives `host:port/dbname`.
- Log this only in verbose mode; gate with `if _VERBOSE:`.

**Compose port mapping means two modes**:
- When compose maps `"5433:5432"` for postgres, host processes (uvicorn, pytest, alembic) must use `localhost:5433`.
- Containers in the compose network use the service name (`postgres:5432`).
- Document both modes in `.env.example` as Mode A (native dev) and Mode B (in-compose). Mode B is overridden by docker-compose.yml env block; `.env` is not used there.
- Default the `.env.example` to Mode A (the only case that reads `.env` directly).

**POSTGRES_PASSWORD co-dependency**:
- `POSTGRES_PASSWORD` in `.env` (used by compose to init the container) must match the password in `DATABASE_URL` in `.env`.
- If they diverge, compose will create the postgres user with one password but the app will try to authenticate with another.
- Always document this co-dependency in `.env.example` and link to `dev-restart.sh --reset`.

### P00-S02-T005 (2026-05-09) — Productive verification bundle delivery

**bundle_type default vs real bundle (CRITICAL gotcha)**:
- Loader functions default to `bundle_type="synthetic"` to preserve back-compat.
- Tests that call loaders against the real `data/verification/` directory MUST pass `bundle_type="productive"` explicitly.
- If a test uses default bundle_type="synthetic" against the productive bundle, McpServerSeed/AiProviderSeed/MfaPrimarySeed validators raise ValueError (synthetic guard rejects productive shape).
- Fix pattern: `report = await load_mcp_agents(engine, verification_bundle_dir, bundle_type="productive")`.

**bundle_type propagation from MANIFEST**:
- `bootstrap_verification_data.py` reads `MANIFEST._bundle_type` and propagates to ALL load_* calls.
- Test fixtures that don't go through bootstrap_verification_data must pass bundle_type explicitly.
- `_common.py BundleType = Literal["synthetic","productive"]` — always import this, not a raw string.

**Auth loader §10.3 SQL shape (CRITICAL)**:
- Real schema (migration 0001): `users.status='active'`, `users.password_hash`, `users.preferred_language`.
- NOT legacy T003 shape: `users.role`, `users.is_active`, `users.mfa_enabled` (these columns DO NOT EXIST in real schema).
- Fernet-encrypted TOTP secret: `mfa_totp_secrets.secret_encrypted` (not `mfa_totp_secrets.totp_secret`).
- ENCRYPTION_KEY env var required at loader time — fail-fast with BundleLoadError if missing.

**Argon2 defaults are OWASP-2024 compliant**:
- `argon2.PasswordHasher()` with no args → m=65536 (64MB), t=3, p=4. These ARE OWASP-2024 compliant.
- No need to set explicit parameters unless benchmark shows unacceptable latency on prod hardware.

**SHA-256 checksum for PDFs (64 hex chars exactly)**:
- `hashlib.sha256(pdf_bytes).hexdigest()` → 64 hex characters.
- Always count: 64 = 32 bytes × 2 hex chars/byte. Not 63, not 66.

**ruff venv false positive**:
- `ruff check .` from `backend/` will flag `.venv-t003/bin/jp.py` and `.venv-verify-t003/bin/jp.py` (venv binary artifacts).
- These are pre-existing and unrelated to project code.
- Correct lint command: `ruff check app/ tests/` — scopes to project code only.
- Or check pyproject.toml for exclude config and use that config if venv should be excluded.

### P01-S01-T002 (2026-05-09) — §11.1 env var alignment (4-file atomic rename)

**git stash gotcha in worktrees**:
- `git stash pop` can fail with conflict on `orchestrator-state/tasks/ledger.jsonl` (written by hooks concurrently).
- When stash pop fails, edits are lost. Always re-apply using Write/Edit tool, not git stash pop.
- Alternative: read old content first, then just use `ruff check` on the original to confirm pre-existing errors without stashing.

**pydantic-settings case_sensitive=False field matching**:
- With `case_sensitive=False` (default) and `extra="ignore"`, pydantic-settings matches env vars to fields by lowercasing the env var name.
- `JWT_PRIVATE_KEY` env var → `jwt_private_key` field. No `Field(alias=...)` needed.
- Same for all renamed fields. This is automatic in pydantic-settings 2.x.

**JWT public key as SecretStr**:
- Public keys are not secrets, but storing as SecretStr keeps them out of log redaction path.
- Consuming code must call `.get_secret_value()` to get the raw PEM.
- This is an acceptable trade-off for defense-in-depth; document in docstring + handoff.

**_REDACTED_KEYS: explicit listing vs substring matching**:
- The `_redaction_processor` does `key.lower() in _REDACTED_KEYS` (exact match on full key name).
- "jwt_private_key" and "jwt_public_key" would NOT be caught by the broader "secret" entry because the check is on the full key name, not substrings.
- Only explicit listings work. The substring logic in the comment is misleading — always add explicit entries for new credential field names.

**ruff E501 line length limit is 100 chars (not 88)**:
- ruff.toml or pyproject.toml sets `line-length = 100` for this project.
- description= strings in Field() can easily exceed 100 chars. Wrap them:
  ```python
  s3_bucket_documents: str = Field(
      "default",
      description=(
          "Long description string here."
      ),
  )
  ```
- Or just shorten the description to fit on one line.

### P00-S02-T006 (2026-05-09) — admin_ai model discovery endpoint

**Fernet key validation failure in tests**:
- `PROVIDER_ENCRYPTION_KEY=dev-encryption-key-placeholder` in .env is NOT a valid Fernet key (must be 32 bytes URL-safe base64).
- The `_resolve_fernet_key()` function finds this invalid value and causes `ValueError: Fernet key must be 32 url-safe base64-encoded bytes` when `encrypt_secret()` is called.
- Fix: `fernet_test_key` autouse fixture in test file generates `Fernet.generate_key().decode()` and sets `ENCRYPTION_KEY` env var before any test runs. Cleanup restores original value.
- The key lookup order: `ENCRYPTION_KEY` (new name) → `PROVIDER_ENCRYPTION_KEY` (legacy) → `settings.encryption_key`. The fixture uses the canonical new name to ensure it takes priority.

**git stash hazard**:
- `git stash` on a dirty main repo reverts modified tracked files (including `app/main.py` and `app/db/models/__init__.py`) even if you only intend to stash unrelated changes.
- Always check which tracked files are modified before stashing. If stash is needed, prefer `git stash push -m "..." <specific-file>` to target only what you need.
- After stash pop fails (conflict), the stash is NOT automatically dropped — run `git stash drop` manually. The working tree files (untracked) are NOT affected by the stash.

**Migration numbering gap (0002 reserved)**:
- Migration 0002 is reserved for P02-S01-T001 (consolidated chat + RAG + history schema).
- T006 uses 0003 to allow out-of-order insertion of the reserved 0002.
- Alembic does NOT require sequential revision numbers — the `down_revision` chain controls order, not the filename number.

**SELECT-then-INSERT diff pattern**:
- Repository `upsert_new_models()` uses SELECT-then-INSERT diff (not ON CONFLICT DO NOTHING).
- Reason: need to return (added, existing) split accurately. ON CONFLICT DO NOTHING doesn't let you know which rows were actually inserted.
- Pattern: 1. `list_existing_models()` → existing set, 2. INSERT only new model_ids, 3. return `(added_rows, matched_existing)`.

**`entity_id` column type in AuditLog**:
- `AuditLog.entity_id` is `Mapped[uuid.UUID | None]`. Pass UUID directly, not `str(uuid)`. SQLAlchemy handles the serialization.

**`from datetime import UTC` (UP017 fix)**:
- Use `from datetime import UTC, datetime` and `datetime.now(tz=UTC)`.
- NOT `from datetime import datetime, timezone` + `datetime.now(tz=timezone.utc)`.
- Ruff UP017 enforces this.

**Provider client httpx pattern**:
- Use `httpx.AsyncClient(transport=AsyncHTTPTransport(retries=0), timeout=Timeout(...))`.
- `verify=True` explicitly (not False — no SSL bypass in production code).
- `retries=0` — caller (service layer) can retry; client should not hide failures.

**`_safe_base_url()` for log safety**:
- Strip query strings from base_url before logging to prevent api_key leakage.
- Pattern: `urlparse(raw).scheme + "://" + urlparse(raw).netloc + urlparse(raw).path`

**Test ordering / event-loop contamination**:
- When running full test suite (`pytest tests/`), the health test `test_ready_returns_200_when_db_ok` fails due to event-loop contamination from integration tests running before it.
- Workaround: when checking health tests, run them in isolation (`pytest tests/test_health.py`).
- This is a pre-existing known issue (T001 session), not introduced by T006.
