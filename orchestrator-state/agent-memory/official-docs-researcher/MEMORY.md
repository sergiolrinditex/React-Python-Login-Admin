# Official Docs Researcher — Agent Memory

> This file persists findings across sessions. Check dates and freshness windows before re-fetching.
> AI/ML-volatile ecosystem entries: always re-verify. Stable ecosystem: 7-day cache. Claude Code/Anthropic: 14-day cache.

---

## 2026-05-11 — P00-S01-T001 Deep Pass (Bootstrap slice)

### FastAPI

- **Verified**: 2026-05-11
- **Latest stable**: 0.136.1
- **Cache valid until**: 2026-05-18 (stable framework)
- **Key findings**:
  - `lifespan` via `@asynccontextmanager` is the canonical pattern (replaces deprecated `on_startup`/`on_shutdown` since 0.93.0).
  - `@app.middleware("http")` for X-Request-ID middleware is current canonical pattern.
  - Health endpoint: async `@app.get("/health")` with no auth is standard.
  - Minimum requirement in task pack was "≥0.115" — current latest is 0.136.1. No issue.
- **Source**: PyPI + Context7 /fastapi/fastapi

### uvicorn

- **Verified**: 2026-05-11
- **Latest stable**: 0.46.0 (`uvicorn[standard]`)
- **Cache valid until**: 2026-05-18
- **Key findings**: Flags `--host`, `--port`, `--reload` all unchanged. No breaking changes.
- **Source**: PyPI

### Pydantic

- **Verified**: 2026-05-11
- **Latest stable**: v2.13.4
- **Cache valid until**: 2026-05-18
- **Key findings**:
  - `model_dump()` is current v2 canonical (`.dict()` is deprecated).
  - `model_config = ConfigDict(...)` is current v2 canonical (inner `class Config` is v1, deprecated).
  - `model_dump_json()` replaces `.json()`.
- **Source**: PyPI + Context7 /pydantic/pydantic

### pytest

- **Verified**: 2026-05-11
- **Latest stable**: 9.0.3
- **Cache valid until**: 2026-05-18
- **Key findings**: pytest ≥8 requirement satisfied. `fastapi.testclient.TestClient` still the canonical FastAPI test client.
- **Source**: PyPI + Context7 /pytest-dev/pytest

### httpx

- **Verified**: 2026-05-11
- **Latest stable**: 0.28.1
- **Cache valid until**: 2026-05-18
- **Key findings**: Used under the hood by FastAPI TestClient. No API breaking changes for test usage.
- **Source**: PyPI

### ruff

- **Verified**: 2026-05-11
- **Latest stable**: 0.15.12
- **Cache valid until**: 2026-05-18
- **Key findings**: Includes both linter (`ruff check`) and formatter (`ruff format`). Config via `[tool.ruff]` + `[tool.ruff.lint]` + `[tool.ruff.format]` in pyproject.toml.
- **Source**: PyPI + Context7 /astral-sh/ruff

### mypy

- **Verified**: 2026-05-11
- **Latest stable**: 2.0.0
- **Cache valid until**: 2026-05-18
- **Key findings**: Major version bump to 2.0; stable API. Config via `[tool.mypy]` in pyproject.toml.
- **Source**: PyPI

---

### React

- **Verified**: 2026-05-11
- **Latest stable (npm `latest`)**: **19.2.6**
- **Cache valid until**: 2026-05-18
- **DISCREPANCY**: Task pack says "React 18.x" and warns against React 19. React 19 is now stable and is the `latest` tag on npm. React 18.x is still maintained but is NOT the current stable for new projects.
- **Note file**: `orchestrator-state/memory/official-doc-notes/P00-S01-T001-react-typescript-versions.md`
- **Source**: npm registry

### TypeScript

- **Verified**: 2026-05-11
- **Latest stable**: **6.0.3**
- **Cache valid until**: 2026-05-18
- **DISCREPANCY**: Task pack says "TypeScript 5.x". TS 6.0 is the current stable. Greenfield projects should use TS 6.
- **Vite 8 templates**: Use `"typescript": "~6.0.2"` confirming TS 6 is correct for Vite 8 stack.
- **Note file**: `orchestrator-state/memory/official-doc-notes/P00-S01-T001-react-typescript-versions.md`
- **Source**: npm registry + Context7 /vitejs/vite

### Vite

- **Verified**: 2026-05-11
- **Latest stable (npm `latest`)**: **8.0.11**
- **Cache valid until**: 2026-05-18
- **DISCREPANCY**: Task pack says "Vite 5.x". Current stable is Vite 8.0.11. Vite 5 is two major versions behind.
- **Critical**: Vitest 4.x requires Vite ≥6.0. @vitejs/plugin-react 6.x requires Vite ^8.0.0.
- **Note file**: `orchestrator-state/memory/official-doc-notes/P00-S01-T001-vite-vitest-versions.md`
- **Source**: npm registry + Context7 /vitejs/vite

### Vitest

- **Verified**: 2026-05-11
- **Latest stable**: **4.1.5**
- **Cache valid until**: 2026-05-18
- **DISCREPANCY**: Task pack says "Vitest ~2.x". Latest is 4.1.5. Vitest 4.0 requires Vite ≥6.0; Vitest 4.1 adds Vite 8 support.
- **Note file**: `orchestrator-state/memory/official-doc-notes/P00-S01-T001-vite-vitest-versions.md`
- **Source**: npm registry + Context7 /vitest-dev/vitest

