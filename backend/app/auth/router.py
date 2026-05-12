"""
Hilo People — Auth APIRouter aggregator.

Slice:  P01-S02-T002 (debugger cycle 1 — split per validator F1).
        P01-S02-T003 — mounted refresh_router (additive 1-line change).
        P01-S02-T004 — mounted logout_router (additive 1-line change).
Phase:  P01 Auth + Data Foundation
Purpose: Build the top-level `auth_router` and mount per-endpoint sub-routers
         living in `app/auth/routers/`. Keeps this file ≤300 LOC and lets each
         endpoint family stay in its own module ("one responsibility per file").

Mounted endpoints (P01-S02 wave):
  - POST /api/v1/auth/sign-up     → app.auth.routers.sign_up.sign_up_router
  - POST /api/v1/auth/sign-in     → app.auth.routers.sign_in.sign_in_router
  - POST /api/v1/auth/refresh     → app.auth.routers.refresh.refresh_router
  - POST /api/v1/auth/logout      → app.auth.routers.logout.logout_router

Source refs:
  - TECHNICAL_GUIDE §6.2 endpoint catalogue.
  - 01-non-negotiables.md §File size (1 responsibility per file).
  - validator P01-S02-T002 cycle-1 finding F1.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.routers.logout import logout_router
from app.auth.routers.refresh import refresh_router
from app.auth.routers.sign_in import sign_in_router
from app.auth.routers.sign_up import sign_up_router

auth_router = APIRouter(prefix="/auth", tags=["auth"])
auth_router.include_router(sign_up_router)
auth_router.include_router(sign_in_router)
auth_router.include_router(refresh_router)
auth_router.include_router(logout_router)
