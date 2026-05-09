# developer agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/developer/archive/MEMORY.full.2026-05-09-221733.md`
- Original lines: 542
- Original SHA-256: `5b50ce10c3cd33cb7514f9432a50a5c87fd7047081682cd7b773d406d215f9d4`
- Compacted at: `2026-05-09-221733`
- When a detail is not present below, read the full archive before making assumptions.

## Current operating invariants
- Production work is DAG-only: `task_dag.mode` must be `explicit_dag`.
- `bootstrap_three_docs.py --refresh` preserves runtime by default; use `--reset-runtime-state` only for intentional destructive reset.
- Never edit generated `registry.json`, `runtime-state.json`, `task-dag.json`, or `execution-graph.json` directly.
- Scope every write by `CLAUDE_ACTIVE_TASK_ID` and `CLAUDE_TASK_PACK`.
- Touch only paths present in the active task pack `Write set` / `allowed_paths`.
- `docker-compose.yml`, `Dockerfile*`, `.env.example`, and `.github/workflows/**` require explicit task scope before editing.
- Propose discovered out-of-slice work with `/register-followup`; do not promote follow-ups automatically.

## Trailer vocabulary
- `OUTCOME`: `success|blocked|failed`
- `NEXT_STATUS`: `validator_tester_pending|blocked`
- Always read `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` before emitting trailers.

