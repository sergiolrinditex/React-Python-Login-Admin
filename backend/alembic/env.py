"""
Alembic environment configuration for Hilo People backend.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: Bootstraps Alembic with a sync SQLAlchemy engine driven by the
         DATABASE_URL environment variable. Currently uses target_metadata=None
         (no models yet); P01-S01-T001 will replace this with Base.metadata.

Key deps:
  - alembic==1.18.4 (run_migrations_online/offline pattern)
  - sqlalchemy==2.0.49 (create_engine, sync)
  - DATABASE_URL env var (postgresql+psycopg://... or postgresql+psycopg2://...)
  - ENABLE_VERBOSE_LOGGING env var (controls alembic log level)

Source refs:
  - STACK_PROFILE.yaml db.migrate_cmd: alembic upgrade head
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §4 backend structure
  - 01-non-negotiables.md §Logging (BEFORE/AFTER, never PII)
"""

import os
import logging
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to alembic.ini settings
# ---------------------------------------------------------------------------
config = context.config

# ---------------------------------------------------------------------------
# Logging configuration
# ENABLE_VERBOSE_LOGGING controls verbosity; code never conditionally wraps logs.
# Per 01-non-negotiables.md §Logging.
# ---------------------------------------------------------------------------
_verbose: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_alembic_logger = logging.getLogger("alembic")
_alembic_logger.setLevel(logging.INFO if _verbose else logging.WARNING)

# ---------------------------------------------------------------------------
# Target metadata — None until P01-S01-T001 adds models.
# P01-S01-T001 will replace this line with:
#   from app.db.base import Base; target_metadata = Base.metadata
# ---------------------------------------------------------------------------
target_metadata = None


def _get_database_url() -> str:
    """Return the sync Postgres URL, converting asyncpg dialect if needed.

    alembic runs sync; we strip 'postgresql+asyncpg://' → 'postgresql+psycopg://'
    to avoid 'asyncpg not usable in sync context' errors at migration time.

    Returns:
        Sync-compatible postgresql URL string.

    Raises:
        RuntimeError: If DATABASE_URL is not set.
    """
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it to postgresql+psycopg://user:pass@host:port/db for Alembic."
        )
    # Normalise asyncpg URLs to psycopg for sync migration runs.
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL, no live connection).

    Useful for producing a migration script for review before applying.
    Per Alembic 1.18 documentation — offline migration pattern.
    """
    _alembic_logger.info("alembic.env.offline.start")
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
    _alembic_logger.info("alembic.env.offline.done")


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection).

    Creates a sync connection pool, begins a transaction, and runs all
    pending migration scripts. pool.NullPool prevents connection leaks in
    short-lived CLI invocations.

    Per 01-non-negotiables.md §Logging: logs BEFORE and AFTER, never PII.
    """
    _alembic_logger.info("alembic.env.online.start")
    url = _get_database_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()
    _alembic_logger.info("alembic.env.online.done")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
