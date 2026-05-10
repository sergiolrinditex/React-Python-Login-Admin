"""
Async SQLAlchemy engine and session factory.

Slice: P00-S01-T003 — Backend dependency pack
Phase: P00 — Scaffold + Design System
Updated: P00-S02-T012 — CWE-532 defense-in-depth: SQLAlchemy echo=False permanent

Provides:
  - get_engine() — lazy public accessor that returns the singleton AsyncEngine.
  - get_session() — FastAPI dependency that yields an AsyncSession per request.

IMPORTANT: This module does NOT connect to the database at import time and
  does NOT build the engine at import time either. Both engine and session
  factory are created on first call to their accessors. The connection pool
  itself opens on the first real query.
  No migrations are applied here — that is P01-S01-T001 (alembic upgrade head).

DB contract (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 + §10.5):
  - Driver: asyncpg
  - ORM: SQLAlchemy 2.x declarative async (no legacy Base.metadata.create_all).
  - Pool: AsyncAdaptedQueuePool (default for asyncpg).
  - Transactions: unit-of-work per request via get_session().
  - SA engine.echo is permanently False (P00-S02-T012 / FU-20260510044529 / CWE-532
    defense-in-depth). When echo=True, SQLAlchemy writes every bind-parameter tuple to
    the sqlalchemy.engine stdlib logger — including the Fernet ciphertext stored in
    ai_provider_credentials.encrypted_secret (the "fourth layer" of the CWE-532 chain,
    following T002/T004/T009). Project SQL observability uses structlog with redaction
    per §10.5; SA echo is a third-party channel that bypasses the redaction processor.
    Re-enabling silently leaks Fernet ciphertext. See test_db_engine_no_secret_leak.py.

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - asyncpg 0.31.0
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

_logger = get_logger(__name__)

# Lazy globals — initialized on first call to _get_engine().
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    """Return (or create) the singleton AsyncEngine.

    Purpose: deferred init so tests can override DATABASE_URL before first use.
    Returns: AsyncEngine configured from settings.database_url.
    Errors: sqlalchemy.exc.OperationalError if the DSN is invalid (on first
            actual connect, not here).
    """
    global _engine  # noqa: PLW0603
    if _engine is None:
        _logger.debug("BEFORE _get_engine: creating async engine")
        settings = get_settings()
        dsn = settings.database_url.get_secret_value()
        _engine = create_async_engine(
            dsn,
            pool_pre_ping=True,
            # CWE-532 (FU-20260510044529 / P00-S02-T012): SQLAlchemy echo=True writes
            # bind parameters (including Fernet ciphertext for
            # ai_provider_credentials.encrypted_secret) to the sqlalchemy.engine stdlib
            # logger. Project structured logs already cover SQL behavior with redaction
            # per HILO_PEOPLE_TECHNICAL_GUIDE §10.5; SA echo is third-party noise that
            # bypasses the redaction processor. Keep echo=False permanently.
            # Re-enabling silently leaks credential ciphertext (regression guard:
            # backend/tests/integration/test_db_engine_no_secret_leak.py).
            echo=False,
        )
        _logger.debug("AFTER _get_engine: engine created (host redacted)")
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (or create) the singleton session factory.

    Purpose: single factory so all session creation is uniform.
    Returns: async_sessionmaker bound to the shared engine.
    Errors: none at factory creation time.
    """
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _logger.debug("BEFORE _get_session_factory: creating session factory")
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
            class_=AsyncSession,
        )
        _logger.debug("AFTER _get_session_factory: session factory ready")
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, Any]:
    """FastAPI dependency: yield an AsyncSession per request.

    Purpose: provide a transactional unit-of-work session to route handlers
    and repositories. Rolls back on any exception; always closes.

    Usage (in router):
        async def handler(session: AsyncSession = Depends(get_session)): ...

    Returns: AsyncSession (async generator — used as FastAPI Depends).
    Errors: sqlalchemy.exc.* propagated after rollback + close.
    """
    _logger.debug("BEFORE get_session: opening db session")
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            _logger.debug("AFTER get_session: session yielded, committing")
            await session.commit()
        except Exception:
            _logger.warning("ERROR get_session: rolling back transaction")
            await session.rollback()
            raise
        finally:
            _logger.debug("AFTER get_session: session closed")


def get_engine() -> AsyncEngine:
    """Public lazy accessor for the singleton AsyncEngine.

    Purpose: Alembic async env (P01-S01-T001) and any future code that needs
    a direct handle to the engine call this instead of touching the private
    _get_engine. The engine is built on first call and memoized — no
    import-time side effect.

    Returns: AsyncEngine configured from settings.database_url.
    Errors: sqlalchemy.exc.OperationalError if the DSN is invalid (only on
            the first actual connect, not on engine creation).
    """
    return _get_engine()