## High-signal preserved notes
- - These are the canonical names to use in `.env.example` and anywhere env vars for ports are needed.
- ### Logging pattern (bootstrap)
- ### Package version pinning (T001 + T002, confirmed 2026-05-08 npm registry)
- ## Implementation decisions
- - Used `frontend/src/.gitkeep` not `frontend/src/main.tsx` because: (a) task pack says "just the folder", (b) hook might block files outside write set if main.tsx was a full TS file.
- - `FRONT_PORT=5173` in .env.example matches Vite default; `dev-restart.profile.sh` had FRONT_PORT=5000 default in comments but that's from Flutter template, not React stack.
- - React Router v7: `react-router-dom` is thin wrapper over `react-router`. P01-S03-T001 must choose library mode (BrowserRouter) vs data mode (createBrowserRouter) intentionally.
- - Any `import { SomeType }` where `SomeType` is a TypeScript type must use `import { type SomeType }` or `import type { SomeType }`.
- - Error TS1484 "X is a type and must be imported using a type-only import".
- - `vitest.config.ts` must include the React plugin and `@` alias for test imports to resolve correctly.
- ## P00-S02-T001 (2026-05-09) — Docker Compose + Dockerfiles
- - Worker has no HTTP port → healthcheck always fails.
- - Task packs may reference outdated 1.27 — always verify with researcher.
- - In test files: always use `t('ns:key.nested')` form for cross-namespace assertions.
- - `structlog.contextvars.clear_contextvars()` in finally — always clean up.
- - `merge_contextvars` processor must be in structlog.configure() chain (already in T003's core/logging.py).
- - asyncpg raw exceptions are always wrapped by SQLAlchemy — you do NOT need to import asyncpg.
- - Bare Exception fallback is acceptable as last resort in /ready to ensure 503 never becomes 500.
- - Tests that probe real DB must set DATABASE_URL with correct credentials.
- - `sqlalchemy.exc.OperationalError(statement, params, orig)` — 3rd arg `orig` must be `BaseException`.
- - All provider/MCP credentials in fixtures MUST start with `synthetic-` to prevent accidental real key commit.
- - Common typo: counting wrong and getting 66 chars. Always `echo -n "<value>" | wc -c` to verify.
- - `0` = success (including "all tables missing" — table-tolerant in P00)
- ## Gotchas
- - All DAG successor tasks (T002, T003, T004) depend on this task being `done`. Don't unblock them until verify-slice + closer completes.
- - **`npm run build` is blocked without tsconfig.json**: The build script is `tsc -b && vite build`. Until tsconfig is added (T004 or later), `build` always fails. Do NOT use build as verify gate in T002/T003/T004.
- - Restoring `core_logging._configured = prev` alone is NOT sufficient — you must also clean up root logger handlers.
- **Test_ready_db_ok pre-existing auth failure**:
- - This failure exists in the T002 baseline (48 counted as baseline; this test was already failing).
- - All JSONB columns must use this dialect-specific import.
- - The relationship `"ClassName"` string form (deferred resolution) works without runtime import.
- - Module-level setup (alembic upgrade head) must use a SYNCHRONOUS autouse fixture that calls alembic as a subprocess, not an async fixture.
- - Track in follow-up FU to replace synthetic bundle with real fixtures.
- - `run_async_migrations` must use `async with engine.connect() as connection` then `await connection.run_sync(do_run_migrations)`.
- - `engine.dispose()` must be called in `run_async_migrations` after `run_sync` completes (inside `try...finally` ideally).
- - Logging configure call must happen BEFORE `from app.db.models import Base` (models trigger structlog setup).
- - Partial index must be created explicitly in migration (not via ORM) — partial indexes require `postgresql_where=` kwarg in `op.create_index()`.
- - Always drop child tables (FK side) before parent tables.
- **pydantic-settings env_file is cwd-relative (CRITICAL gotcha)**:
- - Real env vars (docker-compose, CI, shell exports) still take precedence over `.env` file.
- - DATABASE_URL contains a password → NEVER log the full value.
- - When compose maps `"5433:5432"` for postgres, host processes (uvicorn, pytest, alembic) must use `localhost:5433`.
- - Document both modes in `.env.example` as Mode A (native dev) and Mode B (in-compose). Mode B is overridden by docker-compose.yml env block; `.env` is not used there.
- - Default the `.env.example` to Mode A (the only case that reads `.env` directly).
- - `POSTGRES_PASSWORD` in `.env` (used by compose to init the container) must match the password in `DATABASE_URL` in `.env`.
- - Always document this co-dependency in `.env.example` and link to `dev-restart.sh --reset`.
- **bundle_type default vs real bundle (CRITICAL gotcha)**:
- - Tests that call loaders against the real `data/verification/` directory MUST pass `bundle_type="productive"` explicitly.
- - `bootstrap_verification_data.py` reads `MANIFEST._bundle_type` and propagates to ALL load_* calls.
- - Test fixtures that don't go through bootstrap_verification_data must pass bundle_type explicitly.
- - `_common.py BundleType = Literal["synthetic","productive"]` — always import this, not a raw string.
- - Always count: 64 = 32 bytes × 2 hex chars/byte. Not 63, not 66.
- **git stash gotcha in worktrees**:
- - When stash pop fails, edits are lost. Always re-apply using Write/Edit tool, not git stash pop.
- - Consuming code must call `.get_secret_value()` to get the raw PEM.
- - Only explicit listings work. The substring logic in the comment is misleading — always add explicit entries for new credential field names.
- **Fernet key validation failure in tests**:
- - `PROVIDER_ENCRYPTION_KEY=dev-encryption-key-placeholder` in .env is NOT a valid Fernet key (must be 32 bytes URL-safe base64).
- - The `_resolve_fernet_key()` function finds this invalid value and causes `ValueError: Fernet key must be 32 url-safe base64-encoded bytes` when `encrypt_secret()` is called.
- - Always check which tracked files are modified before stashing. If stash is needed, prefer `git stash push -m "..." <specific-file>` to target only what you need.
- - `retries=0` — caller (service layer) can retry; client should not hide failures.

## Original heading index
- # Developer Agent Memory — Hilo People
- ## Codebase patterns discovered
- ### Env variable naming
- ### `scripts/setup-from-scratch.sh`
- ### Backend module structure
- ### Logging pattern (bootstrap)
- ### Package version pinning (T001 + T002, confirmed 2026-05-08 npm registry)
- ## Implementation decisions
- ### P00-S01-T001 (2026-05-08)
- ### P00-S01-T002 (2026-05-08)
- ### P00-S01-T003 (2026-05-08) — Backend dep pack + core/
- ### P00-S01-T004 (2026-05-09) — Design tokens + editorial system
- ## P00-S02-T001 (2026-05-09) — Docker Compose + Dockerfiles
- ### P00-S01-T005 (2026-05-09) — i18n resources ES/EN/FR
- ### P00-S02-T002 (2026-05-09) — Health live/ready endpoints + request_id middleware
- ### P00-S02-T003 (2026-05-09) — Seed data + verification bundle
- ## Gotchas
- ### P00-S02-T004 (2026-05-09) — CWE-532 structlog frame-locals leak fix
- ### P01-S01-T001 (2026-05-09) — DB auth baseline (Alembic + migration 0001)
- ### P01-S01-T004 (2026-05-09) — pydantic-settings env_file absolute path fix
- ### P00-S02-T005 (2026-05-09) — Productive verification bundle delivery
- ### P01-S01-T002 (2026-05-09) — §11.1 env var alignment (4-file atomic rename)
- ### P00-S02-T006 (2026-05-09) — admin_ai model discovery endpoint

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/developer/archive/MEMORY.full.2026-05-09-221733.md`
