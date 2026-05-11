# Official Docs Researcher Memory

Last updated: 2026-05-11
Agent: official-docs-researcher

---

### 2026-05-11 — P00-S02-T001 Docker Compose infra pins

Full note: `orchestrator-state/memory/official-doc-notes/P00-S02-T001-infra-compose-2026-05-11.md`

#### Verified OK (cache valid until 2026-05-18 for stable; Docker tags are volatile, re-check before re-use)

| Topic | Finding | Source |
|---|---|---|
| postgres:17-alpine | Supported until 2029-11-08; latest minor 17.9; no critical CVEs | postgresql.org/support/versioning |
| valkey/valkey:8-alpine | Stable (not rc/dev); Redis OSS 7.2.4 compatible; `valkey-cli ping` is the correct healthcheck | github.com/valkey-io/valkey/releases, hub.docker.com/r/valkey/valkey |
| litellm v1.83.14-stable.patch.3 | Tag exists, stable (not prerelease); health endpoint = `/health/liveliness`; port 4000 | github.com/BerriAI/litellm/releases, docs.litellm.ai/docs/proxy/deploy |
| litellm required env vars | `LITELLM_MASTER_KEY` (sk- prefix) required; `DATABASE_URL` optional for dev; `LITELLM_SALT_KEY` recommended | docs.litellm.ai/docs/proxy/deploy |
| minio RELEASE.2025-09-07T16-13-09Z | Tag confirmed; server cmd `minio server /data --console-address ":9001"` correct; healthcheck `/minio/health/live` → 200 OK | github.com/minio/minio, docs.min.io |
| mc sidecar pattern | `mc alias set` + `mc mb` + `mc admin policy attach` — all valid commands | docs.min.io |
| Docker Compose `version:` key | Obsolete (informational only, ignored, triggers warning). Omitting it is CORRECT. | docs.docker.com/compose/compose-file/04-version-and-name |
| `condition: service_healthy` | Valid in Compose v2 spec (moby/docker compose) | docs.docker.com/compose/compose-file/05-services/#depends_on |
| python:3.12-slim-bookworm | Actively maintained; safer than slim-trixie for wheel compat | hub.docker.com/_/python |
| nginx stable alpine | Current stable = **nginx:1.30.0-alpine** (or floating `nginx:stable-alpine`). 1.27/1.28 are older. | hub.docker.com/_/nginx |

#### CRITICAL DISCREPANCY (UNRESOLVED)

- **nerdctl compose v2.2.2 does NOT support `healthcheck` or `condition: service_healthy`**.
- `services.<SERVICE>.healthcheck` is explicitly listed as unimplemented in nerdctl compose docs.
- GitHub issue #2386 (open since 2023-07-21) — still unresolved.
- Impact on task: docker-compose.yml with healthchecks works on dockerd (moby) but silently ignores healthchecks on containerd/nerdctl backend.
- Suggested mitigation: add comment in docker-compose.yml; require moby backend for verify-slice.
- Note written: `P00-S02-T001-infra-compose-2026-05-11.md` (items 5 + 8 UNRESOLVED)

#### Minor discrepancy (UNRESOLVED)

- nginx: task pack mentions 1.27-alpine / 1.28-alpine for consideration; current stable is 1.30.0-alpine.
- Suggested fix: use `nginx:stable-alpine` in frontend/Dockerfile.

---

## Cache entries (freshness windows: stable tech=7d, AI/ML volatile=always, Claude Code=14d)

### 2026-05-11 — P00-S01-T001 HILO_PEOPLE scaffold

**Verified via npm registry + PyPI live + Context7:**

#### Backend

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| fastapi | 0.136.1 (latest stable) | PyPI live | 2026-05-18 |
| uvicorn | 0.46.0 (latest stable) | PyPI live | 2026-05-18 |
| pydantic | 2.13.4 (v2, stable) | PyPI live | 2026-05-18 |

- FastAPI canonical entrypoint: `from fastapi import FastAPI; app = FastAPI()` — NO breaking change.
- Lifespan pattern: `@asynccontextmanager async def lifespan(app): yield` — replaces deprecated `@app.on_event`. NOT needed for stub-only health endpoint.
- `__init__.py` required: YES — `backend/app/__init__.py` must exist for `uvicorn app.main:app`.
- Pydantic v1 support deprecated in FastAPI; v2 only for new projects.
- PEP 621 `[project]` table + `hatchling` build backend = current modern standard.
- No health endpoint helper built into FastAPI (hand-rolled `GET /health` returning `{data:{status}}` is correct).

