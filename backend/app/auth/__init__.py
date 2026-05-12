"""
Hilo People — Auth feature module.

Slices covered:
  - P01-S02-T001 — POST /api/v1/auth/sign-up
  - P01-S02-T002 — POST /api/v1/auth/sign-in (incl. MFA challenge branch,
                     opaque refresh token in HttpOnly cookie, JWT access token)

Phase:  P01 Auth + Data Foundation
Purpose: Package marker for the auth feature module. Exports the `auth_router`
         for mounting in `app/main.py` under `/api/v1`.

Submodules:
  - domain.py        — CorporateEmail, Password value objects (pure)
  - errors.py        — Typed domain errors + HTTP code mapping
  - password.py      — Argon2id hash/verify wrapper + DUMMY_VERIFY_HASH +
                       verify_with_dummy_fallback() for aggregate-401 timing
  - rate_limit.py    — In-memory per-IP token bucket (sign-up + sign-in;
                       → Redis in P02-S02-T001)
  - repository.py    — AuthRepository (find_by_email, create_user, write_audit,
                       count_recent_signin_failures, insert_refresh_token)
  - schemas.py       — Pydantic request/response DTOs (sign-up + sign-in)
  - tokens.py        — PyJWT encode_access_token / encode_mfa_challenge_token /
                       decode_token (HS256, claims per §10.2; sign-in slice)
  - services/        — One use case per file
      - sign_up.py   — SignUpUser, SignUpResult
      - sign_in.py   — SignInUser, SignInResult (aggregate-401, lockout, MFA,
                       refresh-token issuance, opportunistic Argon2 rehash)
  - service.py       — Compat shim re-exporting from services/
  - routers/         — One router per endpoint family
      - sign_up.py   — POST /sign-up handler + APIRouter
      - sign_in.py   — POST /sign-in handler + APIRouter
      - _helpers.py  — _get_request_id, _get_client_ip, _error_response (shared)
  - router.py        — Aggregator: builds auth_router and mounts both sub-routers

Dependencies:
  - app.db.models.user (User)
  - app.db.models.auth (AuditLog, MfaTotpSecret, RefreshToken)
  - app.db.session (get_db_session — shared FastAPI Depends)
"""

from app.auth.router import auth_router

__all__ = ["auth_router"]
