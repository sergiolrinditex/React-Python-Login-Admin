"""
Seed data package for verification bundle loading.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Provides the idempotent CLI loader for the data/verification/ bundle.
All namespaces are table-tolerant: missing tables produce WARN + exit 0
(P01-S01-T001 creates the schema; this package predates that slice).

Dependencies:
  - pydantic 2.12.5
  - sqlalchemy[asyncio] 2.0.49
  - structlog 25.5.0
"""
