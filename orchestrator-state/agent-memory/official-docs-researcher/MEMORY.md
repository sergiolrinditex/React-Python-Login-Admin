# official-docs-researcher MEMORY

## Session cache

### Entry 2026-05-09 — P00-S02-T002 Health live/ready endpoints (SHALLOW PASS — all verified)

**Note file**: `orchestrator-state/memory/official-doc-notes/P00-S02-T002-health-endpoints-patterns-2026-05-09.md`
**Freshness window**: All patterns stable — re-verify after 7 days (2026-05-16). structlog / SQLAlchemy / httpx / pytest-asyncio: stable; FastAPI 0.136.1 confirmed in project venv.

#### Cache stamps (2026-05-09)

| # | Pattern | Status | Finding |
|---|---|---|---|
| 1 | FastAPI router include + ops | VERIFIED | `app.include_router(router)` canonical; `@app.middleware("http")` for request_id middleware |
| 2 | SQLAlchemy 2.0 async SELECT 1 | VERIFIED | `async with engine.connect() as conn: await conn.execute(text("SELECT 1"))` |
| 3 | SQLAlchemy/asyncpg exception for DB down | VERIFIED | Catch `sqlalchemy.exc.SQLAlchemyError` — covers OperationalError + InterfaceError; asyncpg raw exceptions NOT exposed |
| 4 | structlog 25.5.0 contextvars API | VERIFIED | `structlog.contextvars.bind_contextvars` / `clear_contextvars` confirmed present and unchanged |
| 5 | httpx 0.28 ASGITransport | VERIFIED | `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` — `app=` param removed in 0.28 |
| 6 | pytest-asyncio 1.3.0 auto mode | VERIFIED | `asyncio_mode="auto"` confirmed in pyproject.toml line 122; no decorator needed |

#### Environment finding (non-blocking)

System `python3` has FastAPI 0.135.2; project venv `.venv-t003` has 0.136.1 (correct). Developer must use project venv.

#### Discrepancies: NONE

---

### Entry 2026-05-09 — P00-S01-T005 i18n resources ES/EN/FR (DEEP PASS — targeted)

#### Sources consulted

- Context7 `/i18next/i18next/v26.0.2` — init API, fallbackLng, ns, defaultNS, resources, supportedLngs, interpolation
- Context7 `/i18next/react-i18next` — initReactI18next, useSuspense, I18nextProvider, TypeScript
- Context7 `/websites/vite_dev` — JSON imports, publicDir behavior, import.meta.glob eager

#### Pinned versions confirmed (from frontend/package.json read 2026-05-09)

| Package | Pinned version | Status |
|---|---|---|
| i18next | 26.0.10 | Current stable in Context7 catalog (v26.0.2 docs apply — same major.minor) |
| react-i18next | 17.0.7 | Current stable |
| i18next-browser-languagedetector | 8.2.1 | Installed; NOT to be registered in T005 (see D4) |
| vite | 8.0.11 | Confirmed; publicDir behavior verified |

#### Verified API patterns for i18next 26 + react-i18next 17

| Pattern | Confirmed | Notes |
|---|---|---|
| `i18n.use(initReactI18next).init({...})` | YES | Canonical chain; unchanged in v17 |
| `fallbackLng: 'es'` (string, singular) | YES | Docs show `fallbackLng: 'en'` (string) as primary example; `string \| string[]` both valid |
| `ns: ['common', 'auth', ...]` (array of strings) | YES | Confirmed property name; array accepted |
| `defaultNS: 'common'` | YES | Confirmed property name |
| `resources: { es: { common: {...} }, en: {...} }` | YES | Canonical inline/eager pattern, unchanged |
| `supportedLngs: ['es', 'en', 'fr']` | YES | Current property name (replaced `whitelist` in i18next 21+) — NOT `whitelist` |
| `interpolation: { escapeValue: false }` | YES | Documented: "React already escapes values" |
| `react: { useSuspense: true }` | YES (but defer) | Property name confirmed as `useSuspense` inside `react:{}` option. Default is `true` in v17. Task D3 uses eager loading → sync → useSuspense default fine; OR set false explicitly |
| `initReactI18next` import | YES | `import { initReactI18next } from 'react-i18next'` — unchanged |

#### Deprecations / renamed props confirmed

- `whitelist` → `supportedLngs` (changed in i18next 21, still current in v26) — developer must NOT use `whitelist`.
- `cleanCode`/`lowerCaseLng`: no changes noted in v26 docs for these defaults.
- `react.useSuspense` default is `true` in react-i18next v17. For eager/sync loading (D3), this is harmless — translations resolve before first render. No need to set `useSuspense: false` unless the developer wants explicit control.

