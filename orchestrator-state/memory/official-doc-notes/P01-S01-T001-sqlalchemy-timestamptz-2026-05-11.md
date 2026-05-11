# Official Doc Note — SQLAlchemy TIMESTAMPTZ mapping for P01-S01-T001

**Task**: P01-S01-T001 — 0001_auth_users_employee_audit.py (Alembic migration + SQLAlchemy models)
**Date**: 2026-05-11
**Researcher**: official-docs-researcher
**Severity**: medium (implementation risk, not a version/import discrepancy)

---

## Finding

The task pack (§10.3 DB Schema) declares all timestamp columns as `TIMESTAMPTZ`:

```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
expires_at TIMESTAMPTZ NOT NULL,
revoked_at TIMESTAMPTZ,
used_at TIMESTAMPTZ,
```

In SQLAlchemy 2.0, the correct way to emit `TIMESTAMP WITH TIME ZONE` (= `TIMESTAMPTZ` in PostgreSQL) is:

```python
sa.TIMESTAMP(timezone=True)
```

**Using `sa.TIMESTAMP` (without `timezone=True`) emits `TIMESTAMP WITHOUT TIME ZONE`** — a silent error that does NOT raise at migration time but stores timestamps without TZ info, breaking UTC consistency.

## Official source

From SQLAlchemy 2.0 Core docs — `sqlalchemy.types.TIMESTAMP`:
> `class sqlalchemy.types.TIMESTAMP(timezone: bool = False)`
> The SQL `TIMESTAMP` type. Keyword Argument: `timezone` — boolean. Indicates that the TIMESTAMP type should enable timezone support, if available on the target database. On a per-dialect basis is similar to `DATETIME`.

Source: https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.TIMESTAMP

For Alembic migrations (manual, `op.create_table`), the same type is used directly:

```python
import sqlalchemy as sa

op.create_table(
    "users",
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
)
```

Alternative using PostgreSQL dialect-specific type (also valid but more verbose):
```python
from sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP
sa.Column("created_at", PG_TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))
```

## Recommendation

In both `backend/alembic/versions/0001_auth_users_employee_audit.py` AND SQLAlchemy model definitions:

- **Migration file**: Use `sa.TIMESTAMP(timezone=True)` for ALL timestamp columns.
- **ORM models** (`user.py`, `auth.py`): Use `Mapped[datetime]` with `mapped_column(sa.TIMESTAMP(timezone=True), ...)` or the standard SQLAlchemy `DateTime(timezone=True)` — which maps to `TIMESTAMPTZ` in PostgreSQL.

```python
# ORM model pattern (canonical for SQLAlchemy 2.0 + PostgreSQL):
from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()")
    )
```

Note: `DateTime(timezone=True)` and `TIMESTAMP(timezone=True)` both emit `TIMESTAMP WITH TIME ZONE` on PostgreSQL — either is acceptable.

## Impact on this slice

Affects columns in: `users` (created_at, updated_at), `refresh_tokens` (expires_at, revoked_at), `password_reset_tokens` (expires_at, used_at), `audit_logs` (created_at).

If the developer uses bare `sa.TIMESTAMP` or `sa.DateTime` (without `timezone=True`), PostgreSQL will silently create `TIMESTAMP WITHOUT TIME ZONE` columns. The migration will run but the schema will not match the source-of-truth DDL contract.

## Internal doc reference

`HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3` specifies `TIMESTAMPTZ` explicitly.

## Status

RESOLVED: 2026-05-11 — verified in worktree-agent-a9c2e2f9442e1f02f. Developer used `sa.TIMESTAMP(timezone=True)` on all 7 TIMESTAMPTZ columns: migration file `backend/alembic/versions/0001_auth_users_employee_audit.py` lines 106, 112, 244, 245, 308, 309, 357; ORM models `backend/app/db/models/user.py` lines 116-122 (created_at, updated_at) and `backend/app/db/models/auth.py` lines 93-99 (refresh_tokens.expires_at, revoked_at), 194-200 (password_reset_tokens.expires_at, used_at), 280-281 (audit_logs.created_at). Schema emits `TIMESTAMP WITH TIME ZONE` correctly, matching TECHNICAL_GUIDE §10.3 contract. No bare `sa.TIMESTAMP` or `sa.DateTime` without `timezone=True` found.