#### Frontend

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| react | **19.2.6** (latest) | npm registry live | 2026-05-18 |
| react-dom | **19.2.6** (latest) | npm registry live | 2026-05-18 |
| vite | **8.0.12** (latest) | npm registry live | 2026-05-18 |
| @vitejs/plugin-react | **6.0.1** (latest) | npm registry live | 2026-05-18 |
| typescript | **6.0.3** (latest) | npm registry live | 2026-05-18 |
| react 18 LTS | 18.3.1 (available, not latest) | npm registry | — |
| vite 7 LTS | 7.3.1 (available, not latest) | npm registry | — |
| typescript 5 LTS | 5.9.3 (available, not latest) | npm registry | — |

**DISCREPANCY written:** `orchestrator-state/memory/official-doc-notes/frontend-stack-versions-2026-05-11.md`
- Task pack and CLAUDE.md mention "React 18 + Vite 5 + TypeScript 5" but current stable is React 19 / Vite 8 / TS 6.
- Developer must escalate to human before picking React 18 vs 19.
- If React 19 chosen: `@vitejs/plugin-react@^6.0.1` + `vite@^8.0.12` + `typescript@~6.0.3`.
- If React 18 LTS chosen (explicit human sign-off required): `@vitejs/plugin-react@^4.3.4` + `vite@^7.3.1` + `typescript@~5.9.3`.

#### Python packaging

- PEP 621 `[project]` table: YES, current recommended standard.
- Build backend: `hatchling` preferred for new FastAPI projects (also `setuptools` valid legacy).
- `backend/app/__init__.py`: required (not implicit namespace packages) for `uvicorn app.main:app`.

#### Python logging

- `logging.basicConfig` + env var: still idiomatic for minimal scaffold in T001.
- `structlog` / `loguru`: not a hard default yet for new FastAPI scaffolds; commonly adopted in mid-to-large projects. Task pack §7 explicitly says "minimal stdlib logging" for T001; structlog lands in T003. Aligns with current practice.

#### Health endpoint

- No FastAPI built-in health helper (unlike Spring Boot Actuator). Hand-rolled `GET /health` returning `{"data": {"status": "ok"}}` is correct canonical pattern.
- Lifespan not required for stub (no external resources to initialize).

---

### 2026-05-11 — P00-S01-T003 Backend dependency pack (full 20-package audit)

**Verified via PyPI live JSON + Context7 (litellm, langchain, langgraph, pgvector, tiktoken).**

Full canonical table in: `orchestrator-state/memory/official-doc-notes/T003-pinned-versions.md`

#### Runtime packages

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| sqlalchemy | **2.0.49** | PyPI live | 2026-05-18 |
| alembic | **1.18.4** | PyPI live | 2026-05-18 |
| celery | **5.6.3** | PyPI live | 2026-05-18 |
| redis | **7.4.0** | PyPI live | 2026-05-18 |
| pypdf | **6.11.0** | PyPI live | 2026-05-18 |
| python-docx | **1.2.0** | PyPI live | 2026-05-18 |
| resend | **2.30.0** | PyPI live | 2026-05-18 |
| structlog | **25.5.0** | PyPI live | 2026-05-18 |
| prometheus-client | **0.25.0** | PyPI live | 2026-05-18 |
| boto3 | **1.43.6** | PyPI live | 2026-05-18 |
| pgvector | **0.4.2** | PyPI live + Context7 | 2026-05-18 |
| litellm | **1.83.14** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |
| langchain | **1.2.18** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |
| langchain-core | **1.3.3** | PyPI live | ALWAYS re-verify (AI/ML) |
| langchain-community | **0.4.1** | PyPI live | ALWAYS re-verify (AI/ML) |
| langchain-text-splitters | **1.1.2** | PyPI live | ALWAYS re-verify (AI/ML) |
| langgraph | **1.1.10** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |
| deepagents | **0.5.9** | PyPI live | ALWAYS re-verify (AI/ML) |
| mcp | **1.27.1** | PyPI live | ALWAYS re-verify (AI/ML) |
| tiktoken | **0.12.0** | PyPI live + Context7 | ALWAYS re-verify (AI/ML) |

