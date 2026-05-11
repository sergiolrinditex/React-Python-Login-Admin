# Planner — agent memory (Reflexion-style)

> Append-only patterns and lessons. Compact via `/slice-maintain compact-agent-memory`.

## Patterns

### P-1 — Dependency-pack slices (P00-S01-T002 frontend, P00-S01-T003 backend)

- Acceptance text may name a library (e.g. "SQLAlchemy") that does NOT appear in TECHNICAL_GUIDE §2.0 Library Discovery Pass rows for that slice. The §2 narrative paragraph is also source-of-truth — cross-reference acceptance against §2 narrative + §2.0 table + §11.1 summary. If acceptance names a lib but §2.0 row is absent, **declare anyway** and document the cross-reference in the task pack.
- Never pin versions in the planner pack for AI/ML libs (LiteLLM, LangChain, LangGraph, DeepAgents, MCP SDK, tiktoken). `.claude/rules/01-non-negotiables.md → AI/ML volatile ecosystem` makes this the researcher's job. Leave explicit "pendiente — researcher" markers and enumerate the version questions in §F of the pack.
- PyPI dist name vs import alias is a common trap (e.g. `python-docx` → `import docx`; `prometheus-client` → `import prometheus_client`). Always list both in the task pack so the smoke test does not silently skip an import.
- `pgvector` and similar ecosystem names can have multiple PyPI packages. Enumerate the disambiguation question explicitly.

### P-2 — Write-set extensions for `backend/tests/`

- Backend deps + scaffold slices frequently need a smoke or health test, but `backend/tests/` is rarely in the literal `write_set`. T001 (Repo scaffold) set the precedent: extension flagged in handoff, validator approved. Reuse this precedent for T003 (dependency smoke) and likely future P00-S02 slices.

### P-3 — Glob non-vacuous markers

- When write_set contains a glob like `backend/app/core/**` and the slice has no business code to put there, create a minimal `__init__.py` with a docstring so the glob is non-vacuous. Avoids validator confusion about empty scope.

### P-4 — UX_CONTRACT N/A documented explicitly

- For library / scaffold / infra slices with no UI, write "UX_CONTRACT.md — N/A for this slice" verbatim in the task pack so closer evidence does not need `VISUAL_CONTRACT_CHECK`. Saves a validator round-trip.

### P-5 — Parallel terminal context block

- When `/next-wave` ran and another terminal is working a sibling slice (e.g. T002 frontend deps while we run T003 backend deps), include a "Parallel-terminal context" section confirming conflict_group/write_set disjointness. Saves the validator from re-checking and helps debug if a wave race appears.

## Modules that tend to be touched together

- `backend/pyproject.toml` + `backend/requirements.txt` + `backend/requirements-test.txt` + (optional) `backend/requirements-dev.txt` — declarations must stay in lockstep. `pyproject.toml` is canonical.
- `backend/tests/test_*_smoke.py` co-evolves with dependency slices.

## Recurring unknowns

- Exact versions for AI/ML libraries (always defer to researcher).
- MCP Python SDK canonical package name (placeholder in §2.0 row 14).
- pgvector PyPI namesake disambiguation.

## Risks repeated

- AI/ML ecosystem version drift between training cutoff and current PyPI.
- Acceptance text and §2.0 table can disagree on lib coverage; trust the union and document.

### P-6 — Vite/Vitest first-touch config trilemma (T002 frontend deps)

- `npm test -- --run` (vitest) fails by default if it finds zero tests and `--passWithNoTests` is not set. A library-only slice with `verify_mode=auto` STILL needs a real smoke test to exit 0. Plan a smoke test as CANDIDATE EXTENSION, never silently expand write_set.
- Three config files are the recurring trap on the first frontend slice that runs vitest: `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/tsconfig.json`. None are usually in the dep-pack write_set, but TSX compilation + plugin resolution + JSX runtime usually require at least one of them. Enumerate all three as CANDIDATE EXTENSIONS with rationale and let the developer rule + flag.
- ESM-only packages on Vite 8 / React 19: `react-router-dom@7`, `zod@4`, possibly `react-i18next`. Researcher must pin major-version compat with React 19, TS 6, vitest 3 explicitly.
- `i18next-browser-languagedetector` is browser-only. In a Node-based vitest run with default env, it may crash. Pre-decide jsdom vs happy-dom in the pack (or defer browser-only init).
- TanStack Query `persistQueryClient` can write to `localStorage`. instrucciones.md §11.2 forbids tokens in localStorage. Even though Query cache != tokens, call this out explicitly in the pack so the developer never wires the persistor in P0.

