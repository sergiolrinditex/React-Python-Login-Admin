"""
Async-safe table existence probe for the seed loader.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Uses information_schema.tables query via run_sync() so it works with
SQLAlchemy 2.0 async engines. No schema metadata inspection needed —
a direct SQL query is simpler and avoids reflect() overhead.

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - asyncpg 0.31.0
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger

_logger = get_logger(__name__)


async def table_exists(engine: AsyncEngine, table_name: str, schema: str = "public") -> bool:
    """Return True if the given table exists in the schema.

    Uses information_schema.tables to avoid locking or schema reflect.
    Works with SQLAlchemy 2.0 async engine (no run_sync needed for text queries).

    Purpose: allow loaders to skip writes gracefully when P01-S01-T001 has
             not yet created the target table.
    Params:
      engine     — async engine instance.
      table_name — exact table name (no quotes).
      schema     — Postgres schema name (default 'public').
    Returns: True if the table exists, False otherwise.
    Errors: SQLAlchemyError propagated (let the caller decide how to handle).
    """
    _logger.debug(
        "BEFORE table_exists: probing",
        table=table_name,
        schema=schema,
    )
    query = text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = :schema AND table_name = :table LIMIT 1"
    )
    async with engine.connect() as conn:
        result = await conn.execute(query, {"schema": schema, "table": table_name})
        exists = result.scalar() == 1

    _logger.debug(
        "AFTER table_exists: probe complete",
        table=table_name,
        schema=schema,
        exists=exists,
    )
    return exists
