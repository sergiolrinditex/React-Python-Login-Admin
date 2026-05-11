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
