"""
SQLAlchemy declarative Base with naming convention for Hilo People.

Slice: P01-S01-T001 — DB auth baseline
Phase: P01 — Auth + base capabilities

All SQLAlchemy model classes in this project inherit from `Base` declared here.
The naming convention ensures Alembic autogenerate produces stable, deterministic
constraint names (indexes, FKs, unique, check) across runs.

Without a naming convention set on Base.metadata, SQLAlchemy generates anonymous
constraint names that differ between DB instances — autogenerate then detects
spurious diffs on every run.  Setting it here (BEFORE the first model is declared)
locks the pattern project-wide.

Convention format (SQLAlchemy 2.x recommended):
  ix_<table>_<column>       — Index
  uq_<table>_<column>       — Unique constraint
  ck_<table>_<constraint>   — Check constraint
  fk_<table>_<column>_<ref> — Foreign key
  pk_<table>                — Primary key

Source:
  HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 migration design notes
  Task-pack P01-S01-T001 §7.1 (naming convention)
  01-non-negotiables.md §Database (indexes, FK constraints)

Dependencies:
  - sqlalchemy 2.0.49

Note: no logging here — this is a pure declarative module (same exemption as
presentational UI components per planner MEMORY.md §design-token slices and
task-pack §8).
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for all Hilo People SQLAlchemy models.

    All ORM models inherit from this class to share the same metadata
    object and naming convention.  The naming convention is applied to
    Base.metadata at class-creation time — every model declared afterwards
    uses it automatically.

    Purpose: single source of metadata for Alembic target_metadata.
    Errors: none at class definition time.
    """

    metadata = sa.MetaData(naming_convention=NAMING_CONVENTION)
