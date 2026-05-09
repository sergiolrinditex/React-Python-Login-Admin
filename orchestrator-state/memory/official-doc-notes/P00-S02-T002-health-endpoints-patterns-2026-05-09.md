# Official Docs Verification — P00-S02-T002 Health live/ready endpoints

**Date**: 2026-05-09
**Task**: P00-S02-T002 — Health live ready endpoints
**Outcome**: VERIFIED — no discrepancies found

---

## Pattern 1: FastAPI health/readiness — router include

**VERIFIED_OFFICIAL** — `app.include_router(router)` is the canonical pattern for larger
applications. `APIRouter` is created in a separate module; `app.include_router()` is called in
`main.py`. No prefix needed for unversioned ops endpoints. Lifespan (`@asynccontextmanager`) is
the modern replacement for `@app.on_event`; NOT required for this slice (no startup init needed
for ops router). `@app.middleware("http")` is the FastAPI-idiomatic form for request_id
middleware (equivalent to `add_middleware(BaseHTTPMiddleware, ...)`; both valid).

Sources: FastAPI tutorial/bigger-applications.md, fastapi/fastapi repo docs.

---

## Pattern 2: SQLAlchemy 2.0 async engine probe — SELECT 1

**VERIFIED_OFFICIAL** — Canonical pattern:
```python
async with engine.connect() as conn:
    await conn.execute(text("SELECT 1"))
```
`engine.connect()` is correct for read-only probes (not `engine.begin()` which is for
transactional writes). `text("SELECT 1")` is the standard raw SQL form. Both are confirmed
in SQLAlchemy 2.0 asyncio extension docs.

Sources: docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

---

## Pattern 3: Exception to catch for DB-down in /ready

**VERIFIED_OFFICIAL** — SQLAlchemy wraps all asyncpg DBAPI errors into its own hierarchy:
- `sqlalchemy.exc.OperationalError` (server down, connection refused — most common)
- `sqlalchemy.exc.InterfaceError` (protocol/driver-level failures)
Both are subclasses of `sqlalchemy.exc.SQLAlchemyError`.

**Correct catch**: `except sqlalchemy.exc.SQLAlchemyError as e:` — covers all cases without
catching generic `Exception` (non-negotiable §Error handling). asyncpg raw exceptions
(`asyncpg.exceptions.PostgresConnectionError` etc.) are NOT directly exposed — SQLAlchemy
intercepts and wraps them. Task pack assertion confirmed.

Sources: docs.sqlalchemy.org/en/20/errors.html (DBAPI Errors section)

---

## Pattern 4: structlog 25.5.0 contextvars for request_id middleware

**VERIFIED_OFFICIAL** — `structlog.contextvars` module confirmed present in 25.5.0 with
full API: `bind_contextvars`, `clear_contextvars`, `unbind_contextvars`, `get_contextvars`,
`merge_contextvars`, `bound_contextvars`, `reset_contextvars`.

Canonical per-request pattern:
```python
structlog.contextvars.clear_contextvars()
structlog.contextvars.bind_contextvars(request_id=request_id, ...)
# ... handle request ...
structlog.contextvars.clear_contextvars()  # or reset_contextvars()
```
No official "FastAPI middleware" recommended by structlog — the clear/bind/clear pattern
inside a `@app.middleware("http")` function is the documented approach (structlog docs show
Flask example; same pattern applies to FastAPI/ASGI). `merge_contextvars` processor must be
in the structlog configuration chain (already wired in T003 `app.core.logging`).

Sources: /hynek/structlog Context7 + github.com/hynek/structlog/blob/main/docs/contextvars.md

---

## Pattern 5: httpx 0.28 AsyncClient + ASGITransport for pytest-asyncio

**VERIFIED_OFFICIAL** — `httpx.ASGITransport` is present and NOT deprecated in httpx 0.28.1.
The `app=` parameter on `AsyncClient` WAS deprecated in httpx 0.27 and removed in 0.28.
The current canonical pattern is:
```python
from httpx import AsyncClient, ASGITransport
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.get("/health")
```
Task pack line 281 already specifies this correctly.

Sources: httpx 0.28.1 installed package — `httpx.ASGITransport` confirmed in `__all__`.
FastAPI advanced/async-tests.md also confirms AsyncClient usage.

---

## Pattern 6: pytest-asyncio 1.3.0 modes

**VERIFIED_OFFICIAL** — pytest-asyncio 1.3.0 supports `asyncio_mode = "auto"` (and `"strict"`;
default is `"strict"`). With `asyncio_mode = "auto"` set in `pyproject.toml` (CONFIRMED — line
122 of backend/pyproject.toml), `async def test_*()` functions are automatically discovered
without any `@pytest.mark.asyncio` decorator. No decorator is needed.

FastAPI docs reference `@pytest.mark.anyio` (from the `anyio` package, which IS installed at
4.13.0 in the project venv) — this is for AnyIO-compatible async tests. It is NOT required for
this stack; `pytest-asyncio` in auto mode is sufficient. Both approaches are valid, but the
task pack's approach (asyncio_mode=auto, no marker) is idiomatic.

Sources: /pytest-dev/pytest-asyncio Context7 (configuration.md, concepts.md)
Confirmed via: backend/pyproject.toml line 122.

---

## Additional finding: FastAPI 0.136.1 vs system Python mismatch

The system `python3` on this machine has FastAPI 0.135.2. The project venv
(`backend/.venv-t003`) has FastAPI 0.136.1 (matches pyproject.toml pin). Developer must use
the project venv for all commands. No functional difference between 0.135.2 and 0.136.1 for
the patterns in this slice. NOT a discrepancy in the code contract.

---

## Summary table

| # | Pattern | Status | Key finding |
|---|---|---|---|
| 1 | FastAPI router include + ops pattern | VERIFIED | `app.include_router(router)` canonical; `@app.middleware("http")` for request_id |
| 2 | SQLAlchemy async SELECT 1 probe | VERIFIED | `engine.connect()` + `text("SELECT 1")` |
| 3 | asyncpg / SQLAlchemy exception to catch | VERIFIED | `sqlalchemy.exc.SQLAlchemyError` covers all DB-down cases |
| 4 | structlog 25.5.0 contextvars API | VERIFIED | Module unchanged; `bind_contextvars`/`clear_contextvars` are the correct functions |
| 5 | httpx 0.28 ASGITransport | VERIFIED | `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` |
| 6 | pytest-asyncio 1.3.0 auto mode | VERIFIED | `asyncio_mode="auto"` in pyproject.toml confirmed; no decorator needed |

**DISCREPANCIES: none**

RESOLVED: All 6 patterns verified against official docs and installed package inspection. No source-of-truth amendment required. Developer may implement as specified in task pack without modification.

RESOLVED (developer P00-S02-T002 2026-05-09): Implementation follows all 6 verified patterns exactly.
- Pattern 1: app.include_router(ops_router) + @app.middleware("http") — used in app/main.py.
- Pattern 2: engine.connect() + text("SELECT 1") — used in app/api/router._probe_db().
- Pattern 3: except SQLAlchemyError — only explicit exception caught; bare Exception as last-resort fallback for asyncpg.
- Pattern 4: structlog.contextvars.clear_contextvars() + bind_contextvars() + clear_contextvars() in @app.middleware.
- Pattern 5: httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") — used in all tests.
- Pattern 6: asyncio_mode=auto confirmed in pyproject.toml; no @pytest.mark.asyncio decorators needed.
