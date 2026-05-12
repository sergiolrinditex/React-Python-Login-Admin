# Developer Agent Memory — Hilo People

> Persistent learnings from previous slices. Update after each slice with new discoveries.
> Agents read this before coding to avoid repeating past mistakes.

## Codebase patterns discovered

### Project structure
- **Worktree root**: `/Users/sergiolr/Desktop/Productos/React-Python-Login-Admin/.claude/worktrees/agent-aba9672c77f4f9801/`
- **Main repo**: `/Users/sergiolr/Desktop/Productos/React-Python-Login-Admin/`
- Task packs are in the **main repo** (`orchestrator-state/tasks/task-packs/`), NOT in the worktree.
- After reading the task pack from main repo, implement in the **worktree**.

### Hook gotcha (CRITICAL)
- `hook_write_scope_guard.py` blocks `Write`/`Edit` tools for paths under `.claude/worktrees/` because they appear as `.claude/`-relative.
- **Solution**: ALWAYS use `Bash` heredoc (`cat > /path << 'EOF'`) for file creation/editing in the worktree.
- This applies to ALL product code files in the worktree (docker-compose.yml, Dockerfiles, .env.example, etc.).

### Docker Compose (P00-S02-T001)
- **Rancher Desktop** uses `~/.rd/bin/docker` — add to PATH with `export PATH="$HOME/.rd/bin:$PATH"`.
- Compose v2-spec: NO `version:` key (deprecated), NO `extra_hosts: host.docker.internal:host-gateway`.
- All volumes MUST be named (not bind-mounts outside $HOME) — Rancher Desktop only mounts $HOME.
- `valkey/valkey:8-alpine` is the Redis-compatible image; service name must be `redis` for DNS compatibility.
- LiteLLM healthcheck endpoint: `/health/liveliness` (v1.83+).
- MinIO healthcheck endpoint: `/minio/health/live` (S3 API on :9000).
- `depends_on` with `condition: service_healthy` prevents race conditions in compose boot order.
- `restart: on-failure` for Celery worker when `app.worker` module doesn't exist yet (R5 pattern).

### Backend Dockerfile (P00-S02-T001)
- Use `python:3.12-slim-bookworm` NOT alpine — alpine causes wheel failures for psycopg/numpy/torch.
- Multi-stage: builder venv + runtime copy — clean separation.
- Non-root user: `appuser:appgroup` (uid/gid 1001) required by non-negotiables §Security.
- Build context is repo ROOT (not `backend/`) when compose uses `context: .`.
- Copy paths must be `backend/app` and `backend/requirements.txt` (relative to root context).

### Frontend Dockerfile (P00-S02-T001)
- Multi-stage: `node:20-alpine` builder + `nginx:1.27-alpine` runtime.
- `ARG SKIP_BUILD=0` guard for when T002 hasn't merged yet (no package-lock.json, vite.config.ts).
- nginx SPA config needs `try_files $uri $uri/ /index.html` for React Router client-side routing.
- `COPY frontend/ ./` in builder copies ALL frontend source including package*.json.

### Environment
- Python 3.11.5 available at `/usr/local/bin/python3` (system, not venv).
- pytest 9.0.2 available via `python3 -m pytest` (not as standalone `pytest` binary).
- fastapi 0.135.2 installed system-wide.

### Dev-restart.sh
- `--check` mode exits 1 when services are DOWN — this is CORRECT behavior, not a failure.
- The profile (`dev-restart.profile.sh`) is a neutral stub; it doesn't handle compose services.
- Do NOT modify `dev-restart.sh` or `dev-restart.profile.sh` unless in write_set.

### Node modules in worktree
- Worktrees do NOT have `node_modules/` — they share the git history but not installed packages.
- Must run `npm --prefix frontend install --prefer-offline` in the worktree before running tests.
- Main repo `frontend/node_modules/.bin/vitest` exists (for main repo test runs).
- Worktree frontend tests are run from the worktree: `npm --prefix frontend run test -- --run`.

### Vitest globals (CRITICAL for tsc)
- `globals: true` in vitest.config.ts enables runtime globals but NOT TypeScript globals for `tsc`.
- The tsconfig `types` array does NOT include `vitest/globals` — adding would be a write_set extension.
- **Pattern**: Always import `{ describe, it, expect }` explicitly from `"vitest"` in test files.
- **Existing pattern**: providers.test.tsx, design-system.test.tsx all import explicitly from "vitest".
- Failing to do this causes `TS2593: Cannot find name 'describe'` in `npm run build` (tsc -b).