#### Dev/test packages

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| ruff | **0.15.12** | PyPI live | 2026-05-18 |
| mypy | **2.0.0** | PyPI live | 2026-05-18 |
| pytest-asyncio | **1.1.0** | PyPI live | 2026-05-18 |

#### Key gotchas verified this pass

- **python-docx**: import is `import docx` (NOT `import python_docx`). PyPI dist = `python-docx`.
- **prometheus-client**: import is `import prometheus_client` (underscore). PyPI dist = `prometheus-client`.
- **pgvector**: canonical package is by Andrew Kane (`pgvector` on PyPI). SQLAlchemy adapter bundled — NO extras needed. Import: `from pgvector.sqlalchemy import VECTOR`. Do NOT use any other `pgvector-*` package.
- **pypdf**: successor to PyPDF2. Do NOT install PyPDF2. Import: `from pypdf import PdfReader`.
- **mcp**: official Anthropic MCP SDK. PyPI name = `mcp`. Maintained by Anthropic PBC. Import: `import mcp`.
- **langchain split packages**: `langchain==1.2.18` is the meta-package; RAG needs `langchain-community` (loaders) + `langchain-text-splitters` (splitters) + `langchain-core` (base abstractions).
- **deepagents peer deps**: `langchain-anthropic>=1.4.3` + `langchain-google-genai>=4.2.2` + `langsmith>=0.8.0` are hard runtime deps pulled transitively. No API keys needed at import time. Beta status.
- **mypy 2.0.0**: major version bump from 1.x — verify changelog before strict mode config.
- **pytest-asyncio 1.1.0**: compatible with `pytest>=8.2,<10`; `pytest==9.0.2` satisfies.
- **sqlalchemy 2.x async**: use `create_async_engine` + `AsyncSession` + `asyncpg` driver.
- **langgraph**: requires Python >=3.11.

#### Discrepancy notes written

- `T003-discrepancy-deepagents.md` — Beta status + mandatory provider SDKs. RESOLVED: pending human decision on whether to include in T003 or defer. Not a blocker per §11.0 USAR classification.

---

### 2026-05-11 — P00-S01-T002 Frontend dependency pack

**Verified via npm registry live + Context7 + reactrouter.com + zod.dev/v4 + GitHub releases (testing-library).**

#### React Router

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| react-router | **7.15.0** | npm registry live | 2026-05-18 |
| react-router-dom | **7.15.0** (thin shim) | npm registry live | 2026-05-18 |

- **DISCREPANCY**: Task pack says install `react-router-dom`; official v7 docs say install `react-router`.
- `react-router-dom` v7 still exists as thin re-export shim — technically works but is deprecated install name.
- Official migration: `npm uninstall react-router-dom && npm install react-router@latest`.
- Import path in v7: `from "react-router"` (not `"react-router-dom"`).
- `BrowserRouter`, `Outlet`, `useNavigate` etc. all export from `"react-router"` in v7.
- DOM-specific API (`RouterProvider` with `createBrowserRouter`): `from "react-router/dom"`.
- peerDependencies: react >=18 — React 19 satisfies.
- DISCREPANCY NOTE: `frontend-deps-T002-react-router-2026-05-11.md`

#### TanStack Query

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| @tanstack/react-query | **5.100.9** | npm registry live | 2026-05-18 |

- peerDependencies: `"react": "^18 || ^19"` — React 19 fully supported.
- `QueryClient` and `QueryClientProvider` export from `"@tanstack/react-query"` (main entry).
- Supported constructor: `new QueryClient({ defaultOptions: { queries: { retry: 1 } } })`.
- Recommended pattern in providers.tsx: `useState(() => new QueryClient(...))` lazy init.
- Do NOT enable persistQueryClient (instrucciones §11.2: no localStorage tokens/cache).

#### React Hook Form + resolvers + Zod

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| react-hook-form | **7.75.0** | npm registry live | 2026-05-18 |
| @hookform/resolvers | **5.2.2** | npm registry live | 2026-05-18 |
| zod | **4.4.3** (v4 current stable) | npm registry + zod.dev | 2026-05-18 |

