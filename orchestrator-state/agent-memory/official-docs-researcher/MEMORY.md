# official-docs-researcher MEMORY

## Session cache

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
