"""
Hilo People — Shared SQLAlchemy sync engine and session factory.

Slice:  P01-S02-T002 — POST /api/v1/auth/sign-in
Phase:  P01 Auth + Data Foundation
Purpose: Centralises the sync SQLAlchemy engine, SessionLocal factory and
         get_db_session FastAPI generator dependency so that multiple routers
         (sign-up, sign-in, refresh, etc.) share a single engine instance.

         Extracted from backend/app/auth/router.py as a nit refactor flagged
         by the T001 validator: "next slice touching app/auth/ should extract
         _engine / _SessionLocal / get_db_session to app/db/session.py".

Key deps:
  - sqlalchemy==2.0.49 (create_engine, sessionmaker, Session)
  - os — DATABASE_URL env var

Source refs:
  - TECHNICAL_GUIDE §10.3 (DB connection strategy)
  - task pack P01-S02-T002 §K (T001 validator nit — extract db session)
  - 01-non-negotiables.md §Database (parametrized queries, transactions)

Decisions:
  - D-DB1: Uses sync psycopg (postgresql+psycopg://) matching the T001
    health-probe pattern. Async is deferred to P02 (YAGNI for auth slice).
  - D-DB2: pool_size=5, max_overflow=10 matches the T001 router.py defaults
    so extracted config is identical to what was there before.
  - D-DB3: URL normalisation strips legacy "postgresql://" prefix to ensure
    psycopg3 dialect is always used (matches T001 pattern).
"""

from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB URL normalisation — ensure psycopg3 dialect (postgresql+psycopg://)
# ---------------------------------------------------------------------------
_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev",
)
# Coerce legacy asyncpg or plain postgresql:// to the sync psycopg3 dialect.
if _DB_URL.startswith("postgresql+asyncpg://"):
    _DB_URL = _DB_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
elif _DB_URL.startswith("postgresql://") and not _DB_URL.startswith("postgresql+"):
    _DB_URL = _DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# ---------------------------------------------------------------------------
# Singleton engine + session factory (created once at module import)
# ---------------------------------------------------------------------------
_engine = create_engine(
    _DB_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI generator dependency: yield a DB session, close on exit.

    Creates a new session for each HTTP request and always closes it in the
    finally block, even if the handler raises. Commit/rollback is the caller's
    responsibility (service layer commits; router does not).

    Yields:
        A SQLAlchemy sync Session for the duration of one request.
    """
    logger.debug("db.session.open")  # BEFORE
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
        logger.debug("db.session.closed")  # AFTER
