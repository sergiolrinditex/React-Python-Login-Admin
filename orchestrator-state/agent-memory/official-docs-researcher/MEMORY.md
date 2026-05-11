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

## Notes for next researcher

- React 19.2.6 human-confirmed 2026-05-11. No re-verify needed until 2026-05-18.
- Backend stable packages (sqlalchemy, alembic, celery, redis, etc.) cache valid until 2026-05-18.
- AI/ML packages (litellm, langchain, langgraph, deepagents, mcp) ALWAYS re-verify — volatile ecosystem.
- deepagents discrepancy note `T003-discrepancy-deepagents.md` is `RESOLVED: pending` — developer documents in handoff.
- Frontend deps T002 all verified 2026-05-11. Re-verify after 2026-05-18.
- Zod v4 is current stable — downstream slices must use v4 API (no `.email()` chain; use `z.email()`).
- @hookform/resolvers v5.2.2 bridges both Zod v3 and v4 — no split package needed.
- react-router v7: canonical install is `react-router`; imports from `"react-router"`.
- i18next-browser-languagedetector: install in T005, NOT in providers.tsx (browser-only init, defer).