### @vitejs/plugin-react

- **Verified**: 2026-05-11
- **Latest stable**: **6.0.1**
- **peerDependencies**: `vite: "^8.0.0"` (requires Vite 8)
- **Note**: v5 remains compatible with Vite 8 for staged upgrades per Vite 8 announcement.
- **Cache valid until**: 2026-05-18
- **DISCREPANCY**: Task pack implies compatibility with Vite 5; actual latest requires Vite ^8.
- **Note file**: `orchestrator-state/memory/official-doc-notes/P00-S01-T001-vite-vitest-versions.md`
- **Source**: npm registry + Context7 /vitejs/vite

### @testing-library/react

- **Verified**: 2026-05-11
- **Latest stable**: **16.3.2**
- **peerDependencies**: `react: "^18.0.0 || ^19.0.0"` — compatible with both React 18 and 19.
- **Cache valid until**: 2026-05-18
- **No discrepancy** on this package. Works with either React version decision.
- **Source**: npm registry

---

## Summary of active discrepancies (unresolved)

| Note file | Topic | Severity |
|---|---|---|
| P00-S01-T001-vite-vitest-versions.md | Vite 5 outdated (8.0.11 current), Vitest 2.x outdated (4.1.5 current), plugin-react v6 requires Vite ^8 | HIGH — hard compatibility break if mismatched |
| P00-S01-T001-react-typescript-versions.md | React 18 outdated (19.2.6 current stable), TypeScript 5 outdated (6.0.3 current) | MEDIUM — React 18 still works but TS 6 is greenfield-correct |

---

## 2026-05-11 — P00-S01-T002 Deep Pass (Frontend dependency pack)

### react-router-dom
- **Verified**: 2026-05-11
- **Latest stable**: **7.15.0**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: `react >=18` (React 19.2.6 covered)
- **Key findings**: `<BrowserRouter>` is fully supported in v7 "Declarative mode" — not deprecated. v7 re-exports from `react-router`; import from `react-router-dom` still correct.
- **Source**: npm registry + Context7 /remix-run/react-router

### @tanstack/react-query
- **Verified**: 2026-05-11
- **Latest stable**: **5.100.9**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: `react: ^18 || ^19` — React 19 explicitly supported
- **Key findings**: `QueryClient` + `QueryClientProvider` API unchanged. `staleTime`/`retry` in `defaultOptions.queries` works as expected.
- **Source**: npm registry

### react-hook-form
- **Verified**: 2026-05-11
- **Latest stable**: **7.75.0**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: `react: ^16.8.0 || ^17 || ^18 || ^19` — React 19 explicit
- **Source**: npm registry

### zod
- **Verified**: 2026-05-11
- **Latest stable (dist-tag `latest`)**: **4.4.3** — ZOD 4 IS NOW STABLE
- **Cache valid until**: 2026-05-18
- **peerDependencies**: None
- **Key findings**: `npm install zod` installs Zod 4.4.3. Import: `import { z } from 'zod'` (Zod 4). Zod 3 available via `import { z } from 'zod/v3'` shim. Greenfield projects must use Zod 4.
- **Source**: npm registry

### @hookform/resolvers
- **Verified**: 2026-05-11
- **Latest stable**: **5.2.2**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: `react-hook-form: ^7.55.0` — RHF 7.75.0 satisfies
- **Key findings**: `zodResolver` supports both Zod 3 AND Zod 4. No API change needed. Import `zod` normally.
- **Source**: npm registry + Context7 /react-hook-form/resolvers

### i18next
- **Verified**: 2026-05-11
- **Latest stable**: **26.0.10**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: `typescript: ^5 || ^6` (optional) — TS 6.0.3 satisfies
- **Source**: npm registry

### react-i18next
- **Verified**: 2026-05-11
- **Latest stable**: **17.0.7**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: `i18next: >= 26.0.10`, `react: >= 16.8.0`, `typescript: ^5 || ^6` (optional)
- **Key findings**: All peers satisfied. i18next 26.0.10 exactly meets `>= 26.0.10`.
- **Source**: npm registry

### i18next-browser-languagedetector
- **Verified**: 2026-05-11
- **Latest stable**: **8.2.1**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: None declared. Plugin-style attachment to i18next instance.
- **Source**: npm registry

### @testing-library/jest-dom
- **Verified**: 2026-05-11
- **Latest stable**: **6.9.1**
- **Cache valid until**: 2026-05-18
- **peerDependencies**: None
- **Key findings**: Vitest import path `@testing-library/jest-dom/vitest` confirmed available. Recommend adding to `setupFiles` in `vitest.config.ts`.
- **Source**: npm registry

### jsdom
- **Verified**: 2026-05-11
- **Latest stable**: **29.1.1** (already installed from T001)
- **Cache valid until**: 2026-05-18
- **peerDependencies**: `canvas: ^3.0.0` (optional)
- **Node engine**: `^20.19.0 || ^22.13.0 || >=24.0.0` — Node 25.9.0 satisfies `>=24.0.0`
- **Source**: npm registry

### T002 note file
- `orchestrator-state/memory/official-doc-notes/P00-S01-T002-frontend-libs-confirmed.md`
- Status: RESOLVED (informational, no source-of-truth change needed)
