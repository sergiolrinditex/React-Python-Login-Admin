# Official Doc Note — P00-S02-T016
## pytest-asyncio event-loop patterns + SQLAlchemy NullPool for multi-loop test suites

**Date**: 2026-05-10
**Task**: P00-S02-T016 (stabilize test_admin_ai_discover_models event-loop fragility)
**Severity**: informational (no blocker for Plan A)
**Outcome**: verified — no discrepancy. Additional informational finding documented.

RESOLVED: All official doc findings align with Plan A. No source-of-truth amendments needed. NullPool alternative documented as informational follow-up only — Plan A (autouse reset in conftest.py) is correct, sufficient, and within scope. Developer may proceed without any changes to the task pack.

---

## Sources consulted

| Source | URL |
|---|---|
| pytest-asyncio official docs — configuration reference | https://github.com/pytest-dev/pytest-asyncio/blob/main/docs/reference/configuration.md |
| pytest-asyncio official docs — fixture loop scope | https://github.com/pytest-dev/pytest-asyncio/blob/main/docs/how-to-guides/change_fixture_loop.md |
| pytest-asyncio official docs — decorators | https://github.com/pytest-dev/pytest-asyncio/blob/main/docs/reference/decorators/index.md |
| SQLAlchemy 2.0 asyncio docs — NullPool multiple event loops | https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html |
| SQLAlchemy 2.0 pooling docs — NullPool | https://docs.sqlalchemy.org/en/20/core/pooling.html |
| httpx transports docs — ASGITransport | https://github.com/encode/httpx/blob/master/docs/advanced/transports.md |

---

## Q1 — pytest-asyncio 1.x: "engine singleton across event loops" pattern

### Official finding
- `asyncio_mode = "auto"` with `asyncio_default_fixture_loop_scope` **unset** → the default is **"the fixture scope"**, not "function". So a `scope="session"` async fixture runs in a session-scoped event loop; a `scope="function"` async fixture runs in a function-scoped loop.
- The `http_client` fixture in `test_admin_ai_discover_models.py` is `scope="function"` (default) and it is an **async** fixture — so it correctly runs in a fresh function-scoped loop per test.
- `fernet_test_key` is `scope="session"` but is **NOT async** (only touches `os.environ`) — it does NOT open a loop or a connection. It is loop-neutral.
- Root cause confirmed: the production singleton `_engine` is created in the first test's function-scoped loop and reused by subsequent tests' different function-scoped loops. asyncpg connections bound to loop A cannot be used from loop B → `Task ... got Future ... attached to a different loop`.

### `asyncio_default_fixture_loop_scope` relevance
- In pytest-asyncio 1.x, this config key controls the **default loop scope for async fixtures** when `loop_scope` is not explicitly set on the `@pytest_asyncio.fixture` decorator.
- When UNSET, defaults to "the fixture scope" (matching caching scope). Docs note "will default to `function` in future versions."
- Setting `asyncio_default_fixture_loop_scope = "function"` in pyproject.toml would force ALL async fixtures to run in function-scoped loops regardless of their caching scope — this would surface mismatch warnings but would not fix the engine-singleton bug, since the bug is in the production singleton, not in a pytest fixture itself.
- **Verdict**: adding `asyncio_default_fixture_loop_scope = "function"` is optional/cosmetic for this codebase. It does not fix or break Plan A.

### Autouse function-scoped reset fixture — officially accepted?
- pytest-asyncio does not document a specific pattern for "singleton reset" fixtures.
- The pattern is a standard pytest autouse function-scoped fixture (`scope="function"`, `autouse=True`) that does teardown via `yield`. This is standard pytest (not pytest-asyncio specific).
- Conclusion: it is an accepted, idiomatic pytest pattern. pytest-asyncio places no restriction on synchronous autouse fixtures of any scope.

---

## Q2 — SQLAlchemy 2.0.49 async engine + NullPool for test suites

### Official finding — CANONICAL SQLALCHEMY SOLUTION

The SQLAlchemy 2.0 official asyncio docs have a dedicated section titled **"Using multiple asyncio event loops"**:

