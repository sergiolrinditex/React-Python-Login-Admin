"""
Core infrastructure package for Hilo People backend.

Slice: P00-S01-T003 — Backend dependency pack
Phase: P00 — Scaffold + Design System

Exposes: Settings (config), configure_logging, get_logger, get_session, engine.
Every feature module imports from this package; no feature code lives here.

Dependencies (installed in this slice):
  - pydantic-settings (config)
  - structlog (logging)
  - sqlalchemy[asyncio] + asyncpg (db)
"""
