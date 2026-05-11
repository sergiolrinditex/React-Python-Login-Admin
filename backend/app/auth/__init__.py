"""
Hilo People — Auth feature module.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Package marker for the auth feature module. Exports the auth_router
         for mounting in app/main.py under /api/v1.

Submodules:
  - domain.py    — CorporateEmail, Password value objects (pure)
  - errors.py    — Typed domain errors + HTTP code mapping
  - password.py  — Argon2id hash/verify wrapper
  - rate_limit.py — In-memory per-IP token bucket (→ Redis in P02-S02-T001)
  - repository.py — AuthRepository (data layer)
  - schemas.py   — Pydantic request/response DTOs
  - service.py   — SignUpUser use case (domain orchestration)
  - router.py    — FastAPI APIRouter (presentation layer)

Dependencies:
  - app.db.models.user (User)
  - app.db.models.auth (AuditLog)
"""

from app.auth.router import auth_router

__all__ = ["auth_router"]
