# P00-S02-T002 sqlalchemy-sync-ping — Official Docs Verification
- DATE: 2026-05-11
- TASK_ID: P00-S02-T002

---

## SQLAlchemy 2.0 sync engine ping pattern — VERIFIED OK

- OFFICIAL: The idiomatic SQLAlchemy 2.0 pattern for a sync health check is:
  ```python
  from sqlalchemy import create_engine, text
  from sqlalchemy import exc as sa_exc

  engine = create_engine(url, pool_pre_ping=True)

  with engine.connect() as conn:
      conn.execute(text("SELECT 1"))
  ```
  The `with` block automatically calls `Connection.close()` on exit, returning the connection to the pool.
  `pool_pre_ping=True` adds a lightweight pre-checkout ping — this is the OFFICIAL recommended way to handle stale connections (documented in SQLAlchemy 2.0 pooling guide).
  No dedicated health-check helper exists — hand-rolling with `text("SELECT 1")` is the documented pattern.

- OFFICIAL exception handling:
  - `sqlalchemy.exc.DBAPIError` — wraps ALL DBAPI-level exceptions (connection failure, timeout, etc.).
  - `sqlalchemy.exc.OperationalError` — subclass of `DBAPIError`; the most common exception for "database not reachable / dropped connection." Raised by most drivers including psycopg3 when postgres is unreachable.
  - Hierarchy: `SQLAlchemyError → DBAPIError → OperationalError`.
  - For health checks, catching `sqlalchemy.exc.OperationalError` is the most precise. Catching `sqlalchemy.exc.DBAPIError` is broader and also correct.

- INTERNAL (task pack §Contracts item 2, §Impact):
  - Recommends `engine.connect() as conn: conn.execute(text("SELECT 1"))` — matches official pattern exactly.
  - Says catch `OperationalError / DBAPIError` — matches official hierarchy.
  - Recommends `pool_pre_ping=True` — matches official docs.
- DISCREPANCY: none — task pack pattern is idiomatic and matches SQLAlchemy 2.0 official docs.
- SOURCE:
  - https://docs.sqlalchemy.org/en/20/core/connections.html (engine.connect + text())
  - https://docs.sqlalchemy.org/en/20/core/pooling.html (pool_pre_ping official docs)
  - https://docs.sqlalchemy.org/en/20/errors.html (DBAPIError / OperationalError hierarchy)
- RESOLVED: 2026-05-11 — verified OK. No action needed beyond confirming both `OperationalError` and `DBAPIError` are correct catches.

---

## psycopg3 + SQLAlchemy 2.0 dialect — VERIFIED OK

- OFFICIAL: Dialect prefix for psycopg3 (psycopg) with SQLAlchemy 2.0: `postgresql+psycopg://`. Supports sync `create_engine("postgresql+psycopg://...")` and async `create_async_engine("postgresql+psycopg://...")`.
- INTERNAL (task pack §Stack): mentions `postgresql+psycopg://` for psycopg3 option — correct.
- DISCREPANCY: none.
- RESOLVED: 2026-05-11 — verified OK.
