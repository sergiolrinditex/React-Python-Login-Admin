"""
Hilo People — SQLAlchemy DeclarativeBase singleton.

Slice:  P01-S01-T001 — 0001_auth_users_employee_audit migration
Phase:  P01 Auth + Data Foundation
Purpose: Declares the single SQLAlchemy 2.x DeclarativeBase class used by all
         ORM models in this project. Also declares a MetaData instance with
         explicit naming_convention so Alembic can generate predictable, named
         constraints (required for downgrade by name, not by inference).

Key deps:
  - sqlalchemy==2.0.49 (DeclarativeBase, MetaData)
  - alembic==1.18.4 (consumes Base.metadata)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 DB Schema
  - https://alembic.sqlalchemy.org/en/latest/naming.html (naming_convention)
  - WRITE_SET_EXTENSION: justified to avoid import cycles between user.py and
    auth.py (both are peers in bounded context auth). Precedent P00-S01-T003.
  - P01-S01-T001 §9.3 U3 — naming_convention chosen per Alembic recommendation.

Decisions:
  - D4: Base lives here (not in user.py) to avoid circular imports user↔auth.
"""

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Naming convention — Alembic recommendation for named constraints so that
# `alembic downgrade` can drop them by name without guessing.
# Reference: https://alembic.sqlalchemy.org/en/latest/naming.html
# ---------------------------------------------------------------------------
_NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy 2.x declarative base with named constraints.

    All ORM models must inherit from this class so their tables are included
    in Base.metadata and visible to Alembic autogenerate / env.py.

    Per SQLAlchemy 2.x DeclarativeBase pattern (not legacy declarative_base()).
    Ref: https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html
    """

    metadata = sa.MetaData(naming_convention=_NAMING_CONVENTION)
