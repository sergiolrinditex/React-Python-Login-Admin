"""
Alembic async migration environment for Hilo People backend.

Slice: P01-S01-T001 — DB auth baseline (Alembic bootstrap + migration 0001)
Phase: P01 — Auth + base capabilities

Wiring:
  - Uses app.core.db.get_engine() (lazy AsyncEngine singleton) so the DSN is
    consistent between the FastAPI app and migration runs.
  - Imports app.db.models to populate Base.metadata for autogenerate safety.
  - compare_type=True, compare_server_default=True for future autogen runs.
  - DATABASE_URL is read from pydantic Settings (app.core.config.get_settings()),
    NOT from alembic.ini sqlalchemy.url (which is intentionally blank).

Dependencies:
  - alembic 1.18.4
  - sqlalchemy[asyncio] 2.0.49
  - asyncpg 0.31.0
  - app.core.db (lazy AsyncEngine)
  - app.core.config (Settings / get_settings)
  - app.db.models (Base metadata)

Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3, task-pack P01-S01-T001 §7.5
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import context
from app.core.db import get_engine
from app.core.logging import configure_logging, get_logger

# Import the shared Base (populates Base.metadata with all declared models).
# This import must happen before run_migrations_online() so autogenerate
# can detect model changes in future runs.
from app.db.models import Base  # noqa: F401 — side-effect import for metadata

_logger = get_logger(__name__)

# Alembic Config object provides access to values within the .ini file.
config = context.config

# Wire stdlib logging from the ini's [loggers] section (writes to stderr).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Configure app structlog so env.py logs follow the same BEFORE/AFTER pattern.
# Use the ENABLE_VERBOSE_LOGGING env var — same as the FastAPI app.
import os as _os  # noqa: E402

_verbose = _os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")
configure_logging(verbose=_verbose)

# Autogenerate target: all SQLAlchemy models imported above via app.db.models.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This mode skips engine/connection creation and emits raw SQL statements
    directly to the output stream. Useful for generating migration scripts
    without a live DB.

    Source: Alembic 1.18 async template (offline path remains synchronous).
    """
    _logger.debug("BEFORE run_migrations_offline: starting offline migration run")
    url = get_engine().url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()
    _logger.debug("AFTER run_migrations_offline: migrations emitted to stdout")


def do_run_migrations(connection: Any) -> None:  # type: ignore[name-defined]
    """Execute migrations synchronously within an async connection run_sync call.

    Purpose: adapter for run_async_migrations — SQLAlchemy run_sync passes a
    synchronous Connection wrapper to this function.
    Params:
      connection — synchronous Connection (wrapped from AsyncConnection).
    Returns: None.
    Errors: propagated from context.run_migrations().
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations(engine: AsyncEngine) -> None:
    """Acquire an async connection and run migrations.

    Purpose: async wrapper that calls do_run_migrations via run_sync.
    The run_sync call lets SQLAlchemy execute the synchronous Alembic context
    inside an asyncio event loop without blocking.

    Params:
      engine — the shared AsyncEngine from app.core.db.get_engine().
    Returns: None.
    Errors: sqlalchemy.exc.* propagated.
    """
    _logger.debug("BEFORE run_async_migrations: acquiring async connection")
    async with engine.connect() as connection:
        _logger.debug("AFTER run_async_migrations: connection acquired, running migrations")
        await connection.run_sync(do_run_migrations)
    _logger.debug("AFTER run_async_migrations: migrations complete, disposing engine")
    await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (default — requires a live DB).

    Acquires the shared AsyncEngine (from app.core.db.get_engine()), runs
    migrations asynchronously via asyncio.run(), and disposes the engine.

    Purpose: main entry point for `alembic upgrade head` etc.
    Returns: None.
    Errors: asyncio.run propagates any DB or migration errors.
    """
    _logger.debug("BEFORE run_migrations_online: preparing async engine")
    engine = get_engine()
    _logger.debug(
        "AFTER run_migrations_online: engine ready, dispatching async migrations"
    )
    asyncio.run(run_async_migrations(engine))
    _logger.debug("AFTER run_migrations_online: async migration run complete")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