#### Critical finding — Vite publicDir + static import conflict

**DISCREPANCY NOTE WRITTEN**: `orchestrator-state/memory/official-doc-notes/P00-S01-T005-i18n-vite-public-vs-src-import.md`

Summary: Vite's official docs confirm `publicDir` files are "not referenced in source code" — they are copied as-is, not processed by Rollup. However, static `import` from `src/` that resolves via filesystem path into `public/locales/` DOES work (Rollup follows the filesystem, not the public-dir serving boundary). The result is double-shipping (bundled + copied). The planner's D3 is architecturally consistent but developer must choose explicitly between Option A (accept double-ship, keep `public/locales/`) or Option B (move to `src/i18n/locales/`, cleaner, no duplication).

This is a medium-severity architectural note — NOT a blocker. Both options compile and test correctly.

#### Vitest + JSON imports

Static `import foo from '…/file.json'` works natively in Vitest (uses Vite's module resolver). No `transform` config needed. `import.meta.glob('./locales/**/*.json', { eager: true })` is also valid if developer prefers dynamic enumeration for the test file; both patterns confirmed.

#### Note file written

`orchestrator-state/memory/official-doc-notes/P00-S01-T005-i18n-vite-public-vs-src-import.md`
Severity: medium. Requires developer to explicitly choose Option A or B and add RESOLVED line.

#### Freshness window

- i18next/react-i18next: stable; re-verify after 7 days (2026-05-16).
- Vite 8 publicDir behavior: stable; re-verify after 7 days (2026-05-16).

---

### Entry 2026-05-09 — P00-S01-T004 Design tokens + editorial system (shallow pass)

#### Sources consulted

- Context7 `/vitejs/vite/v8.0.0` — Vite 8 entry pattern, vite.config.ts defineConfig, test config co-location
- Context7 `/vitest-dev/vitest/v4.0.7` — Vitest 4 defineConfig, environment jsdom, setupFiles
- Context7 `/remix-run/react-router` — v7 minimal createBrowserRouter + RouterProvider pattern
- Context7 `/facebook/react/v19_2_0` — React 19 createRoot, main.tsx mount pattern
- Context7 `/testing-library/jest-dom` — v6 Vitest-specific setup file import path

#### Verified patterns (2026-05-09)

| Topic | Finding | Status |
|---|---|---|
| Vite 8 entry | `index.html` at root + `<script type="module" src="/src/main.tsx">` — canonical, unchanged | OK |
| vite.config.ts | `import { defineConfig } from 'vite'` — unchanged in Vite 8 | OK |
| Vitest config split | Co-location in `vite.config.ts` test block AND separate `vitest.config.ts` both valid; separate NOT mandatory | OK |
| TS 6 tsconfig | `"moduleResolution": "bundler"`, `"verbatimModuleSyntax": true`, `"jsx": "react-jsx"`, `"isolatedModules": true` — all confirmed; task pack R6 already correct | OK |
| React 19 createRoot | `import { createRoot } from 'react-dom/client'` — canonical, unchanged. New additive: `onUncaughtError`/`onCaughtError` opts | OK |
| react-router v7 minimal | `import { createBrowserRouter } from 'react-router'` + `import { RouterProvider } from 'react-router/dom'`; `<BrowserRouter>` not deprecated but `createBrowserRouter` is recommended | OK |
| @testing-library/jest-dom v6 Vitest setup | **ACTIONABLE**: Setup file must use `import '@testing-library/jest-dom/vitest'` NOT `extend-expect`. Note written. | NOTE |

#### Note file written

`orchestrator-state/memory/official-doc-notes/P00-S01-T004-testing-library-vitest-setup.md`
Severity: warn-only. Developer must use the correct import path. Note contains `RESOLVED:` line.

#### Discrepancies found

ONE actionable finding (warn-only, not blocking): `@testing-library/jest-dom/vitest` import path for Vitest setup. Not a version mismatch — a configuration pattern that could silently break if using the v5/Jest form. Task pack did not specify the exact import path. Note written with `RESOLVED:` line.

#### Freshness window

All stack components verified 2026-05-09 — re-verify after 7 days (2026-05-16).
react-router v7 still in active development — re-verify on any router-touching slice.

---

### Entry 2026-05-08 — P00-S01-T001 scaffold pass

#### Sources consulted

- Context7 `/fastapi/fastapi` (versions listed: 0.115.13, 0_116_1, 0.118.2, 0.122.0, 0.128.0) — Source Reputation: High
- Context7 `/facebook/react` (versions listed: v18_3_1, v19_1_1, v19_2_0, v17.0.2) — Source Reputation: High
- Context7 `/vitejs/vite` (versions listed: v7.0.0, v5.4.21, v8.0.0, v7.3.1, v8.0.7, v8.0.10) — Source Reputation: High
- Context7 `/vitest-dev/vitest` (versions listed: v3_2_4, v4.0.7) — Source Reputation: High

#### Verified versions (2026-05-08)

| Technology | Latest stable | Notes |
|---|---|---|
| FastAPI | **0.128.0** | Highest version in Context7 catalog; confirmed stable. Import: `from fastapi import FastAPI`. `app = FastAPI()` + `@app.get("/health")` pattern unchanged from 0.10x. |
| Uvicorn | Compatible with FastAPI 0.128.0 | Canonical command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`. No import changes. `uvicorn[standard]` is still recommended for production (websockets, watchfiles). |
| React + react-dom | **19.2.0** (latest), 18.3.1 also stable | Both are stable. React 19 is the current recommended version. react-dom must match react version. |
| Vite | **8.0.10** (latest), 7.3.1 also stable | Vite 8 requires Node 22.12+. Vite 7 requires Node 20+. `@vitejs/plugin-react` is still the standard React plugin. Vue template in create-vite shows `vite: "^8.0.8"` as of this date. |
| @vitejs/plugin-react | ~6.x (aligned with Vite 8) | Used as `plugins: [react()]` in vite.config.ts. No API change. |
| TypeScript | **~6.0.2** | create-vite Vue+TS template shows `typescript: "~6.0.2"`. |
| Vitest | **4.0.7** (latest), 3.2.4 also stable | Vitest 4 requires **Vite >= 6.0.0** and **Node >= 20.0.0**. Vitest current stable (4.0.7) requires Vite 6.4.0+ per the docs ("Vitest requires Vite version 6.4.0 or higher and Node.js version 22.12.0 or higher"). |

#### Canonical FastAPI pattern (unchanged from 0.10x)

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}
```

No breaking changes in imports or app instantiation between 0.10x and 0.128.0.

#### Key compatibility matrix

- Vitest 4 requires Vite 6.4.0+ and Node 22.12.0+
- Vitest 3 requires Vite 6.0.0+ and Node 20.0.0+
- Vite 8 requires Node 22.12.0+
- Vite 7 requires Node 20.0.0+
- React 19 is the current stable; React 18.3.1 remains LTS-like
- React 19 + Vite 8 + Vitest 4 is a fully consistent modern stack

#### Discrepancies found

NONE. The source-of-truth (STACK_PROFILE.yaml, instrucciones.md, TECHNICAL_GUIDE) declares framework names without version pins. The official latest stable versions are all compatible with each other and with the declared stack. No note opened.

#### Freshness window

- FastAPI: stable framework — re-verify after 7 days
- React: stable framework — re-verify after 7 days
- Vite/Vitest: stable frameworks — re-verify after 7 days
- Next check recommended after: 2026-05-15

#### Task scope

Verified for: P00-S01-T001 (scaffold only — `backend/app/main.py` + `frontend/package.json` stubs).
NOT verified yet (reserved for their respective tasks):
- SQLAlchemy, Alembic, pgvector — T002/T003
- LangChain, LangGraph, LiteLLM, DeepAgents — T003 (AI/ML volatile, MUST re-verify)
- React Router, TanStack Query, react-hook-form, Zod, i18next — T002
- Celery, Redis — T003
- pytest-asyncio, httpx, @testing-library/react — T002/T003

---

### Entry 2026-05-08 — P00-S01-T002 Frontend dependency pack

#### Sources consulted

- npm registry live queries (2026-05-08): `npm view <pkg> version peerDependencies --json`
- Context7 `/remix-run/react-router` (Source Reputation: High) — v7 breaking changes + package consolidation
- Context7 `/react-hook-form/resolvers` (Source Reputation: High) — zod v3/v4 resolver support
- Context7 `/websites/zod_dev_v4` (Source Reputation: High) — zod v4 breaking changes

#### Verified versions (2026-05-08)

| Package | Latest stable (`npm latest` tag) | peerDeps React | peerDeps TS | Notes |
|---|---|---|---|---|
| `react-router-dom` | **7.15.0** | `>= 18` (covers 19) | — | v7 is a thin wrapper over `react-router@7.15.0`; both install together. `BrowserRouter` still exported for library mode. `createBrowserRouter` recommended for data mode. |
| `@tanstack/react-query` | **5.100.9** | `^18 \|\| ^19` | — | v5 stable; React 19 fully supported. `gcTime` replaced `cacheTime` in v5. No `onError`/`onSuccess` on `useQuery`. |
| `react-hook-form` | **7.75.0** | `^16.8 \|\| ^17 \|\| ^18 \|\| ^19` | — | React 19 compatible. |
| `zod` | **4.4.3** | — | no peerDep (TS 6 compat) | v4 is `latest`; v3 is paradoxically on `next` tag (3.25.x beta). Major rewrite: `z.coerce` input now `unknown`, `.merge()` deprecated, defaults in optional changed. |
| `@hookform/resolvers` | **5.2.2** | — | — | peerDep: `react-hook-form ^7.55.0` (satisfied by 7.75.0). Supports zod v3 AND v4. Import: `from 'zod'` (top-level re-exports v4 in zod@4.x); `from 'zod/v4'` only needed if mixing v3+v4. |
| `i18next` | **26.0.10** | — | `^5 \|\| ^6` | TS 6 compatible. |
| `react-i18next` | **17.0.7** | `>= 16.8.0` (covers 19) | `^5 \|\| ^6` | peerDep on `i18next >= 26.0.10` — tight: our pin 26.0.10 satisfies exactly. TS 6 compatible. |
| `i18next-browser-languagedetector` | **8.2.1** | — | — | No peerDeps listed. |

#### Additional testing-lib packages queried (also for T002)

| Package | Version |
|---|---|
| `@testing-library/react` | **16.3.2** — peerDeps `react ^18 \|\| ^19`, `react-dom ^18 \|\| ^19`, `@types/react ^18 \|\| ^19` |
| `@testing-library/jest-dom` | **6.9.1** — no React peerDep |
| `jsdom` | **29.1.1** |
| `@testing-library/dom` | **10.4.1** |

#### Key compatibility findings

- All 8 primary packages satisfy React 19.2.6 peerDeps.
- All TS-sensitive packages (i18next, react-i18next) declare `^5 || ^6` — TS 6.0.3 satisfied.
- zod v4 (not v3) is `latest`. v3 lives under `next` dist-tag. Pin `zod@4.4.3`.
- `@hookform/resolvers@5.2.2` supports both zod versions. Use plain `'zod'` import for v4 in a fresh project.
- `react-router-dom@7.15.0` is v7 (the active major). v6 is pinned at `6.30.3` under the `version-6` dist-tag. Do NOT install `react-router-dom@6.x` — use v7.

#### Discrepancies / notes opened

Two notes written (not blockers — informational/architectural):
1. `orchestrator-state/memory/official-doc-notes/P00-S01-T002-react-router-v7-consolidation.md`
   — Architect note: v7 `react-router-dom` is a re-export wrapper; `BrowserRouter` still present but `createBrowserRouter` is recommended data-mode API. P01-S03-T001 planner must decide.
2. `orchestrator-state/memory/official-doc-notes/P00-S01-T002-zod-v4-hookform-resolvers.md`
   — Zod v4 breaking changes + `@hookform/resolvers` import path; fresh-start project uses `import { z } from 'zod'` (top-level re-exports v4).

Both notes have `RESOLVED: <placeholder>` — developer must fill after reconciling.

#### Freshness window

- These packages: stable; re-verify after 7 days (2026-05-15), EXCEPT if a new major lands.
- react-router v7 in active development (frequent minor/pre releases observed) — re-verify on any router-touching slice.

#### Task scope

Verified for: P00-S01-T002 (frontend dependency pack — 8 primary packages + 4 testing packages).

---

### Entry 2026-05-09 — P00-S02-T001 Docker compose image tags (DEEP PASS — all new topics)

**Note file**: `orchestrator-state/memory/official-doc-notes/P00-S02-T001-compose-images.md`
**Freshness window**: Docker image tags — re-verify after 7 days (2026-05-16). LiteLLM — re-verify BEFORE ANY BUMP (AI/ML volatile).

#### Cache stamps (2026-05-09)

| Topic | Verified tag / finding | Re-verify |
|---|---|---|
| pgvector Docker image | `pgvector/pgvector:pg18-bookworm` (pgvector 0.8.2, PG18 stable) | 7 days |
| Redis Docker image | `redis:8-alpine` = Redis 8.6.3 (current stable/latest) | 7 days |
| redis:7.4-alpine | OUTDATED — task pack candidate was stale | 7 days |
| kombu 5.6.2 redis client constraint | `>=4.5.2,<6.5` — redis==6.4.0 IS COMPATIBLE | 7 days |
| Celery 5.6.3 | Still latest; no 5.6.4+ released as of 2026-05-09 | 7 days |
| Redis server 8.x + kombu | Constraints are on Python client only; server 8.x compatible | 7 days |
| LiteLLM proxy image | `ghcr.io/berriai/litellm:v1.83.14-stable` (NOT `main-stable`) | BEFORE ANY BUMP |
| LiteLLM latest release | v1.83.14-stable.patch.3 (2026-05-07) | BEFORE ANY BUMP |
| LiteLLM healthcheck | `/health/liveliness` (note: "liveliness" not "liveness") | BEFORE ANY BUMP |
| LiteLLM config.yaml schema | `model_list`, `general_settings.master_key`, optional `litellm_settings` | BEFORE ANY BUMP |
| MinIO Docker image | `minio/minio:RELEASE.2025-09-07T16-13-09Z` (or `latest` + digest) | 7 days |
| MinIO healthcheck | `/minio/health/live` (liveness) — CORRECT per official docs | 7 days |
| MinIO canonical registry | Docker Hub `minio/minio` | 7 days |
| Python 3.13-slim | `python:3.13-slim-bookworm` = 3.13.13, digest sha256:bb73517d..., pushed 2026-04-22 | 7 days |
| Python trixie drift | Trixie tags EXIST but bookworm is still stable default | 7 days |
| nginx-unprivileged | `nginxinc/nginx-unprivileged:1.29-alpine` (1.27 does NOT exist, 1.29 is current) | 7 days |
| nginx-unprivileged UID | 101 (nginx user); default port 8080 | 7 days |

#### Discrepancies found (require developer action)

1. **MEDIUM** — `redis:7.4-alpine` (task pack candidate) is outdated. Use `redis:8-alpine`.
2. **MEDIUM** — `nginxinc/nginx-unprivileged:1.27-alpine` does NOT exist. Use `1.29-alpine`.
3. **LOW** — `ghcr.io/berriai/litellm:main-stable` is floating/non-immutable. Pin to `v1.83.14-stable`.
4. **LOW (note)** — `pgvector/pgvector:pg18` valid but `pg18-bookworm` is more explicit.
5. **LOW (note)** — MinIO `latest` acceptable for dev; pin by SHA256 digest before P06 (production).

---

### Entry 2026-05-08 — P00-S01-T003 Backend dependency pack (DEEP PASS — user requested re-verify all)

**Source**: PyPI JSON API `pypi.org/pypi/<name>/json` — 37 parallel fetches + 7 follow-up fetches. Full deep pass per user instruction "busca las últimas versiones porque hay versiones más nuevas".
**Note file**: `orchestrator-state/memory/official-doc-notes/P00-S01-T003-backend-deps.md`
**Freshness window**: AI/ML ecosystem deps (litellm, langchain*, langgraph, deepagents, mcp) — re-verify before ANY bump (weekly volatility). All others — 7 days (2026-05-15).

#### Verified versions (2026-05-08)

| Package | Latest stable | Re-verify |
|---|---|---|
| fastapi | 0.136.1 | 7 days |
| uvicorn | 0.46.0 | 7 days |
| httpx | 0.28.1 | 7 days |
| python-multipart | 0.0.27 | 7 days |
| sqlalchemy | 2.0.49 | 7 days |
| asyncpg | 0.31.0 | 7 days |
| alembic | 1.18.4 | 7 days |
| pgvector | 0.4.2 | 7 days |
| pydantic | 2.13.4 (declare as range — litellm forces 2.12.5) | 7 days |
| pydantic-settings | 2.14.1 | 7 days |
| structlog | 25.5.0 | 7 days |
| prometheus-client | 0.25.0 | 7 days |
| celery | 5.6.3 | 7 days |
| redis | 7.4.0 | 7 days |
| argon2-cffi | 25.1.0 | 7 days |
| PyJWT | 2.12.1 | 7 days |
| cryptography | 48.0.0 | 7 days |
| itsdangerous | 2.2.0 | 7 days |
| pypdf | 6.10.2 | 7 days |
| python-docx | 1.2.0 | 7 days |
| resend | 2.30.0 | 7 days |
| boto3 | 1.43.6 | 7 days |
| litellm | 1.83.14 | BEFORE ANY BUMP |
| langchain | 1.2.18 | BEFORE ANY BUMP |
| langchain-core | 1.3.3 | BEFORE ANY BUMP |
| langchain-community | 0.4.1 | BEFORE ANY BUMP |
| langchain-text-splitters | 1.1.2 | BEFORE ANY BUMP |
| langgraph | 1.1.10 | BEFORE ANY BUMP |
| deepagents | 0.5.7 | BEFORE ANY BUMP |
| mcp | 1.27.1 | BEFORE ANY BUMP |
| tiktoken | 0.12.0 | BEFORE ANY BUMP |
| ruff | 0.15.12 | 7 days |
| mypy | 2.0.0 | 7 days |
| pytest | 9.0.3 | 7 days |
| pytest-asyncio | 1.3.0 | 7 days |
| pytest-cov | 7.1.0 | 7 days |
| pip-audit | 2.10.0 | 7 days |
| psycopg2-binary | 2.9.12 | NOT declared (asyncpg sufficient) |
| python-jose | 3.5.0 | NOT used (PyJWT chosen) |

#### Key findings from T003 deep pass

1. **CRITICAL — pydantic exact-pin conflict**: litellm==1.83.14 pins `pydantic==2.12.5` exactly. Declare pydantic with range `>=2.7.4,<3.0.0` in pyproject; pip resolves to 2.12.5. Do NOT pin `pydantic==2.13.4`.
2. **JWT decision**: pyjwt[crypto]==2.12.1 chosen. python-jose NOT declared.
3. **Alembic + asyncpg**: asyncpg alone covers both SQLAlchemy async ORM and Alembic async migrations (`async_engine_from_config` via `run_sync`). No psycopg2-binary needed.
4. **langchain-community 0.x**: stays at 0.x numbering (0.4.1) — separate release track from langchain-core 1.x. Fully compatible.
5. **deepagents**: requires Python>=3.11 (matches project) + pulls langchain-anthropic>=1.4.3 as transitive dep.
6. **mcp 1.27.1**: CONFIRMED official Anthropic SDK (Author: Anthropic, PBC; Homepage: modelcontextprotocol.io). Correct canonical package name is `mcp`.
7. **langchain 1.2.18 constraint**: requires `langchain-core>=1.3.3,<2.0.0` AND `langgraph>=1.1.10,<1.2.0` — satisfied by our pin table.
8. **T001 pinned versions**: fastapi 0.136.1, uvicorn 0.46.0, ruff 0.15.12, mypy 2.0.0, pytest 9.0.3, pytest-asyncio 1.3.0, httpx 0.28.1 — ALL still at latest. T001 pins were correct.
9. **All 37 deps verified Python 3.11 compatible**: no gaps found.
10. **litellm peer constraints**: also pins httpx==0.28.1 (matches our pin) and tiktoken==0.12.0 (matches our pin). Only pydantic is the conflict.

---

### Entry 2026-05-09 — P00-S02-T003 Seed data + verification bundle (SHALLOW/TARGETED PASS)

**Freshness window**: All stable topics — re-verify after 7 days (2026-05-16). pyotp status: not in lockfile, confirmed 2026-05-09; re-verify only if lockfile changes.

#### Topic verdicts (2026-05-09)

| # | Topic | Verdict | Finding |
|---|---|---|---|
| 1 | SQLAlchemy 2.0 async upsert `INSERT...ON CONFLICT DO UPDATE` | OK | `from sqlalchemy.dialects.postgresql import insert` + `.on_conflict_do_update(index_elements=[...], set_={...})` confirmed canonical. `await session.execute(stmt)` works via `AsyncSession`. No version change in 2.0.49. |
| 2 | `inspect(...).has_table(...)` over async engine | OK | Official pattern confirmed: `await conn.run_sync(lambda sync_conn: inspect(sync_conn).has_table('users'))`. Docs explicitly state "SQLAlchemy does not yet offer an asyncio version of Inspector" → must use `run_sync`. Also valid: `inspect(sync_conn).get_table_names()`. |
| 3 | argparse vs typer/click on Python 3.13 | OK | argparse is NOT deprecated in 3.13. Python docs explicitly call it "the default recommended standard library module." Only enhancements in 3.13 (new `deprecated` param on `add_argument`). Stay with argparse for T003 CLI. |
| 4 | pytest-asyncio 1.3.0 asyncio_mode | OK (cache) | `asyncio_mode="auto"` confirmed set in project's `pyproject.toml` line 122 (T002 cache). Auto mode picks up `async def test_*` without decorators. |
| 5 | structlog 25.5.0 `capture_logs` | OK | `from structlog.testing import capture_logs` confirmed unchanged. Context manager returns list of dicts; each dict has `event`, `log_level`, and any bound keys. Pattern for assertion: `assert cap_logs[0]["event"] == "seed.namespace.start"`. |
| 6 | Pydantic 2.12.5 `ConfigDict(extra='forbid', strict=True)` | OK | Both `extra` and `strict` are valid `ConfigDict` keys in Pydantic 2.x. `extra='forbid'` rejects unknown fields. `strict=True` disables type coercion. `model_config = ConfigDict(extra='forbid', strict=True)` is the canonical 2.x form. |
| 7 | `docker compose down -v` semantics | OK (clarified) | `-v` removes ALL named volumes in the project (not per-service). BUT: `dev-restart.sh --reset` does NOT call `docker compose down -v` — it uses `alembic downgrade base + upgrade head` for DB reset, which is schema-only and does NOT touch Docker volumes at all. Safe pattern confirmed: the existing dev-restart.sh wiring is correct and does not risk minio/redis volumes. |
| 8 | pyotp | DISCREPANCY | pyotp is NOT in `backend/pyproject.toml` and NOT a transitive dep of mcp==1.27.1 or any other package in the lockfile. Developer MUST NOT use `pyotp.random_base32()`. Use static base32 string in JSON fixture instead. Note written: `P00-S02-T003-pyotp-not-in-lockfile-2026-05-09.md`. |
| 9 | asyncpg + ON CONFLICT + SQLAlchemy 2.0 | OK | SQLAlchemy docs show no asyncpg-specific gotchas for ON CONFLICT DO UPDATE. The upsert is a dialect-level feature; asyncpg receives it as a parameterized PostgreSQL statement. No parameter style issues documented. |

#### Key findings

- **SQLAlchemy upsert pattern**: `from sqlalchemy.dialects.postgresql import insert` → `.on_conflict_do_update(index_elements=[col_or_name], set_={...})` → `await session.execute(stmt)`. Confirmed for 2.0.49+asyncpg.
- **Natural key upsert WITHOUT DB-side UNIQUE**: The SQLAlchemy ON CONFLICT requires a unique constraint or index on the conflict column(s) at the DB level. For `users.email` this is fine (UNIQUE per §10.3). For `ai_providers.name`, `mcp_servers.name`, `agents.name`, `rag_collections.name` — if these tables don't have UNIQUE constraints yet (they don't exist yet in T003), the `on_conflict_do_update(index_elements=['name'])` will FAIL at runtime unless the column has a unique constraint. Since T003's tables don't exist yet, this is deferred to when the tables land (P01-S01-T001, P02-S01-T001). The loader's "table missing" WARN path will be triggered for all namespaces except `auth`. No action needed for T003 scope — but developer should add a docstring explaining that upsert depends on a UNIQUE constraint that will exist when the migration lands.
- **structlog capture_logs**: import path `from structlog.testing import capture_logs` unchanged in 25.5.0. Inside context manager all configured processors are disabled; captured records are plain dicts.
- **pyotp**: NOT in lockfile; NOT transitive. Use static base32 string. Discrepancy note written.
- **dev-restart.sh --reset**: already uses `alembic downgrade/upgrade` approach — does NOT touch Docker volumes. The compose file comment `docker compose down -v` → "DELETE volumes (data loss!)" is a developer warning in the usage docs, not a command that dev-restart.sh calls. T003 wiring verification should confirm loader is importable and the `python -c "import app.seeds.bootstrap_verification_data"` guard fires correctly.

