# developer agent memory

Compact operational memory. No history was deleted.

## Full history archive
- Original full file: `orchestrator-state/agent-memory/developer/archive/MEMORY.full.2026-05-13-182225.md`
- Original lines: 868
- Original SHA-256: `8c9e5ef8e73bb58924f19d42ea68d3fc9cfea8aac72b881c53f144ea52700c6a`
- Compacted at: `2026-05-13-182225`
- When a detail is not present below, read the full archive before making assumptions.

## Current operating invariants
- Production work is DAG-only: `task_dag.mode` must be `explicit_dag`.
- `bootstrap_source_of_truth.py --refresh` preserves runtime by default; use `--reset-runtime-state` only for intentional destructive reset.
- Never edit generated `registry.json`, `runtime-state.json`, `task-dag.json`, or `execution-graph.json` directly.
- Scope every write by `CLAUDE_ACTIVE_TASK_ID` and `CLAUDE_TASK_PACK`.
- Touch only paths present in the DAG task pack `Write set` / `allowed_paths`.
- `docker-compose.yml`, `Dockerfile*`, `.env.example`, and `.github/workflows/**` require explicit task scope before editing.
- Propose discovered out-of-slice work with `/register-followup`; do not promote follow-ups automatically.

## Trailer vocabulary
- `OUTCOME`: `success|blocked|failed`
- `NEXT_STATUS`: `validator_tester_pending|blocked`
- Always read `.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>` before emitting trailers.

