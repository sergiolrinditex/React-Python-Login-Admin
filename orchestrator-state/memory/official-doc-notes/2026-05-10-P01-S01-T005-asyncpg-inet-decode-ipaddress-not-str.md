# Discrepancy: asyncpg INET decode returns ipaddress objects, not str

**Date**: 2026-05-10
**Task**: P01-S01-T005
**Severity**: medium (affects test assertions; does not break INSERT/production runtime)
**Status**: RESOLVED
RESOLVED: In test_audit_logs_compliance_cols.py, all assertions on the `ip` column use `str(row.ip)` (e.g., `assert str(row.ip) == '192.168.1.1'`) to handle asyncpg returning `ipaddress.IPv4Address` objects for INET. ORM annotation kept as `Mapped[str | None]` per task-pack decision (runtime-safe; asyncpg accepts str on INSERT via inet_encode). No migration change needed. native_inet_types=False NOT added to db.py (outside write set). P01-S01-T005 developer 2026-05-10.

---

## Pattern assumed in task pack

Task pack §"Open questions resolved" (line 173):
> "asyncpg returns INET as `str` by default; converting to `ipaddress.IPv4Address` adds dependency surface for zero gain in T005. P02-S02-T001 may revisit when middleware lands."

Task pack §"Front → Back → DB contract" (line 132):
> "Keep type-stub: ip as `Mapped[str | None]` is fine (asyncpg returns INET as `str` by default)"

**Assumed behavior**: reading an INET column returns a Python `str` like `'192.168.1.1'`.

---

## Official behavior (source-code verified)

**Source**: installed asyncpg 0.31.0 at
`backend/.venv/lib/python3.12/site-packages/asyncpg/pgproto/codecs/network.pyx`

The `inet_decode` function (lines 138-139) calls `net_decode(settings, buf, False)`.
`net_decode` (lines 63-103) returns:
- `ipaddress.ip_address(addr)` — an `IPv4Address` or `IPv6Address` — for plain host addresses (prefix == max prefix length, i.e. /32 for IPv4, /128 for IPv6).
- `ipaddress.ip_interface(...)` — for CIDR-notation values like `'192.168.1.0/24'`.

**Source**: SQLAlchemy 2.0.49 asyncpg dialect at
`backend/.venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py`
lines 1237-1274:

```python
async def _disable_asyncpg_inet_codecs(self, conn):
    await asyncpg_connection.set_type_codec(
        "inet",
        encoder=lambda s: s,
        decoder=lambda s: s,    # <-- returns str when disabled
        schema="pg_catalog",
        format="text",
    )

# on_connect:
if self._native_inet_types is False:          # only if explicitly False
    conn.await_(self._disable_asyncpg_inet_codecs(conn))
```

`native_inet_types` defaults to `None` (not `False`) per base.py line 3328.
The project's `create_async_engine(dsn, pool_pre_ping=True, echo=...)` does NOT pass `native_inet_types=False`.
Therefore: **asyncpg's native INET codec IS active**. Reads return `ipaddress.IPv4Address`, not `str`.

**INSERT/bind (encoding)**: `inet_encode` calls `ipaddress.ip_address(obj)` which accepts a plain `str` like `'192.168.1.1'` correctly (documented Python stdlib behavior). So writing a string is fine.

**SELECT/result (decoding)**: returns `IPv4Address`, not `str`.

---

## Impact

### ORM `Mapped[str | None]` annotation

SQLAlchemy does NOT enforce type annotations at runtime. The annotation `Mapped[str | None]` is legal and will not cause any runtime error. However, mypy/pyright may flag it as incorrect if they resolve the asyncpg dialect's type specialization. For T005 scope this is a documentation/type-stub concern only, not a functional bug.

### Integration test assertions (CRITICAL for T005)

Test 3 in task pack ("test_insert_with_compliance_cols_persists_non_null") plans:

```python
assert row.ip == '192.168.1.1'  # WILL FAIL
```

`row.ip` will be `ipaddress.IPv4Address('192.168.1.1')`, so `row.ip == '192.168.1.1'` evaluates to `False`. The assertion will fail.

Correct assertion patterns:
```python
assert str(row.ip) == '192.168.1.1'       # safe — IPv4Address.__str__() returns '192.168.1.1'
# or
import ipaddress
assert row.ip == ipaddress.IPv4Address('192.168.1.1')
```

For Test 3's raw SQL INSERT path (via `execute(text(...), {...})` with `'192.168.1.1'` as a string parameter), the bind is fine — asyncpg accepts `str` for INET parameters and coerces it internally. Only the SELECT-and-compare step needs adjustment.

---

## Action for developer (concise)

**One change only** — in `test_audit_logs_compliance_cols.py` Test 3:

When asserting the `ip` column value after SELECT, compare with `str(row.ip)` or use `ipaddress.IPv4Address(...)`, not a raw string equality `== '192.168.1.1'`. All four INSERT patterns (raw SQL via `text()`, `session.add(AuditLog(..., ip='192.168.1.1', ...))`) are correct — asyncpg's `inet_encode` accepts plain strings. Only the assertion side needs the `str()` conversion.

No change needed to:
- Migration 0002 (INET type declaration is correct and unchanged)
- ORM `Mapped[str | None]` annotation (works at runtime; may keep for simplicity in T005)
- Any service or repository code (not in T005 scope)

Optional (no scope change required): add `native_inet_types=False` to `create_async_engine(...)` in `backend/app/core/db.py` to force string returns everywhere — but this is explicitly out of T005 write-set scope and changes behavior for existing INET columns (none exist today, so it is safe if the developer chooses to do it, but it IS a write to `db.py` which is outside the declared write set).

---

## References

- asyncpg `network.pyx` inet_decode: `backend/.venv/lib/python3.12/site-packages/asyncpg/pgproto/codecs/network.pyx` lines 138-139
- SQLAlchemy asyncpg dialect `_disable_asyncpg_inet_codecs`: `backend/.venv/lib/python3.12/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py` lines 1237-1274
- asyncpg docs: https://magicstack.github.io/asyncpg/current/
- SQLAlchemy INET type: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#sqlalchemy.dialects.postgresql.INET
