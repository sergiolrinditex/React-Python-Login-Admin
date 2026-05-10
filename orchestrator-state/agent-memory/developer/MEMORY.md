# developer agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/developer/archive/MEMORY.full.2026-05-10-044634.md`
- Original lines: 252
- Original SHA-256: `10cb6778798a498b11a26b98414015a7926818bb11bdf05125516a6dfa97573b`
- Compacted at: `2026-05-10-044634`
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
- ## Current operating invariants
- - Production work is DAG-only: `task_dag.mode` must be `explicit_dag`.
- - `bootstrap_three_docs.py --refresh` preserves runtime by default; use `--reset-runtime-state` only for intentional destructive reset.
- - Never edit generated `registry.json`, `runtime-state.json`, `task-dag.json`, or `execution-graph.json` directly.
- - Scope every write by `CLAUDE_ACTIVE_TASK_ID` and `CLAUDE_TASK_PACK`.
- - Touch only paths present in the active task pack `Write set` / `allowed_paths`.
- - `docker-compose.yml`, `Dockerfile*`, `.env.example`, and `.github/workflows/**` require explicit task scope before editing.
- - Propose discovered out-of-slice work with `/register-followup`; do not promote follow-ups automatically.
- ## Trailer vocabulary
- - `OUTCOME`: `success|blocked|failed`
- - `NEXT_STATUS`: `validator_tester_pending|blocked`
- - Always read `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` before emitting trailers.
- - - These are the canonical names to use in `.env.example` and anywhere env vars for ports are needed.
- - ### Logging pattern (bootstrap)
- - ### Package version pinning (T001 + T002, confirmed 2026-05-08 npm registry)
- - ## Implementation decisions
- - - Used `frontend/src/.gitkeep` not `frontend/src/main.tsx` because: (a) task pack says "just the folder", (b) hook might block files outside write set if main.tsx was a full TS file.
- - - `FRONT_PORT=5173` in .env.example matches Vite default; `dev-restart.profile.sh` had FRONT_PORT=5000 default in comments but that's from Flutter template, not React stack.
- - - React Router v7: `react-router-dom` is thin wrapper over `react-router`. P01-S03-T001 must choose library mode (BrowserRouter) vs data mode (createBrowserRouter) intentionally.
- - - Any `import { SomeType }` where `SomeType` is a TypeScript type must use `import { type SomeType }` or `import type { SomeType }`.
- - - Error TS1484 "X is a type and must be imported using a type-only import".
- - - `vitest.config.ts` must include the React plugin and `@` alias for test imports to resolve correctly.
- - ## P00-S02-T001 (2026-05-09) — Docker Compose + Dockerfiles
- - - Worker has no HTTP port → healthcheck always fails.
- - - Task packs may reference outdated 1.27 — always verify with researcher.
- - - In test files: always use `t('ns:key.nested')` form for cross-namespace assertions.
- - - `structlog.contextvars.clear_contextvars()` in finally — always clean up.
- - - `merge_contextvars` processor must be in structlog.configure() chain (already in T003's core/logging.py).
- - - asyncpg raw exceptions are always wrapped by SQLAlchemy — you do NOT need to import asyncpg.
- - - Bare Exception fallback is acceptable as last resort in /ready to ensure 503 never becomes 500.
- - - Tests that probe real DB must set DATABASE_URL with correct credentials.
- - - `sqlalchemy.exc.OperationalError(statement, params, orig)` — 3rd arg `orig` must be `BaseException`.
- - - All provider/MCP credentials in fixtures MUST start with `synthetic-` to prevent accidental real key commit.
- - - Common typo: counting wrong and getting 66 chars. Always `echo -n "<value>" | wc -c` to verify.
- - - `0` = success (including "all tables missing" — table-tolerant in P00)
- - ## Gotchas
- - - All DAG successor tasks (T002, T003, T004) depend on this task being `done`. Don't unblock them until verify-slice + closer completes.
- - - **`npm run build` is blocked without tsconfig.json**: The build script is `tsc -b && vite build`. Until tsconfig is added (T004 or later), `build` always fails. Do NOT use build as verify gate in T002/T003/T004.
- - - Restoring `core_logging._configured = prev` alone is NOT sufficient — you must also clean up root logger handlers.
- - **Test_ready_db_ok pre-existing auth failure**:
- - - This failure exists in the T002 baseline (48 counted as baseline; this test was already failing).
- - - All JSONB columns must use this dialect-specific import.
- - - The relationship `"ClassName"` string form (deferred resolution) works without runtime import.
- - - Module-level setup (alembic upgrade head) must use a SYNCHRONOUS autouse fixture that calls alembic as a subprocess, not an async fixture.
- - - Track in follow-up FU to replace synthetic bundle with real fixtures.
- - - `run_async_migrations` must use `async with engine.connect() as connection` then `await connection.run_sync(do_run_migrations)`.
- - - `engine.dispose()` must be called in `run_async_migrations` after `run_sync` completes (inside `try...finally` ideally).
- - - Logging configure call must happen BEFORE `from app.db.models import Base` (models trigger structlog setup).
- - - Partial index must be created explicitly in migration (not via ORM) — partial indexes require `postgresql_where=` kwarg in `op.create_index()`.
- - - Always drop child tables (FK side) before parent tables.
- - **pydantic-settings env_file is cwd-relative (CRITICAL gotcha)**:
- - - Real env vars (docker-compose, CI, shell exports) still take precedence over `.env` file.
- - - DATABASE_URL contains a password → NEVER log the full value.
- - - When compose maps `"5433:5432"` for postgres, host processes (uvicorn, pytest, alembic) must use `localhost:5433`.
- - - Document both modes in `.env.example` as Mode A (native dev) and Mode B (in-compose). Mode B is overridden by docker-compose.yml env block; `.env` is not used there.
- - - Default the `.env.example` to Mode A (the only case that reads `.env` directly).
- - - `POSTGRES_PASSWORD` in `.env` (used by compose to init the container) must match the password in `DATABASE_URL` in `.env`.
- - - Always document this co-dependency in `.env.example` and link to `dev-restart.sh --reset`.
- - **bundle_type default vs real bundle (CRITICAL gotcha)**:
- - - Tests that call loaders against the real `data/verification/` directory MUST pass `bundle_type="productive"` explicitly.
- - - `bootstrap_verification_data.py` reads `MANIFEST._bundle_type` and propagates to ALL load_* calls.
- - - Test fixtures that don't go through bootstrap_verification_data must pass bundle_type explicitly.
- - - `_common.py BundleType = Literal["synthetic","productive"]` — always import this, not a raw string.
- - - Always count: 64 = 32 bytes × 2 hex chars/byte. Not 63, not 66.
- - **git stash gotcha in worktrees**:
- - - When stash pop fails, edits are lost. Always re-apply using Write/Edit tool, not git stash pop.
- - - Consuming code must call `.get_secret_value()` to get the raw PEM.
- - - Only explicit listings work. The substring logic in the comment is misleading — always add explicit entries for new credential field names.
- - **Fernet key validation failure in tests**:
- - - `PROVIDER_ENCRYPTION_KEY=dev-encryption-key-placeholder` in .env is NOT a valid Fernet key (must be 32 bytes URL-safe base64).
- - - The `_resolve_fernet_key()` function finds this invalid value and causes `ValueError: Fernet key must be 32 url-safe base64-encoded bytes` when `encrypt_secret()` is called.
- - - Always check which tracked files are modified before stashing. If stash is needed, prefer `git stash push -m "..." <specific-file>` to target only what you need.
- - - `retries=0` — caller (service layer) can retry; client should not hide failures.
- - Applied UNCONDITIONALLY in both verbose=True and verbose=False branches. The verbose=False root is already at WARNING, but the explicit pin is defense-in-depth (R2 risk: future root level change).
- - Module root: `frontend/src/features/admin_ai/` (underscore, not hyphen — matches backend module name and registry write_set)
- - Return `{ ok: true, value: T } | { ok: false, error: E }` — never throw across layer boundaries
- - Log: event, truncated provider_id (first 8 chars only), request_id, latency_ms — NEVER Authorization header value
- - No `<BrowserRouter>` — always `createBrowserRouter` + `RouterProvider`
- - Existing keys must be preserved verbatim — test checks `esAdminAi.models.title === 'Modelos LiteLLM'`
- - `.claude/orchestrator-contract.json`

## Original heading index
- # developer agent memory
- ## Full history archive
- ## Current operating invariants
- ## Trailer vocabulary
- ## High-signal preserved notes
- ## P00-S02-T009 (2026-05-10) — httpx logger suppression (CWE-532 third-layer)
- ## Original heading index
- ## P00-S02-T007 (2026-05-10) — AdminAiModelsPage discover wizard UI (first feature module)
- ### Feature module pattern established
- ### Zod v4 UUID validation
- ### API client Result pattern
- ### React Router v7 route addition pattern
- ### i18n extension pattern (T007)
- ### fetch mock pattern in Vitest
- ### Design-token enforcer in feature modules
- ### Linting note
- ## Canonical references
- ## P00-S02-T011 (2026-05-10) — dev .env ENCRYPTION_KEY hygiene
- ### Key patterns
- ## P00-S02-T010 (2026-05-10) — admin_ai seed loader column mismatch fix
- ### Hook write scope guard gotcha in worktrees
- ### Seed loader vs seed schema distinction
- ### Real UNIQUE constraint location matters
- ### auth_type mapping rule
- ### provider_id cross-phase tracking
- ### encrypt_secret import path
- ### Fernet key for tester (CRITICAL — R1)
- ### SQLAlchemy echo=True leaks SQL parameters (pre-existing CWE-532 gap, out of scope)
- ### alembic upgrade head in integration tests
- ### Test cleanup pattern for seed tests

## P01-S01-T005 (2026-05-10) — Alembic migration chain insert + asyncpg INET

### Alembic chain insert (inserting revision between two existing revisions)

When inserting a new revision (0002) between two existing ones (0001 and 0003 both branching from 0001):
- If new revision 0002 has `down_revision="0001"` and existing 0003 also has `down_revision="0001"` → TWO HEADS → `alembic upgrade head` FAILS.
- FIX: update the child (0003) `down_revision` from "0001" to "0002" → single linear chain 0001→0002→0003.
- If the DB was stamped at 0003 (without ever applying 0002), you must `alembic stamp 0001` then `alembic upgrade head` to apply the full chain. Running `alembic upgrade head` from 0003 is a no-op (already at head); running `alembic downgrade -1` from 0003 goes to 0002 without ever having run 0002's upgrade.
- WRITE_SET_DRIFT: updating child revision `down_revision` is necessary even if the child migration is outside the declared write set. Document in handoff as WRITE_SET_DRIFT.

### asyncpg INET column decode (critical)
- asyncpg 0.31.0 returns `ipaddress.IPv4Address` objects for INET columns (not `str`) when `native_inet_types` is active (default).
- INSERT with plain `str` like `'192.168.1.1'` is fine — `inet_encode` accepts str.
- SELECT assertions MUST use `str(row.ip)` or compare with `ipaddress.IPv4Address(...)`.
- ORM annotation `Mapped[str | None]` is runtime-safe (SQLAlchemy does not enforce annotations). Keep for simplicity.
- `native_inet_types=False` on `create_async_engine(...)` would force str returns everywhere — but this is a write to `db.py` which may be outside write set. Document trade-off.

### PostgreSQL 18 `information_schema.columns` for INET
- PG18 reports `data_type='inet'` for INET columns in `information_schema.columns`.
- Older PG versions may report `data_type='USER-DEFINED', udt_name='inet'`.
- Test assertion: `assert data_type == 'inet' OR udt_name == 'inet'` to be version-agnostic.

### Test 2 (round-trip) design
- Downgrade 0003→0002 removes AI tables but KEEPS audit_logs compliance cols (they're at 0002).
- Downgrade 0002→0001 removes compliance cols. Row preserved with §10.3 shape.
- Upgrade 0001→0002→0003: compliance cols re-added. Pre-existing rows get NULL (no DEFAULT).
- Do NOT check for NULL at 0002 state (after only one downgrade from 0003) — cols still present.

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/developer/archive/MEMORY.full.2026-05-10-044634.md`

## P00-S02-T011 (2026-05-10) — secret hygiene in bash commands (debugger lesson)
- The PostToolUse hook `hook_update_ledger.py` records EVERY Bash command verbatim to `orchestrator-state/tasks/ledger.jsonl`, which is git-tracked. NEVER paste a secret as a literal in a bash command — Fernet keys, JWT secrets, API keys, passwords. Three lines pasting `ENCRYPTION_KEY=...` in T011 leaked the master key into a tracked file; debugger had to rotate the key + redact the ledger.
- Allowed patterns when handling secrets:
  1. `python3 -c "..."` heredoc that GENERATES the secret AND writes to file — the literal lives only inside python, the bash command captured is the heredoc text itself (no resolved value).
  2. `Edit` tool against `.env` / `.env.local` — diffs are not captured verbatim by the bash ledger.
  3. Shell command-substitution: `KEY=$(python3 -c '...')` — ledger captures the `$(...)` syntax, not the resolved value.
- Forbidden patterns: `EXPORT KEY=<literal>`, `cat > .env <<EOF\nENCRYPTION_KEY=<literal>\nEOF`, any echo or print of full secret to stdout. Verification steps must use masked form (`****<last4>`).
- Side fix: `scripts/dev-restart.profile.sh` no longer persists the Fernet key to `orchestrator-state/dev-logs/encryption-key.runtime`. The blast radius is now the dev-restart shell process and the spawned uvicorn (pydantic-settings reads ENCRYPTION_KEY from `.env` directly).
- `.gitignore` now covers `orchestrator-state/dev-logs/*` (except `.gitkeep`) so any future runtime cache cannot accidentally be `git add`-ed.
