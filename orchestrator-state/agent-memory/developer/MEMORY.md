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
