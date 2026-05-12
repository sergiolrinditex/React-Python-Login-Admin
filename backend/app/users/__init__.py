"""
Hilo People — Users feature package.

Slice:  P01-S02-T007 — GET /api/v1/users/me + PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: Re-exports the users_router for registration in app/main.py.
         This is the public surface of the users feature module.

Exported:
  users_router — APIRouter with GET /users/me and PATCH /users/me/language
                 Mounted under /api/v1 by main.py (prefix="/api/v1/users").
"""

from __future__ import annotations

from fastapi import APIRouter

from app.users.routers.me import me_router

users_router = APIRouter(prefix="/users", tags=["users"])
users_router.include_router(me_router)

__all__ = ["users_router"]