#### Sources consulted

- Context7 `/websites/sqlalchemy_en_20` — async upsert, run_sync, AsyncSession.execute
- Context7 `/hynek/structlog` — capture_logs, LogCapture, testing API
- WebFetch `https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html` — has_table via run_sync pattern
- WebFetch `https://pydantic.dev/docs/validation/latest/api/pydantic/config/` — ConfigDict strict + extra
- WebFetch `https://docs.python.org/3.13/library/argparse.html` — argparse status in 3.13
- WebFetch `https://pypi.org/pypi/pyotp/json` — pyotp 2.9.0, no runtime deps
- WebFetch `https://pypi.org/pypi/mcp/1.27.1/json` — mcp 1.27.1 deps (pyotp absent)
- WebFetch `https://docs.docker.com/reference/cli/docker/compose/down/` — down -v semantics
- Local file reads: `scripts/dev-restart.sh`, `scripts/dev-restart.profile.sh`, `docker-compose.yml`
- T002 cache (2026-05-09): pytest-asyncio asyncio_mode=auto confirmed in pyproject.toml line 122

---

### Entry 2026-05-09 — P00-S02-T004 structlog 25.5.0 RichTracebackFormatter / ConsoleRenderer / frame-locals redaction (DEEP PASS)

**Freshness window**: structlog is a stable framework — re-verify after 7 days (2026-05-16).

