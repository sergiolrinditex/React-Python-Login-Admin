"""
SQLAlchemy models package for Hilo People backend.

Slice: P01-S01-T001 — DB auth baseline
       P00-S02-T006 — admin_ai models added
Phase: P01 — Auth + base capabilities

Exports:
  - Base     — shared DeclarativeBase (+ naming convention); required by
               alembic/env.py for target_metadata.
  - User     — users table (auth domain entity)
  - EmployeeProfile — employee_profiles table
  - user_roles_table — association table (no ORM class needed)
  - Role, Permission — roles/permissions lookup tables
  - RefreshToken, MfaTotpSecret, PasswordResetToken, AuditLog — auth tables
  - AiProvider, AiProviderCredential, AiModel — admin_ai tables (0003)

Alembic's env.py imports `from app.db.models import Base` which triggers the
import of all sub-modules here, registering their Table objects in
Base.metadata before autogenerate runs.

Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3
Task-pack P01-S01-T001 §4.2 (model split rationale)
Task-pack P00-S02-T006 §7.3 (admin_ai models)

Note: no logging here — pure package re-export module.
"""
from app.db.models.admin_ai import AiModel, AiProvider, AiProviderCredential
from app.db.models.auth import (
    AuditLog,
    MfaTotpSecret,
    PasswordResetToken,
    Permission,
    RefreshToken,
    Role,
)
from app.db.models.base import Base
from app.db.models.user import EmployeeProfile, User, user_roles_table

__all__ = [
    "Base",
    "User",
    "EmployeeProfile",
    "user_roles_table",
    "Role",
    "Permission",
    "RefreshToken",
    "MfaTotpSecret",
    "PasswordResetToken",
    "AuditLog",
    "AiProvider",
    "AiProviderCredential",
    "AiModel",
]
