# Official Doc Note — Backend Stack Versions (CONFIRMED)

**Date**: 2026-05-11
**Task**: P00-S01-T001
**Sources**:
- https://pypi.org/pypi/fastapi/json
- https://pypi.org/pypi/uvicorn/json
- https://pypi.org/pypi/pydantic/json
- https://pypi.org/pypi/pytest/json
- https://pypi.org/pypi/httpx/json
- https://pypi.org/pypi/ruff/json
- https://pypi.org/pypi/mypy/json
- https://github.com/fastapi/fastapi (Context7)
- https://github.com/pydantic/pydantic (Context7)

## Verified versions (2026-05-11)

| Package | Internal assumption (task pack) | PyPI latest stable | Status |
|---|---|---|---|
| `fastapi` | ≥0.115 | **0.136.1** | OK — well above minimum |
| `uvicorn[standard]` | latest stable | **0.46.0** | OK |
| `pydantic` | v2, latest | **2.13.4** | OK |
| `pytest` | ≥8 | **9.0.3** | OK — ≥8 confirmed |
| `httpx` | latest (for TestClient) | **0.28.1** | OK |
| `ruff` | latest stable | **0.15.12** | OK |
| `mypy` | latest stable | **2.0.0** | OK (major version, API stable) |

## Pattern confirmations

### FastAPI lifespan (CONFIRMED correct)

The task pack requires using `lifespan` (not deprecated `on_startup/on_shutdown`). Official docs confirm:
- `@asynccontextmanager` + `async def lifespan(app: FastAPI):` with `yield` is the **current recommended** pattern.
- `on_startup`/`on_shutdown` events are deprecated as of FastAPI 0.93.0+.
- Task pack usage is correct.

### FastAPI middleware for X-Request-ID (CONFIRMED correct)

The task pack pattern — using `@app.middleware("http")` to intercept `Request`, read `X-Request-ID` header, pass it through, and add it to response — matches the official middleware pattern exactly. No discrepancy.

### Pydantic v2 patterns (CONFIRMED correct)

Task pack requires `model_dump()` and `model_config`. Official Pydantic v2 docs confirm:
- `model_dump()` is the v2 canonical replacement for `.dict()` (v1, deprecated).
- `model_config = ConfigDict(...)` is the v2 canonical replacement for inner `class Config`. 
- `.dict()` and inner `class Config` are v1 patterns — confirmed deprecated in v2.
- Task pack is aligned with current Pydantic v2 patterns.

### pytest + httpx + TestClient (CONFIRMED correct)

- `fastapi.testclient.TestClient` (backed by Starlette + httpx under the hood) is still the canonical FastAPI test client pattern.
- pytest 9.0.3 is latest stable (above the ≥8 requirement).
- httpx 0.28.1 is latest stable — no breaking changes relevant to TestClient usage.

### ruff as linter+formatter (CONFIRMED)

- ruff 0.15.12 includes both linter (`ruff check`) and formatter (`ruff format`) in one tool.
- The `[tool.ruff.format]` section in pyproject.toml is the correct configuration path.
- No need for a separate Black or isort — ruff covers both.

## No discrepancies in backend stack

All backend versions and patterns in the task pack are valid. Developer can proceed with these as the floor:
- `fastapi>=0.136.1`
- `uvicorn[standard]>=0.46.0`
- `pydantic>=2.13.4`
- `pytest>=9.0.3`
- `httpx>=0.28.1`
- `ruff>=0.15.12`
- `mypy>=2.0.0`

RESOLVED: 2026-05-11 — informational only; backend stack versions and patterns confirmed correct in T001 (commit 09154e5). No reconciliation needed.

<!-- RESOLVED: 2026-05-11 — informational, backend stack confirmed correct; no change needed. -->
