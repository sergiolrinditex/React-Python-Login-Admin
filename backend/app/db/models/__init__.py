"""
Hilo People — ORM models sub-package.

Slice:  P01-S01-T001 — 0001_auth_users_employee_audit migration
Phase:  P01 Auth + Data Foundation
Purpose: Imports all model modules so their classes register with Base.metadata
         when this package is imported. Alembic env.py imports app.db which
         imports this package, ensuring every mapped table is known to metadata
         before autogenerate or upgrade/downgrade runs.

Modules:
  - user.py  — User, EmployeeProfile, Role, Permission, UserRole (identity + RBAC)
  - auth.py  — RefreshToken, MfaTotpSecret, PasswordResetToken, AuditLog (auth session + audit)

Key deps:
  - app.db.base  — Base declarative class
  - sqlalchemy==2.0.49

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 DB Schema
  - WRITE_SET_EXTENSION: package marker required for module discovery; same
    pattern as app/core/__init__.py (P00-S01-T003).

Decisions:
  - D3: Models split by bounded context — identity (user.py) vs session/audit (auth.py).
"""

from app.db.models import user as _user_models  # noqa: F401 — registers User, EmployeeProfile, Role, Permission, UserRole
from app.db.models import auth as _auth_models  # noqa: F401 — registers RefreshToken, MfaTotpSecret, PasswordResetToken, AuditLog

__all__ = ["_user_models", "_auth_models"]