- RHF peerDeps: `"react": "^16.8.0 || ^17 || ^18 || ^19"` — React 19 fully supported.
- `@hookform/resolvers` v5.2.2 supports BOTH Zod v3 and Zod v4 (README: `from 'zod/v4'` example).
- zodResolver import: `import { zodResolver } from "@hookform/resolvers/zod"`.
- Zod v4 is current stable. Deprecated form: `z.string().email()` → prefer `z.email()`.
- Zod v4 error customization: `message`/`invalid_type_error` → unified `error` parameter.
- Downstream slices writing Zod schemas must use v4 API.

#### i18next stack

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| i18next | **26.1.0** | npm registry live | 2026-05-18 |
| react-i18next | **17.0.7** | npm registry live | 2026-05-18 |
| i18next-browser-languagedetector | **8.2.1** | npm registry live | 2026-05-18 |

- react-i18next 17.0.7 requires i18next >=26.0.10 and react >=16.8.0 — all satisfied.
- Package name CONFIRMED: `i18next-browser-languagedetector` (no extra 's', no typo).
- `I18nextProvider` import: `from "react-i18next"`.
- Minimal init without resources: valid — pass `resources: {}`. `t("key")` returns the key.
- Language detector MUST NOT be registered in providers.tsx for T002 — defer to T005.
- jsdom safety: browser detector reads `window.navigator.language`; jsdom provides this mock. Safe.

#### Test dependencies

| Package | Verified version | Source | Cache expires |
|---|---|---|---|
| @testing-library/react | **16.3.2** | npm registry live | 2026-05-18 |
| jsdom | **26.x** (latest) | npm registry | 2026-05-18 |

- RTL peerDeps: `"react": "^18.0.0 || ^19.0.0"` — React 19 fully supported.
- Minimum RTL version for React 19: **v16.1.0** (added 2024-12-05).
- jsdom recommended over happy-dom for React + i18next tests (fuller window.navigator mock).
- vitest.config.ts IS required to set `environment: "jsdom"` — vitest defaults to node env without config.
- Alternative: per-file `// @vitest-environment jsdom` docblock without global config.
- No polyfills needed for providers smoke test in jsdom.

#### Discrepancy notes written for T002

| Note file | Status |
|---|---|
| `frontend-deps-T002-react-router-2026-05-11.md` | UNRESOLVED — developer reconciles |
| `frontend-deps-T002-pins-2026-05-11.md` | Full pin table; UNRESOLVED — developer adds RESOLVED after package.json |

---

### 2026-05-11 — P00-S01-T005 i18n resources ES/EN/FR — deep pass

**Sources**: Context7 /i18next/i18next v26.0.2, /i18next/react-i18next; i18next.com/misc/migration-guide; i18next.com/overview/configuration-options; react.i18next.com/misc/testing.

**Cache valid until**: 2026-05-18 (stable lib — react-i18next, i18next are not AI/ML volatile).

#### i18next v26 breaking changes (verified)

| Breaking change | Impact on T005 |
|---|---|
| `initImmediate` removed (use `initAsync`) | No impact — project never used `initImmediate` |
| Legacy `interpolation.format` monolithic fn removed | No impact — only `escapeValue: false` used |
| `simplifyPluralSuffix` option removed | No impact — option not used |
| `showSupportNotice` + suppression logic removed | No impact — no suppression logic in project |

**v24 note**: `initImmediate` was renamed to `initAsync` in v24. Already irrelevant.
**v23 note**: `returnNull` default changed to `false` — already the correct default; no explicit setting needed.

#### init pattern (inline resources)

- `i18n.use(initReactI18next).init({ resources: {...}, lng, fallbackLng, ns, defaultNS, interpolation, saveMissing, ... })` — canonical for v23/v24/v25/v26 with inline resources. No breaking change in this pattern across versions.
- Inline resources → init is **synchronous**. `i18n.isInitialized === true` immediately after `.init()`.
- With synchronous init, React Suspense is NOT triggered. `useSuspense: false` is not required when bundles are inline.

#### fallbackLng = 'es' (non-English fallback)

- **VERIFIED OK**. `fallbackLng` accepts any language string. The default value in the docs is `'dev'` but any valid language code works. No documented caveat about using Spanish or any non-English language as fallback.
- Fallback chain: if key missing in current language, i18next looks in `fallbackLng`. With `fallbackLng: 'es'`, missing EN/FR keys will fall back to ES values. Correct per instrucciones §3.1.

