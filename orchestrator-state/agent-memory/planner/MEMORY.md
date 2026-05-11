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