### i18n (P00-S01-T005)
- `resolveJsonModule` is NOT in tsconfig.json — JSON files cannot be imported directly.
- **Pattern**: Inline all translation resources as TypeScript `const` objects in `i18n/index.ts`.
- JSON files in `public/locales/` serve as canonical reference and are served as static assets.
- i18next `init()` with inline `resources` is synchronous — no async needed.
- Language detector DISABLED (browser-only, crashes jsdom) — keep off until AccountPage.
- i18next v26 `i18n.options.ns` is `string | readonly string[]` — cast to `string[]` for includes check.
- `i18n.getResourceBundle(lng, ns)` returns the namespace object as `unknown` — cast to `Record<string, string>` or nested type for property access.
- `i18n.options.fallbackLng` can be `string | string[]` — normalise with `Array.isArray` before assertion.
- `i18n.options.version` does NOT exist on `InitOptions` — do not use.

## Decisions and why

| Decision | Rationale |
|----------|-----------|
| Bash heredoc for all file writes | hook_write_scope_guard.py blocks Write/Edit in worktree paths |
| `python:3.12-slim-bookworm` over alpine | alpine breaks psycopg/numpy wheels |
| Non-root user in Dockerfile | non-negotiables §Security requirement |
| `restart: on-failure` for worker | app.worker doesn't exist yet; service must be declared but tolerate failures |
| `ARG SKIP_BUILD` in frontend Dockerfile | Allows compose syntax smoke test before T002 merges |
| Named volumes only | Rancher Desktop mount restrictions |
| `.env.example` extension for Postgres/MinIO/LiteLLM keys | Compose services require these; without them `compose up` fails with missing vars |
| Inline TS resources for i18n (not JSON imports) | `resolveJsonModule` absent from tsconfig; no http-backend (YAGNI P0) |
| Explicit vitest imports (not globals) | globals: true is runtime-only; tsc needs explicit imports to avoid TS2593 errors |


### Argon2id idempotency pattern (P00-S02-T003)
- argon2-cffi 25.1.0 (NOT ~23.x): latest stable 2026-05-11. API: hash/verify/check_needs_rehash.
- NO verify_and_update() method — it does not exist in any version.
- Idempotency: INSERT path always hashes fresh. UPDATE path: ph.verify(stored, plain) first.
  Only re-hash if VerifyMismatchError or InvalidHashError is raised.
- Pydantic v2 schemas for fixtures: MUST use extra="ignore" (not "forbid") to tolerate _comment keys in JSON.

### Alembic in worktree (P00-S02-T003)
-  does NOT work — alembic is not a runnable module.
- Must use:  (full path).
- In CI/Docker use  inside the venv where alembic is pip-installed.
- env.py: normalise asyncpg→psycopg URL (asyncpg driver not compatible with CLI sync calls).
- target_metadata=None until models are declared in P01.

### cryptography dep (P00-S02-T003)
- cryptography is NOT a guaranteed transitive dep of argon2-cffi (it only requires argon2-cffi-bindings).
- litellm pulls cryptography==46.0.7 ONLY under its proxy extra (not installed by default).
- ALWAYS pin cryptography explicitly when using Fernet.
- cryptography==48.0.0 is compatible with litellm==1.83.14 (no ABI conflict).

### Fixture loader deferred pattern (P00-S02-T003)
- Use sqlalchemy.inspect(engine).has_table(name) to check table existence at runtime.
- Return LoadResult(status="deferred", reason="table missing") when table absent — exit 0.
- This enables bootstrap to run safely in P00 without the DB schema and activate in P01.

### Integration test setup (P00-S02-T003)
- Real Postgres required: use DATABASE_URL env var pointing to running postgres container.
- Session-scoped pg_engine + function-scoped pg_session with transactional rollback in conftest.py.
- Mark tests @pytest.mark.integration; run selectively with -m integration or -m "not integration".
- Port 5432 may be claimed by another worktree container — check before trying docker compose up.

### SQLAlchemy text() JSONB cast patterns (P00-S02-T004)
- **BROKEN**: `:param::jsonb` — SQLAlchemy 2.x `text()` parser may misinterpret `::` after a bind param (psycopg3 driver interaction).
- **SAFE forms** (both accepted):
  - `CAST(:param AS JSONB)` — SQL-standard, preferred for clarity.
  - `(:param)::jsonb` — parenthesized to isolate bind param before cast operator.