### P-7 — Composition-root shape contract

- For `providers.tsx` (or any composition root file consumed by 3+ downstream slices), write the SHAPE CONTRACT in the pack:
  - exported component name (`Providers`),
  - typed props with optional injection seams (`queryClient?`, `i18n?`),
  - fixed composition order outer→inner,
  - what is intentionally NOT mounted (e.g., `<BrowserRouter>` belongs to T004).
- Downstream slices (T004 router, T005 i18n, P01-S03-T001 auth) consume this contract — saves them a re-read of the file.

### P-8 — DAG terminal vs singleton-active-task drift

- `runtime-state.active_task_id` is the SINGLETON pointer; in DAG mode multiple terminals run concurrently. If your env `CLAUDE_ACTIVE_TASK_ID=T002` but the singleton points to T003, that is NORMAL parallelism (sister terminal). Confirm via `Conflict group` disjointness in registry. Do not bail out as "registry drift".

### P-10 — i18n resource slice (T005 pattern, reusable for any locale-pack slice)

- `instrucciones.md §6` (or the project's equivalent i18n keys section) usually contains a small literal table that fixes:
  - the set of supported languages,
  - the fallback,
  - the set of namespaces (string literals),
  - the canonical copy for a sample of keys per language.
  Treat this table as the legal contract. Every namespace + every literal copy MUST land verbatim in the bundles. EN/FR (or any non-fallback language) MUST NOT be a copy-paste of the fallback — that is a covert acceptance failure even if `t()` returns a string.
- `TECHNICAL_GUIDE §6.4 Formato de errores` (or equivalent error-code catalog) is the legal source for the `errors` namespace keys. Cross-list ALL codes there into the errors bundle in the pack so the developer doesn't ship a half-empty errors map.
- Bundle delivery format on Vite + i18next v26: inline import from `public/locales/**/*.json` is KISS-correct for tiny bundles (<10KB gzipped). HTTP backend + lazy-load is YAGNI in P0. Document the decision in the pack so the developer doesn't introduce `i18next-http-backend`.
- `i18next-browser-languagedetector` should remain DISABLED in any slice that lives before the screen that exposes a language selector (AccountPage in this product). The jsdom crash already documented in T002 is reason to keep it OFF. Activation belongs to the AccountPage slice, not the bundle slice.
- Verify_mode=human on an infrastructure slice with no new screen → propose a **minimal demo consumer in the existing dev-only showcase route** (`/showcase` here). Flag it as WRITE_SET_DRIFT in the handoff with the reason "verify_mode=human requires a visible consumer". Without this, /verify-slice cannot run a real browser reproduction and the slice cannot close.
- TS module augmentation (`declare module "i18next" { CustomTypeOptions }`) is an optional best-practice that future screen slices will benefit from. Make it explicit in the pack but deferable if it generates TS friction in the dep matrix.
- Write_set `frontend/src/i18n/**` + `frontend/public/locales/**` is **disjoint** from `frontend/src/shared/styles/**` (tokens) — confirm this in the pack to short-circuit validator concern about i18n touching the design system.

### P-11 — DB migration slice (P01-S01-T001 first auth baseline)

- TECHNICAL_GUIDE §10.3 declares ALL extensions at the top of the SQL block (`pgcrypto`, `vector`) even when not all tables in the same migration use them. Decision: split — create only the extensions actually referenced by THIS migration's tables, defer the rest to the migration that introduces dependent tables. Document explicitly (D1/D2) in the pack to forestall validator confusion.
- `gen_random_uuid()` lives in pgcrypto. Without `CREATE EXTENSION IF NOT EXISTS pgcrypto` first, every UUID-default column fails at INSERT time, not at CREATE time. Easy to miss in lint-only review; the verify command `alembic upgrade head && downgrade -1 && upgrade head` catches it because the second upgrade tries to insert (verification_data bootstrap).
- §10.3 raw DDL omits NOT NULL on FK columns (`refresh_tokens.user_id`, `password_reset_tokens.user_id`). Reality: every refresh/reset token must belong to a user. Plan tighter constraint than raw DDL, document as "tighter than §10.3 raw DDL justified by §3.1 business rules" in handoff §K. Validator approval pattern reusable for future migrations.
- ON DELETE CASCADE for identity-attached tables (employee_profiles, user_roles, refresh_tokens, mfa_totp_secrets, password_reset_tokens) is the GDPR right-to-be-forgotten posture. ON DELETE SET NULL for `audit_logs.actor_user_id` is the GDPR Art. 30 records-of-processing posture. Combine both for the auth baseline. Document explicitly to avoid future validator/debugger debate.
- `alembic/env.py` may already contain a docstring predicting "P01-S01-T001 will replace this line." That's the previous slice's planner anticipating; it does NOT make the change in-scope automatically. Declare it as a write_set extension in handoff §I anyway. Hook write-scope-guard does not block since the file is touched by an active TASK_ID, but validator should still see it acknowledged.
- Model split by bounded context: identity (User, EmployeeProfile, Role, Permission, UserRole) → `user.py`; session/credential/audit (RefreshToken, MfaTotpSecret, PasswordResetToken, AuditLog) → `auth.py`. Rationale: avoid user.py becoming a god-file when auth flows expand in P01-S02. AuditLog is operational trace of identity actions → fits auth.py because actor + action + result is the auth bounded context.
- `Base = DeclarativeBase` ALWAYS goes in its own module (`base.py`) when 2+ model files exist. Importing Base from one model file into another creates ciclo problems with SQLAlchemy's metaclass when registry collisions happen during test teardown. Write_set extension justified, precedent reusable (P00-S01-T001/T003 markers).
- SQLAlchemy 2.x naming convention via `MetaData(naming_convention=...)` should be declared in `base.py`, not later. Alembic inherits it for `op.f("constraint_name")` style downgrade reliability. Standard convention: `https://alembic.sqlalchemy.org/en/latest/naming.html`.
- Index recommendations for auth tables that survive validator: `refresh_tokens(token_hash)`, `refresh_tokens(user_id, revoked_at)`, `password_reset_tokens(token_hash)`, `user_roles(role_id)`, `audit_logs(actor_user_id, created_at DESC)`, `audit_logs(entity_type, entity_id)`, `audit_logs(created_at DESC)`. Skip `users(email)` — UNIQUE already gives implicit btree.
- Verification_data loader (`backend/app/verification_data/`) sets up a Chekhov's gun: it expects EXACT column names from §10.3 and uses `inspect().has_table()` to defer until the migration runs. The DB migration slice's column names are therefore contract-bound with that loader. ANY rename (e.g., `password_hash` → `pwd_hash`) breaks the load silently with a KeyError. Cross-reference loader.py against the migration column-by-column in handoff §K before approving.

### P-9 — Infra/compose slices in P00-S02 (Docker Compose)

- Acceptance text "Postgres, Redis, LiteLLM, MinIO and worker boot locally" can be interpreted two ways: (a) services declared in YAML + healthchecks pass, (b) every service actually runs sanely. For "worker" (Celery), the Celery entrypoint module (e.g. `app.worker`) usually does NOT exist yet at this stage (lives in P02-S04-T002). Plan the slice for interpretation (a) with `restart: on-failure`, and surface the question to the human via §J Open questions. Don't silently create a stub `app/worker.py` in a write_set that excludes it.
- Compose YAML must be **v2-spec pure** for Rancher Desktop (works on both moby and containerd via `nerdctl compose`). Forbid: top-level `version:`, `host-gateway`, bind-mounts outside `$HOME`. Require: named volumes, standard healthchecks (`test`/`interval`/`timeout`/`retries`/`start_period`), `depends_on` with `condition: service_healthy`.
- Image pin contracts the human gave on this project (record verbatim if reused):
  - Postgres → `postgres:17-alpine` (pgvector deferred to P01; can switch to `pgvector/pgvector:pg17` later).
  - Redis broker → `valkey/valkey:8-alpine` with service NAME `redis` so the existing `REDIS_URL=redis://redis:6379/0` resolves unchanged.
  - LiteLLM → `ghcr.io/berriai/litellm:v1.83.14-stable.patch.3`.
  - MinIO → `minio/minio:RELEASE.2025-09-07T16-13-09Z`, plus a `minio/mc:latest` sidecar (`restart: "no"`) for bucket+keys bootstrap, gated by `depends_on: { minio: { condition: service_healthy } }`.
- Cross-task interlock: backend/Dockerfile depends on the final `requirements.txt` produced by P00-S01-T003; frontend/Dockerfile depends on `package-lock.json` + Vite config produced by P00-S01-T002. While those siblings are `claimed`/`in_progress`, **defer** `docker compose build backend|frontend` smoke to `/verify-slice` or to `P06-S01-T001`. The infra smoke that always works is `compose config` + `compose up -d` on postgres/redis/litellm/minio only.
- Health endpoint paths for managed images (LiteLLM, MinIO, Valkey) drift between releases. Add an explicit researcher hook: confirm `/health/liveliness` vs `/health` vs `/v1/health` for the pinned LiteLLM tag before the developer codes the healthcheck — otherwise `condition: service_healthy` will silently never fire.
- `.env.example` extension is acceptable for infra slices (MinIO root creds, optional `LITELLM_MASTER_KEY`) even when the canonical TECHNICAL_GUIDE §11.1 table does not list them — they are imposed by the service images, not by app contract. Document as explicit write_set extension in the pack so validator approves without ambiguity.
- Slice-Traceability rule: a Docker Compose slice **does NOT** invoke `VISUAL_CONTRACT_CHECK` (no UI). Write "UX_CONTRACT.md — N/A for this slice" verbatim in §K of the pack so closer doesn't reject for missing visual evidence (reuse of P-4).

### P-12 — Runtime follow-up promoted to its own DAG task (P00-S02-T004 pattern)

- A promoted FU is NOT a generic bug ticket — it is a full DAG node with `acceptance` and `verification_commands` cloned from the FU YAML into `registry.json`. Always quote the FU `triage.why_not_debugger` field verbatim in the task pack so the validator can confirm the FU was correctly out-of-scope from the origin task (i.e., the FU pathway was justified vs. the debugger-retest pathway).
- `:bindparam::pg_type` in SQLAlchemy `text()` is a recurring trap. The parser is ambiguous on `::` after a named bindparam. Canonical fixes: `CAST(:p AS PG_TYPE)` (preferred — SQL-standard) or `(:p)::pg_type`. Document both in the pack so the developer + validator agree on form before the fix lands.
- `str(dict).replace("'", '"')` masquerading as JSON is also a recurring trap — passes for trivial fixtures, breaks for any value containing `'`, `True`/`False`, `None`, datetimes. Always recommend `json.dumps(...)`. The fix is one-line and the same file in question often already imports `json` inside other functions; hoisting to module top is acceptable.
- **In-scope vs out-of-scope code paths in a bug-fix slice**: classify EVERY occurrence of the broken pattern in the affected file against the acceptance tests. The path that the tests do NOT exercise (because of `_table_exists()`/feature flag/deferred branch guards) is out_of_scope by default, even when it has the same bug. Mention them as a triage table in the pack so the developer can choose conservative-fix-only or belt-and-suspenders-fix with validator approval. Conservative wins when unsure.
- Acceptance tests in a bug-fix slice OFTEN need to be in the `write_set` even though no test should change behavior: they were written under a now-invalid assumption (in this case, "tables don't exist post-migration"). Plan for the developer to make minimal clarifying edits (comments or assertion-set extension that still accepts the old branch). Block scope-weakening edits explicitly in the pack.
- Alembic CLI vs `python -m alembic` shadowing trap: when a project has `backend/alembic/` (the migrations directory) and `cwd=backend/`, the import of the `alembic` Python package is shadowed by the local migrations dir → `ModuleNotFoundError: No module named 'alembic.config'`. The fix is to either invoke from repo root (`cd backend && alembic ...` where the shell PATH resolves to the binary) or use the absolute CLI binary path. Tests in this project already pin the absolute CLI path; document it in §Open questions so the developer doesn't waste a debug cycle.
- Unrelated working-tree changes at claim time (here: `scripts/dev-restart.profile.sh`): flag them in the pack explicitly with "NOT in this slice's write_set; closer will handle separately". Prevents the developer from picking them up accidentally and prevents the closer from including them in this slice's atomic commit.