#### Sources consulted

- Context7 `/hynek/structlog` — ConsoleRenderer, RichTracebackFormatter, exception_formatter API
- Context7 `/websites/structlog_en_stable` — stable docs processors, recipes
- WebFetch `https://www.structlog.org/en/stable/api.html` — full constructor signatures
- WebFetch `https://github.com/hynek/structlog/releases` — changelog 24.x → 25.5.0
- WebFetch `https://rich.readthedocs.io/en/stable/traceback.html` — Rich Traceback show_locals cross-check

#### Verified API surface for structlog 25.5.0

| # | Question | Answer | Source |
|---|---|---|---|
| 1 | Import path for `RichTracebackFormatter` | `structlog.dev.RichTracebackFormatter` | structlog API docs + Context7 |
| 2 | Constructor signature | `RichTracebackFormatter(color_system='truecolor', show_locals=True, max_frames=100, theme=None, word_wrap=True, extra_lines=3, width=None, code_width=88, indent_guides=True, locals_max_length=10, locals_max_string=80, locals_hide_dunder=True, locals_hide_sunder=False, suppress=())` | structlog API docs |
| 3 | `show_locals` default | `True` — frame locals displayed by default | structlog API docs |
| 4 | `show_locals=False` effect | Suppresses all frame-local variable display in Rich tracebacks | Rich docs + structlog docs |
| 5 | `ConsoleRenderer` `exception_formatter=` kwarg | YES — confirmed present, accepts callable. In 25.5.0 it is also settable as mutable attribute post-instantiation via `ConsoleRenderer.get_active().exception_formatter = ...` | structlog 25.5.0 release notes + Context7 |
| 6 | Built-in structlog redaction processor for frame locals | NONE — no built-in processor walks frame locals. `_redaction_processor` on event_dict keys is not sufficient; frame locals live inside the exc_info tuple, opaque to dict-level processors | structlog API docs |
| 7 | JSONRenderer + frame locals | JSONRenderer uses stdlib `traceback.format_exception` — does NOT include frame locals by default. The leak is Console-renderer-only (verbose=true path) | task pack + confirmed |
| 8 | ENABLE_VERBOSE_LOGGING competing structlog setting | NONE — structlog has no built-in verbose/quiet flag that would override `show_locals=False`. Project's env-var-based toggle is the only gate | structlog docs |
| 9 | 24.x → 25.x breaking changes affecting this slice | NONE affecting `show_locals` or `exception_formatter`. Only breaking change in 25.x affecting ConsoleRenderer is `pad_event` → `pad_event_to` rename (not used in this project's logging.py) | structlog release changelog |
| 10 | `ExceptionDictTransformer` (structured tracebacks) | Accepts `show_locals=True/False` also, but applies to JSONRenderer dict path only | Context7 |

#### Planner's Option C validation

The task pack recommends "Option C — Hybrid":
```python
renderer = structlog.dev.ConsoleRenderer(
    exception_formatter=structlog.dev.RichTracebackFormatter(show_locals=False),
)
```
This pattern is **fully correct** for structlog 25.5.0:
- `structlog.dev.RichTracebackFormatter` — correct import.
- `show_locals=False` — correct kwarg name, suppresses frame locals.
- `ConsoleRenderer(exception_formatter=...)` — correct wiring kwarg.

No newer redaction API exists in structlog 25.5.0 that would supersede this approach.

#### Additional finding — `format_exc_info` processor (JSON path)

When using `structlog.processors.format_exc_info` (converts exc_info to formatted string for JSON output), the stdlib `traceback.format_exception` is used internally — this does NOT include frame locals. Defense in depth for the JSON path is already satisfied. Confirmed not a concern.

#### Discrepancies: NONE

The planner's intended pattern (Option C) is correct and consistent with structlog 25.5.0 official API. No discrepancy note required.
