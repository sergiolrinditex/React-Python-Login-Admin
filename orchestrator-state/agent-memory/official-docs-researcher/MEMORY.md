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
