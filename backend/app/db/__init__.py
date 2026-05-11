"""
Hilo People — SQLAlchemy database package marker.

Slice:  P01-S01-T001 — 0001_auth_users_employee_audit migration
Phase:  P01 Auth + Data Foundation
Purpose: Package marker for the app.db namespace. When imported, triggers
         registration of all model classes with Base.metadata so that
         Alembic can detect the full schema during upgrade/downgrade/autogenerate.

         Import order within this module:
         1. app.db.base is imported by app.db.models.* (transitively)
         2. app.db.models triggers all model class registrations

Key deps:
  - app.db.base   — DeclarativeBase singleton (Base)
  - app.db.models — model sub-package (user.py, auth.py)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 DB Schema
  - WRITE_SET_EXTENSION: justified by need to trigger model registration;
    precedent from app/core/__init__.py (P00-S01-T003).
"""

from app.db import models as _models  # noqa: F401 — triggers Base.metadata population

__all__: list[str] = []
