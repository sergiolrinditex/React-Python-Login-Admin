# Official Docs Researcher Memory

Last updated: 2026-05-11
Agent: official-docs-researcher

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

## Notes for next researcher

- React version choice (18 vs 19) must be resolved by human before T002 installs deps. DISCREPANCY note is live and unresolved.
- Backend versions are non-controversial — pin to latest stable.
- AI/ML stack (LiteLLM, LangChain, LangGraph, DeepAgents) was NOT verified this pass — explicitly out of scope for T001. Must re-verify fresh in T003 (AI/ML volatile ecosystem, always re-check).
- Next time these packages are needed: re-verify if >7 days have elapsed (stable) or always (AI/ML).