#### ns array + defaultNS

- `ns: ["common","auth","chat","account","admin-ai","rag","mcp","errors"]` (8 namespaces) is the canonical pattern.
- `defaultNS: "common"` is correct — `t('productName')` resolves from `common` by default.
- Namespace separator: `:` by default. `t('auth:signIn.title')` is canonical.

#### missingKeyHandler: false (redundant but harmless)

- Official API: `missingKeyHandler` is called ONLY when `saveMissing: true`. With `saveMissing: false` (project setting), the handler is never invoked regardless of its value.
- Setting `missingKeyHandler: false` (boolean) is non-standard (docs show function signature), but with `saveMissing: false` it has zero effect. Redundant, not a bug. No change needed.
- For the missing-key test in §8.5: `t('common:doesNotExist')` returns the key string (e.g. `"common:doesNotExist"`) by default when no fallback value exists and `returnNull: false`. This is correct behavior.

#### react-i18next 17 API patterns (verified)

- `useTranslation('namespace')` — canonical for functional components. Unchanged in v17.
- `useTranslation(['ns1', 'ns2'])` — valid (first ns is default for that hook call).
- `I18nextProvider i18n={i18nInstance}` — canonical provider pattern. No change in v17.
- `initReactI18next` plugin — canonical for `.use(initReactI18next)`. No change.
- **React 19 compat**: react-i18next 17.0.7 peerDeps `react >=16.8.0` — React 19.2.6 satisfies. No documented incompatibility.
- `useSuspense: false` in hook options (`useTranslation('ns', { useSuspense: false })`) — valid pattern for disabling Suspense per hook. Not needed with inline resources (sync init), but acceptable to set globally.
- With inline resources and sync init, `ready === true` from first render. No need for `if (!ready) return null` guard.

#### Vite + public/locales/ (inline import, no http backend)

- No official Vite-specific i18next pattern documented.
- Two valid approaches:
  1. **Direct TS import**: `import esCommon from "../../public/locales/es/common.json"` — Vite resolves JSON imports natively. `resolveJsonModule: true` in tsconfig required (confirmed active from T004).
  2. **http backend** with `loadPath: '/locales/{{lng}}/{{ns}}.json'` — planner correctly rejected (YAGNI P0, adds async complexity).
- Approach 1 (inline import) is correct and aligns with "no network request for /locales/**" verify requirement.
- **Vite behavior**: files in `frontend/public/` are served as static assets AND can be imported directly via relative paths from `src/`. Both are valid; direct import preferred for bundle inclusion.

#### Vitest + jsdom + i18next (testing)

- Official approach: `i18n.init({ resources: { en: {...} }, lng: 'en', fallbackLng: 'en' })` inline in test setup — accepted pattern.
- For T005 unit tests (testing i18n module itself, not components): import the real i18n instance + resources directly. No mocking needed.
- For component tests using `useTranslation`: wrap with `I18nextProvider` or use the module-mock pattern. T005 only writes `i18n.test.ts` (not component tests), so no provider wrapping needed.
- Language detector DISABLED (no `window.navigator.language` reads in init) → jsdom safe.
- `await i18n.changeLanguage('fr')` in tests: returns a Promise. Must `await` in async test. `i18n.language` updates synchronously after resolution.
- No documented jsdom-specific issues with i18next when detector is off.

#### Type augmentation (CustomTypeOptions)

- Pattern: `declare module "i18next" { interface CustomTypeOptions { defaultNS: "common"; resources: { common: typeof import("...") } } }` — valid in v23+ TypeScript redesign (requires TS strict mode, already active).
- Optional but recommended for downstream type safety. In-scope for T005 `frontend/src/i18n/types.d.ts`.

#### Outcome: VERIFIED — all planner decisions confirmed

No discrepancy notes written. Developer may proceed without reconciliation.

---

---

### 2026-05-11 — P00-S02-T003 Verification data loader (8 hooks)

**Verified via PyPI live JSON + argon2-cffi ReadTheDocs + Context7 (SQLAlchemy, Alembic, structlog, pydantic) + pgvector GitHub README.**
**Cache valid until**: 2026-05-18 (all stable tech except pgvector Docker tag — check before P01).

#### Hook 1 — argon2-cffi — DISCREPANCY