## P02-S05-T004 notes (2026-05-13)
- **`.claude/` write guard**: All writes to `.claude/bin/tests/` are blocked by `hook_write_scope_guard.py` during app execution. For orchestrator-maintenance slices, use `CLAUDE_ALLOW_STATIC_CONFIG_WRITES=1` env var prefix in Bash (not in Write tool — use `Bash` with Python to write the content).
- **Merge topology**: When git PRs merge non-linearly, `git log --oneline` may show commits out of chronological order. Check `git log HEAD..origin/main` to confirm whether HEAD == origin/main, not just the log order.
- **Write tool blocked for .claude/**: Always use `CLAUDE_ALLOW_STATIC_CONFIG_WRITES=1 python3 << 'EOF'` heredoc pattern for writing to `.claude/` directories during maintenance slices. The `Write` tool will be blocked by the hook.
- **Pre-existing test failures**: `test_minireact_source_docs_bootstrap_without_flutter_tables` fails due to P02 DAG count >20. Pre-existing; don't confuse with slice regressions.
- **Sentinel pattern (Option A)**: Use subprocess pytest with node IDs pinned as strings; `_PINNED: tuple[str, ...]` with cwd=REPO resolved via `Path(__file__).resolve().parents[3]`.

## High-signal preserved notes
- ### Hook gotcha (CRITICAL)
- - **Solution**: ALWAYS use `Bash` heredoc (`cat > /path << 'EOF'`) for file creation/editing in the worktree.
- - This applies to ALL product code files in the worktree (docker-compose.yml, Dockerfiles, .env.example, etc.).
- - All volumes MUST be named (not bind-mounts outside $HOME) — Rancher Desktop only mounts $HOME.
- - `valkey/valkey:8-alpine` is the Redis-compatible image; service name must be `redis` for DNS compatibility.
- - `restart: on-failure` for Celery worker when `app.worker` module doesn't exist yet (R5 pattern).
- ### Backend Dockerfile (P00-S02-T001)
- - Use `python:3.12-slim-bookworm` NOT alpine — alpine causes wheel failures for psycopg/numpy/torch.
- - Multi-stage: builder venv + runtime copy — clean separation.
- - Copy paths must be `backend/app` and `backend/requirements.txt` (relative to root context).
- ### Frontend Dockerfile (P00-S02-T001)
- - Multi-stage: `node:20-alpine` builder + `nginx:1.27-alpine` runtime.
- - `--check` mode exits 1 when services are DOWN — this is CORRECT behavior, not a failure.
- - Do NOT modify `dev-restart.sh` or `dev-restart.profile.sh` unless in write_set.
- - Must run `npm --prefix frontend install --prefer-offline` in the worktree before running tests.
- - `globals: true` in vitest.config.ts enables runtime globals but NOT TypeScript globals for `tsc`.
- - The tsconfig `types` array does NOT include `vitest/globals` — adding would be a write_set extension.
- - **Pattern**: Always import `{ describe, it, expect }` explicitly from `"vitest"` in test files.
- ## Decisions and why
- | Decision | Rationale |
- | Non-root user in Dockerfile | non-negotiables §Security requirement |
- | `restart: on-failure` for worker | app.worker doesn't exist yet; service must be declared but tolerate failures |
- | `ARG SKIP_BUILD` in frontend Dockerfile | Allows compose syntax smoke test before T002 merges |
- | `.env.example` extension for Postgres/MinIO/LiteLLM keys | Compose services require these; without them `compose up` fails with missing vars |
- | Explicit vitest imports (not globals) | globals: true is runtime-only; tsc needs explicit imports to avoid TS2593 errors |
- - Idempotency: INSERT path always hashes fresh. UPDATE path: ph.verify(stored, plain) first.
- - Pydantic v2 schemas for fixtures: MUST use extra="ignore" (not "forbid") to tolerate _comment keys in JSON.
- - Must use:  (full path).
- - ALWAYS pin cryptography explicitly when using Fernet.
- - Use sqlalchemy.inspect(engine).has_table(name) to check table existence at runtime.
- - This enables bootstrap to run safely in P00 without the DB schema and activate in P01.
- - Always pair with `json.dumps(value or {})` — NOT `str(dict).replace("'", '"')`.
- - Must set `DATABASE_URL` env var — alembic env.py raises `RuntimeError` without it.
- - pytest is run with `cwd=backend/`, so test paths must be relative to `backend/`:
- - The worktree has the OLD code — the fix lives in the MAIN REPO. Always read the main repo paths when continuing/closing a tooling fix slice in a worktree continuation session.
- - Hard-fail (`fail "..."`) is always preferred over warn-only (`warn "..."; return 0`) for seed steps once the blocking issue is resolved. Silent-pass after warn is an anti-pattern per non-negotiables §Error handling.
- ## P02-S06-T003 — POSIX sh sidecar patterns
- - `minio/mc:latest` uses Alpine BusyBox `/bin/sh` — shebang `#!/bin/sh`, `set -eu` (NOT `set -euo pipefail`), no `[[`, no `local`, no arrays.
- - Portable env var validation without bashisms: `eval "val=\${$1:-}"` inside a `require_env()` function. POSIX `sh` has no `${!varname}` indirect expansion.
- - `mc alias set` + `mc mb --ignore-existing` are stable mc commands since 2022+. Flag `--ignore-existing` exits 0 when bucket already exists → idempotency.
- - Retry loop (5×2s) around `mc alias set`: compose `depends_on: service_healthy` does not guarantee MinIO S3 API is fully up — only that the `/minio/health/live` healthcheck passes. Small warm-up window remains. Retry inside the script absorbs it without looping the container.
- - Never echo MINIO_ROOT_PASSWORD: redirect `mc alias set` stdout+stderr to `/dev/null 2>&1`. Pass creds as positional args, not env vars printed in BEFORE log.
- - Endpoint `http://minio:9000` is literal (docker internal network). Not configurable per task pack §7.1 — over-engineering if made into a variable.
- - `mc alias set local`: alias name `local` is ephemeral inside the one-shot container; stored in `/root/.mc/config.json` inside container, discarded on exit.
- - Log convention for shell sidecars: `log()` → stdout `==> msg`; `warn()`/`fail()` → stderr. Matches `dev-restart.profile.sh` + `setup-from-scratch.sh` style.
- ## Known gotchas
- - Task packs for the current task MUST be read from the main repo path, not the worktree (they're not synced to worktrees).
- - The `.env` file must exist for `docker compose config` to work (compose reads `env_file: .env` at parse time).
- - Create `.env` from `.env.example` as a smoke test step; it should be gitignored.
- - `npm --prefix frontend install` must run first in each worktree session — no node_modules symlink.
- - vitest.config.ts `globals: true` does NOT affect TypeScript type checking — always import from "vitest" in tests.
- | Slice | Outcome | Key files touched |
- | P02-S04-T001 | success | backend/app/rag/{__init__,errors,schemas,retriever}.py (NEW), backend/tests/ai/{__init__,conftest,test_rag_retriever}.py (NEW) — 10/10 smoke tests PASS |
- | P00-S01-T001 | success | backend/app/main.py, backend/pyproject.toml, .env.example, scripts/ |
- | P00-S02-T001 | success | docker-compose.yml, backend/Dockerfile, frontend/Dockerfile, .dockerignore, scripts/minio-bootstrap.sh, frontend/nginx.conf, .env.example |
- | P01-S02-T009 | developer done (pending validator+tester+verify-slice) | scripts/gen-dev-secrets.sh (NEW), scripts/setup-from-scratch.sh (+15 LOC), .env.example (comments) |
- - WRITE_SET_DRIFT: `tests/ai/__init__.py` + `tests/ai/conftest.py` are outside declared write_set but required as intra-test helpers — same approved pattern as T002/T004/T007.
- - errors.py must be standalone (no external deps) so domain.py can import it
- - domain.py must be standalone (no DB, no FastAPI) — domain layer must not import external libs
- - If you want 400 for a field, the service layer must handle it (not the schema)
- ### Migration test gotcha (P01-S02-T001)
- - After full test suite run: MUST run `alembic upgrade head` to restore schema
- ## P01-S02-T002 decisions and patterns
- - jti must be `uuid.uuid4().hex` (str) — PyJWT requires str jti per RFC 7519.
- - iat and exp must be `int(datetime.now(tz=UTC).timestamp())` — NOT datetime objects for consistency.
- - JWT_PRIVATE_KEY must be ≥32 bytes for HS256 (RFC 7518 §3.2). tokens.py emits startup warning.
- - Never store plain token in DB — only the SHA-256 digest.
- - Success audit + refresh_token share the main transaction (atomicity).
- - Tests MUST use `monkeypatch.setenv("AUTH_SIGNUP_RATE_PER_MINUTE", "N")` NOT `monkeypatch.setattr(rl_module, "_RATE_PER_MINUTE", N)`.
- - After a full test run: ALWAYS run `alembic upgrade head` before using the live DB.
- - Never use `sed -i` for in-place .env edits — BSD macOS requires `sed -i ''` (empty backup arg), GNU accepts `sed -i`. Always use: `awk ... "$ENV_PATH" > "$tmp" && mv "$tmp" "$ENV_PATH"`.
- - NEVER use `set -x` in scripts that handle secrets (xtrace prints every expansion to stderr).
- - Log only `len=${#VAR}` (shell string length), never `echo "$VAR"`.
- - Worktree vs main-repo: the script resolves ROOT_DIR at runtime so it works in worktrees, CI, and sandbox temp dirs.
- ### Idempotency contract for provisioners
- - Rule: running the script twice must produce `changed=0` on the second run.
- ## P01-S02-T010 — Bootstrap preservation framework patterns
- - `Write` / `Edit` tools are blocked for paths under `.claude/` during app-building slices UNLESS `CLAUDE_ALLOW_STATIC_CONFIG_WRITES=1` is in the environment.
- - BUT: the env var must be in the CURRENT BASH SHELL, not a previous one. The tools run in isolated shell calls.
- ### Bootstrap test pattern (canonical)
- - Test file: `_BIN = Path(__file__).resolve().parent.parent` + `sys.path.insert(0, str(_BIN))` + `import bootstrap_source_of_truth as boot; import common`
- - The two-context pattern (first pass to materialize registry, second pass to inject state, third pass to refresh) is the standard for refresh preservation tests.
- - NEVER use `boot.generate_artifacts()` pointing at the real registry — always use a tmp dir.
- ### Closer-final preservation contract
- - `CLOSER_FINAL_STATUSES = frozenset({"done","blocked","skipped"})` — importable from `bootstrap_source_of_truth`.
- - `CLOSER_FINAL_OUTCOMES = frozenset({"committed","deployed"})` — importable from `bootstrap_source_of_truth`.
- - `_RUNTIME_TASK_FIELDS_TO_PRESERVE` — the full allowlist of lifecycle fields (20 fields).
- - `_apply_preserved_runtime` has a defensive re-assertion: after the copy loop, for closer-final tasks it re-sets `status`, `last_outcome`, `last_updated_by`, `last_stop_at` from `old`.
- - Derived fields (`title`, `depends_on`, `write_set`, `conflict_groups`) are ALWAYS refreshed — never preserved.

## Original heading index
- # Developer Agent Memory — Hilo People
- ## Codebase patterns discovered
- ### Project structure
- ### Hook gotcha (CRITICAL)
- ### Docker Compose (P00-S02-T001)
- ### Backend Dockerfile (P00-S02-T001)
- ### Frontend Dockerfile (P00-S02-T001)
- ### Environment
- ### Dev-restart.sh
- ### Node modules in worktree
- ### Vitest globals (CRITICAL for tsc)
- ### i18n (P00-S01-T005)
- ## Decisions and why
- ### Argon2id idempotency pattern (P00-S02-T003)
- ### Alembic in worktree (P00-S02-T003)
- ### cryptography dep (P00-S02-T003)
- ### Fixture loader deferred pattern (P00-S02-T003)
- ### Integration test setup (P00-S02-T003)
- ### SQLAlchemy text() JSONB cast patterns (P00-S02-T004)
- ### Alembic worktree invocation (updated P00-S02-T004)
- ### Acceptance test path (P00-S02-T004)
- ### Tooling-fix slices in worktrees (P01-S02-T008 pattern)
- ## Known gotchas
- ## Slice history
- ### pgvector retrieval patterns (P02-S04-T001)
- ### Auth module structure (P01-S02-T001)
- ### Pydantic v2 field_validator behavior (P01-S02-T001)
- ### TestClient vs live uvicorn session handling (P01-S02-T001)
- ### Migration test gotcha (P01-S02-T001)
- ### Service layer session ownership (P01-S02-T001)
- ## P01-S02-T002 decisions and patterns
- ### JWT with PyJWT==2.12.1
- ### Refresh token cookie pattern (Web BFF)
- ### Aggregate-401 anti-enumeration
- ### D-S2 rejection audit pattern
- ### Circular import prevention in auth module
- ### rate_limit.py refactor for multi-endpoint support
- ### Test isolation for sign-in tests
- ### Alembic in test suite
- ## P01-S02-T009 — Bash dev-secrets provisioner patterns
- ### POSIX-portable in-place .env editing
- ### Bash secret hygiene
- ### CLAUDE_PROJECT_DIR pattern for portable scripts
- ### Idempotency contract for provisioners
- ### uvicorn invocation for verification (macOS)
- ## P01-S02-T010 — Bootstrap preservation framework patterns
- ### hook_write_scope_guard.py blocks .claude/bin/ writes (CRITICAL)
- ### Bootstrap test pattern (canonical)
- ### Closer-final preservation contract
- ### Pre-existing test_static_contracts failure
- ### Snapshot verification pattern for framework maintenance slices
- ## P01-S02-T003 — POST /api/v1/auth/refresh patterns
- ### SELECT FOR UPDATE for concurrent rotation (D-RP3)
- ### D-S2 pattern for refresh failure audits
- ### Aggregate anti-enumeration for refresh
- ### ORM DetachedInstanceError in test helpers (CRITICAL)
- ### Rate limit namespace for new endpoint
- ### Cookie helper shared across endpoints (D-RP2)
- ### Alembic test suite destroys DB schema (known issue)
- ### test_signin_success_no_mfa + test_signin_mfa_required_branch pre-existing failures
- ## P01-S02-T004 — POST /api/v1/auth/logout patterns
- ### Logout audit extraction pattern (file size compliance)
- ### _clear_refresh_cookie pattern
- ### classify_logout_miss(row) pattern
- ### _safe_uuid helper for bearer/cookie user_id comparison
- ### Test isolation for logout tests
- ### D-S2 on logout (T14)
- ### Byte-identical 401 body (T10)
- ### Test pre-existing failures with no postgres (known)
- ## P01-S02-T012 — db_health race fix patterns
- ### Bash /dev/tcp is bash-only (NOT zsh)
- ### Two-probe AND pattern for host TCP + container-internal pg_isready
- ### Negative control with --reset
- ### File write workaround (T012 pattern)
- ## P01-S02-T011 — Cookie Path fix + httpx cookie-jar test patterns
- ### httpx.AsyncClient + ASGITransport cookie-jar behavior (CRITICAL)
- ### Regression guard design principle
- ### Cookie Path constant pattern (DRY)
- ## P01-S02-T005 — Forgot + reset password (2026-05-12)
- ## P01-S02-T006 — POST /api/v1/auth/2fa/verify TOTP MFA endpoint (2026-05-12)

## Canonical references
- `.claude/orchestrator-contract.json`
- `.claude/rules/00-source-of-truth.md`
- `.claude/rules/01-non-negotiables.md`
- `.claude/rules/02-phase-execution.md`
- `.claude/rules/05-runtime-write-contract.md`
- `CHEATSHEET.md`
- `orchestrator-state/agent-memory/developer/archive/MEMORY.full.2026-05-13-182225.md`

## P02-S03-T004 — ENCRYPTION_KEY rotation + AI provider seeding

### Bash POSIX-portable .env editing (critical pattern)
- Never use `sed -i` (BSD macOS requires empty backup arg; GNU doesn't). Use awk + tmpfile + mv.
- Pattern: `awk -v K="$key" -v V="$val" 'NF>=2 && $1==K { if(!replaced){print K"="V; replaced=1} next } {print}' "$env_path" > "$tmp" && mv "$tmp" "$env_path"`
- Always use `set +x` at top of bash scripts that handle secrets — xtrace prints every expansion to stderr.
- Log to stderr only; never echo key values; log `key_len=${#VAR}` only.

### Fernet key generation pattern (confirmed via researcher Q1)
- Canonical: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Generates 44-char url-safe base64 key ending in `=`.
- Validation smoke: `Fernet(key.encode())` raises ValueError on bad key — constructor-only is sufficient.
- cryptography==48.0.0: no changes to Fernet API; single-key sufficient for bootstrap (MultiFernet only for live rotation).

### Idempotent key provisioner pattern
- Check if value == 'replace-with-dev-key' (exact string) to decide rotation.
- For JWT keys: also check len < 32 as secondary placeholder signal.
- Second run must produce `changed=0` — test this explicitly (T02 pattern).
- Never print key value in any output — test explicitly (T03 pattern).

### load_ai_provider_credentials pattern
- FK resolution at load time: `SELECT id FROM ai_providers WHERE name = :provider_ref`
- Encrypt at load time: `from app.security.encryption import encrypt_secret`
- Idempotency key: (provider_id, auth_type)
- Log: `credential_len=len(fx.credential_plain)` only — never the value itself.
- Reset Fernet cache in tests: `from app.security.encryption import reset_fernet_cache; reset_fernet_cache()` before and after monkeypatching ENCRYPTION_KEY.

### ai_models_default_per_type_uidx gotcha
- Index: `UNIQUE(model_type) WHERE is_default = true` — GLOBAL across all providers, not per-provider.
- Tests that insert a new `is_default=true` model for a new test provider MUST first clear any existing `is_default=true` row for that model_type via `UPDATE ai_models SET is_default = false WHERE model_type = :t AND is_default = true`.
- This is a test isolation requirement; the production bootstrap is idempotent by (provider_id, model_id) — no issue.

### Fixture dir structure for admin_ai
- providers/*.json → AiProviderFixture (loaded by load_ai_providers)
- credentials/*.json → AiProviderCredentialFixture (loaded by load_ai_provider_credentials)
- models/*.json → AiModelFixture (loaded by load_ai_models)
- FK-safe order: providers → credentials → models

### T09 deferred-skip test pattern
- Use `patch("app.verification_data.loader._table_exists", return_value=False)` with context manager.
- Mock session and engine with MagicMock().
- Assert status == "deferred" and "table_missing" in reason.
- Assert mock_session.execute not called.

### Slice outcome
- P02-S03-T004: success. 14/14 tests PASS both verbose modes. Lint clean. ENCRYPTION_KEY rotated.

## P02-S06-T001 — RAG document admin endpoints (2026-05-13)

### Python mocking gotcha (T22/T26/T27/T29 lesson)
- `patch("mod.target")` returns a `MagicMock` whose `.return_value` is auto-created. This is what you almost always want.
- `patch("mod.target", new_callable=lambda: type("X", (), {...}))` returns a CLASS object — classes have no `.return_value` attribute. AttributeError at access.
- Also: function-local `from module import name` shadows the module-level `name` attribute, so a patch on the module-level binding does nothing. Always import at module level when tests need to patch.

### FastAPI 0.135.x file upload routes
- `UploadFile.read(size)` is async, runs in threadpool; loop with byte counter for chunked reads.
- Starlette 0.49+ does NOT provide `MaxRequestBodySizeMiddleware`. Custom ASGI middleware (10–15 LoC) for total-body cap before multipart parsing.
- `python-multipart` is NOT a transitive dep of `fastapi` base; pin `python-multipart==0.0.28` explicitly with `fastapi==0.135.2`.

### Celery dispatch from async def
- `apply_async` is blocking I/O (Kombu socket). Wrap in `await asyncio.to_thread(task.apply_async, args=[...])` to keep event loop responsive.
- Idempotent inflight check at service layer before dispatch — return 409 if a `vectorization_jobs.status='queued'` row already exists for the document.

### boto3 against MinIO
- `put_object` is always single-part; `multipart_threshold` in TransferConfig only affects high-level `upload_file`/`upload_fileobj`.
- Pass `ContentType` explicitly — MinIO stores `application/octet-stream` if omitted.
- Storage order: DB INSERT+commit first, then MinIO PUT; on PUT failure delete the documents row (no orphan).

### Slice outcome
- P02-S06-T001: success. 29/29 tests PASS both verbose modes. python-multipart pinned. 2 recovery runs after early agent cutoffs (subprocess context exhaustion).
