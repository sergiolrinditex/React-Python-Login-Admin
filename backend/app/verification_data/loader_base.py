"""
Hilo People — Shared primitives for verification data loaders.

Slice:  P02-S03-T004 — Rotate ENCRYPTION_KEY in dev .env + seed active AI provider
Phase:  P02 Core Features
Purpose: Shared primitives extracted to avoid circular imports between loader.py
         and loader_ai_tables.py. Both import LoadResult, _table_exists and _info
         from this module.

         Exported symbols:
           - LoadResult (dataclass) — summary of a load operation
           - _table_exists(engine, table) — runtime table check
           - _info(event, **kw) — verbose-gated INFO logger helper

Key deps:
  - sqlalchemy==2.0.49 (Engine, inspect)
  - structlog==25.5.0

Source refs:
  - P02-S03-T004 (split for file-size compliance and circular import avoidance)
  - 01-non-negotiables.md §File size (one responsibility per file)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import Engine, inspect

log = structlog.get_logger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def _info(event: str, **kw: Any) -> None:
    """Emit INFO only when ENABLE_VERBOSE_LOGGING=true (per non-negotiables).

    Args:
        event: Log event name.
        **kw:  Additional key-value pairs.
    """
    if _VERBOSE:
        log.info(event, **kw)


@dataclass
class LoadResult:
    """Summary of a single group load operation.

    Attributes:
        group:    Name of the group (e.g. 'auth', 'rag_chat').
        status:   'ok', 'deferred', 'dry_run', or 'error'.
        inserted: Rows newly inserted (0 if deferred/dry-run).
        updated:  Rows updated on conflict (0 if deferred/dry-run).
        skipped:  Rows unchanged because the stored data was identical.
        reason:   Human-readable reason for deferred/error status.
    """

    group: str
    status: str
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    reason: str = ""


def _table_exists(engine: Engine, table_name: str) -> bool:
    """Return True if table_name exists in the public schema at runtime.

    Uses sqlalchemy.inspect() which queries information_schema — no cache.

    Args:
        engine:     Active SQLAlchemy Engine.
        table_name: Unqualified table name (e.g. 'users').

    Returns:
        True if the table exists in the connected database.
    """
    insp = inspect(engine)
    return insp.has_table(table_name)