| Field | Value |
|---|---|
| Latest stable | **25.1.0** (NOT ~23.x as task pack suggested) |
| Python support | >=3.8 incl. 3.12 |
| Key API | `PasswordHasher.hash()`, `.verify()`, `.check_needs_rehash()` |
| verify() exceptions | `VerifyMismatchError` (mismatch), `VerificationError` (other), `InvalidHashError` (bad format) |
| verify_and_update | Does NOT exist — use `verify()` + `check_needs_rehash()` pattern |
| Import | `from argon2 import PasswordHasher; from argon2.exceptions import VerifyMismatchError` |
| Direct dep of argon2-cffi | only `argon2-cffi-bindings`; no cryptography |
| DISCREPANCY NOTE | `P00-S02-T003-argon2-cffi-2026-05-11.md` |
| RECOMMENDED PIN | `argon2-cffi==25.1.0` |

#### Hook 2 — SQLAlchemy 2.0.49 UPSERT — CONFIRMED

`from sqlalchemy.dialects.postgresql import insert; insert(table).values(...).on_conflict_do_update(index_elements=[col_name], set_={col: insert_stmt.excluded.col})` — official API unchanged.

#### Hook 3 — `inspect(engine).has_table()` SQLAlchemy 2.x — CONFIRMED

`from sqlalchemy import inspect; inspect(engine).has_table("tablename")` — official and unchanged in 2.x. Opción C is valid.

#### Hook 4 — Alembic 1.18.4 init structure — CONFIRMED

`alembic init <dir>` generates: `alembic.ini`, `<dir>/env.py`, `<dir>/README`, `<dir>/script.py.mako`, `<dir>/versions/`. Minor: also creates a `README` file (not a `.gitkeep`). Harmless.

#### Hook 5 — structlog 25.5.0 redaction — CONFIRMED

Custom processor pattern: `def redact(logger, method, event_dict): event_dict["password"] = "***"; return event_dict`. Add to `structlog.configure(processors=[..., redact, ...])`. Confirmed best practice.

#### Hook 6 — pgvector deferral — CONFIRMED (with tag note for P01)

Deferral to P01 is correct. When P01 switches, the correct tag is `pgvector/pgvector:pg17-trixie` (NOT `pg17-alpine` — alpine variant is not an official pgvector tag; must compile from source on alpine).

#### Hook 7 — cryptography (Fernet) — DISCREPANCY

NOT a transitive dep from argon2-cffi or psycopg. litellm pulls it only under `proxy` extra (older version 46.0.7) — not guaranteed. Must pin explicitly: `cryptography==48.0.0`.
DISCREPANCY NOTE: `P00-S02-T003-cryptography-fernet-2026-05-11.md`

#### Hook 8 — Pydantic v2.12.5 validators — CONFIRMED

`@field_validator`, `@model_validator(mode='after')`, `model_config = ConfigDict(...)` — all confirmed. Do NOT mix `class Config:` with `model_config` (raises PydanticUserError).

---

## Notes for next researcher

- React 19.2.6 human-confirmed 2026-05-11. No re-verify needed until 2026-05-18.
- Backend stable packages (sqlalchemy, alembic, celery, redis, etc.) cache valid until 2026-05-18.
- AI/ML packages (litellm, langchain, langgraph, deepagents, mcp) ALWAYS re-verify — volatile ecosystem.
- deepagents discrepancy note `T003-discrepancy-deepagents.md` is `RESOLVED: pending` — developer documents in handoff.
- Frontend deps T002 all verified 2026-05-11. Re-verify after 2026-05-18.
- Zod v4 is current stable — downstream slices must use v4 API (no `.email()` chain; use `z.email()`).
- @hookform/resolvers v5.2.2 bridges both Zod v3 and v4 — no split package needed.
- react-router v7: canonical install is `react-router`; imports from `"react-router"`.
- i18next T005 fully verified 2026-05-11 (cache until 2026-05-18). All planner decisions confirmed. No discrepancy notes. See section above for full details.
- P00-S02-T003 two discrepancy notes written 2026-05-11: argon2-cffi==25.1.0 (not ~23.x) and cryptography==48.0.0 (must be explicit dep).
- pgvector Docker tag for P01 is `pgvector/pgvector:pg17-trixie` (NOT pg17-alpine).
- MEMORY.md well over 200 lines. Strongly recommend `/slice-maintain compact-agent-memory` after this slice.
