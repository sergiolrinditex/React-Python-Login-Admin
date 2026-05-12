"""
Hilo People — Auth routers package.

Slice:  P01-S02-T002 (debugger cycle 1 — split per validator F1).
        P01-S02-T003 — added refresh_router.
        P01-S02-T004 — added logout_router.
Phase:  P01 Auth + Data Foundation
Purpose: Holds one router file per endpoint family to keep `router.py`
         readable (≤300 LOC) per 01-non-negotiables.md §File size.

Submodules:
  - _helpers.py   — _get_request_id, _get_client_ip, _error_response,
                    _set_refresh_cookie (shared; P01-S02-T003),
                    _clear_refresh_cookie (P01-S02-T004)
  - sign_up.py    — POST /sign-up handler + its APIRouter
  - sign_in.py    — POST /sign-in handler + its APIRouter
  - refresh.py    — POST /refresh handler + its APIRouter (P01-S02-T003)
  - logout.py     — POST /logout handler + its APIRouter (P01-S02-T004)
"""

from app.auth.routers.logout import logout_router
from app.auth.routers.refresh import refresh_router
from app.auth.routers.sign_in import sign_in_router
from app.auth.routers.sign_up import sign_up_router

__all__ = ["logout_router", "refresh_router", "sign_in_router", "sign_up_router"]