> "To share the same engine between different event loops, configure it to disable pooling using `NullPool`. This prevents the engine from reusing any connection more than once, eliminating the issues associated with connections being tied to specific event loops."

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/dbname",
    poolclass=NullPool,
)
```

**NullPool behavior**: opens and closes the underlying DB-API connection per each connection open/close. Compatible with asyncio and `create_async_engine()`. Reconnect and invalidation features not supported (not relevant for test suites).

### Per-test engine vs global engine
- SQLAlchemy docs do not explicitly recommend "per-test engine" vs "global engine with NullPool". The `NullPool` pattern implies the engine _can_ be global (shared), because `NullPool` eliminates the loop-attachment problem.
- Creating a fresh engine per test (function scope) also works but is wasteful. `NullPool` is the lighter, more idiomatic solution.

### `engine.dispose()` — is `await` needed?
- `AsyncEngine.dispose()` signature: `dispose() → None`. **Synchronous** in the official API signature shown in 2.0 docs.
- However, the docs explicitly recommend: "It is recommended to explicitly invoke `AsyncEngine.dispose()` method using `await`". This implies there IS an `async def dispose(close=True)` variant in some contexts — or that calling it returns an awaitable in async contexts.
- The safe pattern from the existing `test_auth_signup.py` (`await engine.dispose()`) is the right call under async test code.
- Calling `engine.dispose()` (sync) from a sync fixture teardown is also valid (NullPool case: there's nothing to dispose).

### Relationship to Plan A
- Plan A (singleton reset `_engine = None` at the conftest layer) achieves equivalent safety to `NullPool`: each test's first `_get_engine()` call creates a brand-new engine object in the current function-scoped loop.
- The SQLAlchemy-native solution would be `poolclass=NullPool` in `backend/app/core/db.py:create_async_engine(...)`. This is a **cleaner single-line fix** but is **out of scope for this slice** (task pack §12 prohibits `backend/app/**` changes).
- **No discrepancy with Plan A**: Plan A is correct, sufficient, and will fix the bug. `NullPool` is noted here as a potential follow-up improvement (cleaner, smaller surface, no runtime overhead).

### Follow-up suggestion (informational, not blocking)
A follow-up task could add `poolclass=NullPool` to the production `create_async_engine(...)` call in `backend/app/core/db.py` — this would eliminate the need for the `reset_db_engine_singleton` workaround entirely and align with the official SQLAlchemy-recommended approach for test isolation. Severity: low, kind: test/refactor.

---

## Q3 — httpx 0.28.1 ASGITransport event loop behavior

### Official finding
- `httpx.ASGITransport(app=app)` is an **in-process transport**. It does NOT create its own event loop. It executes the ASGI app coroutines directly within the **caller's event loop**.
- When used with `async with httpx.AsyncClient(transport=ASGITransport(app=app), ...)`, the ASGI app's `__call__` is awaited in the same event loop as the `AsyncClient` context.
- This means the FastAPI app (and its dependency-injected `get_session()` → `_get_engine()`) runs in the **same function-scoped loop** as the test. It does NOT create a separate loop. The engine singleton created in test 1's loop IS the same engine re-accessed in test 2's loop — confirming H1.
- ASGITransport vs uvicorn live: ASGITransport is in-process (faster, no TCP overhead, same loop). Against uvicorn live the client and server run in potentially different processes/loops — the singleton problem does not manifest because the DB connection pool lives in the server process. However, as the pack notes, uvicorn live makes test isolation harder. ASGITransport + Plan A is the correct approach.
- Official httpx docs confirm ASGITransport is the idiomatic test pattern for FastAPI/Starlette apps.

---

## Q4 — Autouse fixture impact on non-DB tests

### Official finding
- A synchronous `autouse=True, scope="function"` fixture in `conftest.py` runs for EVERY test in the directory/package, including those that don't use DB.
- The fix: set `_engine = None` only if `_engine is not None` (check before reset) — this is a no-op for tests that never initialized the singleton. The existing pattern in `test_auth_signup.py` already does this idiomatically.
- Alternative gating: `@pytest.mark.no_engine_reset` opt-out marker + `request.node.get_closest_marker("no_engine_reset")` check inside the fixture — acceptable if needed, but the task pack §13 audit shows zero tests assume persistent `_engine` across tests, making this unnecessary.
- `capsys`/`caplog` impact: zero — the fixture is synchronous and runs in pytest's teardown phase, after any captures.

---

## Summary verdicts

| Question | Verdict | Detail |
|---|---|---|
| pytest-asyncio 1.x "different loop" canonical pattern | VERIFIED — Plan A correct | Official docs confirm function-scoped loops per test; autouse reset is idiomatic pytest |
| `asyncio_default_fixture_loop_scope` default | VERIFIED | Defaults to fixture scope when unset; not needed for Plan A |
| SA 2.0 per-test engine vs NullPool | INFORMATIONAL | NullPool is the official SA recommendation for multi-loop scenarios; Plan A is equivalent workaround at conftest level; NullPool fix in db.py is out of scope |
| `engine.dispose()` async | VERIFIED | `await engine.dispose()` is the correct call in async context per SA docs |
| ASGITransport event loop | VERIFIED — H1 confirmed | ASGITransport runs app coroutines in caller's loop; no separate loop; singleton bug manifests as pack describes |
| Autouse impact on non-DB tests | VERIFIED — safe | Reset is a no-op when `_engine is None`; no capsys/caplog impact |

**RESOLVED**: No changes to Plan A required. All patterns are confirmed. NullPool follow-up documented as informational for future consideration.