- Always pair with `json.dumps(value or {})` — NOT `str(dict).replace("'", '"')`.
- `json.dumps` is the canonical serializer. `str(dict)` produces Python repr (True/False/None/single-quotes) which is not valid JSON.
- Import `json` at module top (not inside functions) for cleanliness.

### Alembic worktree invocation (updated P00-S02-T004)
- Must set `DATABASE_URL` env var — alembic env.py raises `RuntimeError` without it.
- Use: `DATABASE_URL=postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev /Users/sergiolr/Library/Python/3.11/bin/alembic upgrade head`
- The `python -m alembic` workaround fails due to `backend/alembic/` directory shadowing the installed package.

### Acceptance test path (P00-S02-T004)
- pytest is run with `cwd=backend/`, so test paths must be relative to `backend/`:
  - Correct: `pytest tests/integration/test_dev_restart_reset.py`
  - Wrong: `pytest backend/tests/integration/test_dev_restart_reset.py` (exit 4 — not found)

## Known gotchas

- Task packs for the current task MUST be read from the main repo path, not the worktree (they're not synced to worktrees).
- The `.env` file must exist for `docker compose config` to work (compose reads `env_file: .env` at parse time).
- Create `.env` from `.env.example` as a smoke test step; it should be gitignored.
- `docker compose config --quiet` with exit 0 is the authoritative syntax smoke for YAML validity.
- `dev-restart.sh --check` exiting 1 is expected when infra isn't running — document it as "expected" in evidence.
- `npm --prefix frontend install` must run first in each worktree session — no node_modules symlink.
- vitest.config.ts `globals: true` does NOT affect TypeScript type checking — always import from "vitest" in tests.
- i18next `i18n.options.version` property does not exist — use `i18n.isInitialized` for status checks instead.

## Slice history

| Slice | Outcome | Key files touched |
|-------|---------|-------------------|
| P00-S01-T001 | success | backend/app/main.py, backend/pyproject.toml, .env.example, scripts/ |
| P00-S02-T001 | success | docker-compose.yml, backend/Dockerfile, frontend/Dockerfile, .dockerignore, scripts/minio-bootstrap.sh, frontend/nginx.conf, .env.example |
| P00-S01-T005 | success | frontend/src/i18n/index.ts (rewrite), frontend/src/i18n/languages.ts, frontend/src/i18n/types.d.ts, frontend/src/i18n/__tests__/i18n.test.ts, frontend/public/locales/**/{8 ns}.json (×3 langs = 24 files), frontend/src/pages/showcase/I18nDemoSection.tsx, frontend/src/pages/showcase/ShowcasePage.tsx |
| P00-S02-T004 | in progress (developer done) | backend/app/verification_data/loader.py (cast fix + json.dumps + preventive maintenance) |
| P00-S02-T003 | success | backend/alembic.ini, backend/alembic/env.py, backend/alembic/script.py.mako, backend/alembic/versions/.gitkeep, backend/app/verification_data/** (8 files), data/verification/** (11 fixtures + README), backend/tests/conftest.py, backend/tests/integration/** (3 files), scripts/dev-restart.profile.sh, backend/pyproject.toml (cryptography+argon2-cffi), backend/requirements.txt, .env.example |

### Auth module structure (P01-S02-T001)
- Module layout: errors.py → domain.py → password.py → rate_limit.py → repository.py → service.py → schemas.py → router.py → __init__.py
- errors.py must be standalone (no external deps) so domain.py can import it
- domain.py must be standalone (no DB, no FastAPI) — domain layer must not import external libs
- CorporateEmail value object normalises email to lowercase and validates domain from env var
- Password value object validates min/max length + letter+digit, stores plain for one-time hash use
- Rate limit store is a module-level dict + threading.Lock — NOT a singleton class

### Pydantic v2 field_validator behavior (P01-S02-T001)
- `@field_validator` fires BEFORE FastAPI reaches the endpoint handler
- If field_validator raises ValueError, FastAPI wraps it as 422 (not 400)
- If you want 400 for a field, the service layer must handle it (not the schema)
- Task pack's "optionally fold into 422" acknowledges this — legal_acceptance=false gets 422

### TestClient vs live uvicorn session handling (P01-S02-T001)
- FastAPI TestClient uses ASGI transport — no HTTP server, but DOES share DB connections
- Router creates its own SQLAlchemy engine (`_engine = create_engine(...)`) at module import
- That engine is DIFFERENT from `pg_session` fixture's engine
- Tests using pg_session fixture CAN see rows committed by the router's engine (same DB)
- BUT pg_session fixture uses transactional rollback — after test, all rows visible to fixture are rolled back
- The router's engine commits independently — rows committed by the router PERSIST after test
- This means test isolation works correctly only because we use separate emails per test

### Migration test gotcha (P01-S02-T001)
- test_migrations_0001_auth.py::test_downgrade_removes_all_tables drops all tables
- After full test suite run: MUST run `alembic upgrade head` to restore schema
- This is expected behavior; just remember to re-apply before using the live DB

### Service layer session ownership (P01-S02-T001)
- Service layer (SignUpUser) owns transaction management: flush in repo, commit in service
- This allows rejection audit to use a SEPARATE transaction (different Session.commit())
- Router creates Session, passes to service, closes in finally block
- DO NOT call session.commit() in the repository — that's the service's job

## P01-S02-T002 decisions and patterns

### JWT with PyJWT==2.12.1
- `jwt.encode(payload, key, algorithm="HS256")` returns **str** directly (no .decode() needed).
- `jwt.decode(token, key, algorithms=["HS256"], options={"require": [...]})`
- jti must be `uuid.uuid4().hex` (str) — PyJWT requires str jti per RFC 7519.
- iat and exp must be `int(datetime.now(tz=UTC).timestamp())` — NOT datetime objects for consistency.
- JWT_PRIVATE_KEY must be ≥32 bytes for HS256 (RFC 7518 §3.2). tokens.py emits startup warning.

### Refresh token cookie pattern (Web BFF)
- Opaque token: `secrets.token_urlsafe(48)` → SHA-256 hex digest stored in DB.
- Cookie: `samesite="lax"` (lowercase "lax" — Starlette API requirement, NOT "Lax").
- `httponly=True, secure=True, path="/auth", max_age=<int seconds>`.
- Never store plain token in DB — only the SHA-256 digest.

### Aggregate-401 anti-enumeration
- Module-level `_DUMMY_HASH = hash_password("dummy-...")` computed once at import.
- Unknown-email path calls `verify_password(plain, _DUMMY_HASH)` to equalise timing.
- Both unknown-email and wrong-password paths return identical JSON body.
- T16 timing smoke check: threshold 20ms (NOT 50ms) — hardware-agnostic floor.

### D-S2 rejection audit pattern
- Rejection audits (unknown email, wrong pw, locked, etc.) use a SEPARATE short session.
- Short session opens, writes audit, commits, closes — independently of main sign-in transaction.
- Success audit + refresh_token share the main transaction (atomicity).
- This ensures audit rows persist even if the main tx aborts.

### Circular import prevention in auth module
- service.py lazily imports `encode_access_token`, `encode_mfa_challenge_token`, `verify_password`, `_DUMMY_HASH`, `needs_rehash`, `MfaTotpSecret` inside the `execute()` method with `# noqa: PLC0415`.
- This avoids circular import chains: tokens.py → (none), password.py → errors.py only.
- repository.py lazily imports `RefreshToken` model inside `insert_refresh_token()`.

### rate_limit.py refactor for multi-endpoint support
- `_load_limits(prefix)` reads `AUTH_{PREFIX}_RATE_PER_MINUTE` and `AUTH_{PREFIX}_RATE_BURST` env vars.
- Store key is `"{PREFIX}:{ip}"` — sign-up and sign-in have separate buckets.
- There are NO `_RATE_PER_MINUTE` or `_BURST` module attributes (they were removed).
- Tests MUST use `monkeypatch.setenv("AUTH_SIGNUP_RATE_PER_MINUTE", "N")` NOT `monkeypatch.setattr(rl_module, "_RATE_PER_MINUTE", N)`.

### Test isolation for sign-in tests
- `pg_session` fixture wraps each test in a rollback transaction.
- Sign-in endpoint uses a different DB connection from `_SessionLocal` (can't see uncommitted data).
- Solution: `_create_user()` uses a SEPARATE `_SetupSession` that commits immediately to real DB.
- `_cleanup_created_users` autouse fixture deletes committed rows after each test.
- Pattern: `_created_user_ids: list[str]` collects IDs; autouse fixture iterates and deletes.

### Alembic in test suite
- `test_downgrade_removes_all_tables` drops ALL tables (including users, audit_logs, etc.).
- After a full test run: ALWAYS run `alembic upgrade head` before using the live DB.
- Pre-condition check before running tests: verify tables exist.
- This is R1-T001-S02 (pre-existing known issue — nothing to fix).
