"""
Hilo People — HTTP router: GET /me and PATCH /me/language.

Slice:  P01-S02-T007 — GET /api/v1/users/me + PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: FastAPI router for the two user-profile endpoints. Both routes share
         the same Bearer authentication via get_current_user dependency.
         Mounted under /api/v1/users by main.py.

Endpoints:
  GET  /users/me               → 200 UserProfileResponse | 401 AUTH_SESSION_EXPIRED
  PATCH /users/me/language     → 200 UserProfileResponse | 400 AUTH_INVALID_PAYLOAD | 401

Dependencies:
  - fastapi (APIRouter, Depends, Request)
  - app.users.deps.get_current_user — Bearer → User ORM dependency
  - app.users.schemas — UserProfile, UserProfileResponse, LanguagePatchRequest
  - app.users.services.get_current_user_profile.build_user_profile — GET use case
  - app.users.services.update_user_language.patch_user_language — PATCH use case
  - app.auth.routers._helpers — _get_request_id, _get_client_ip, _error_response
  - app.db.session.get_db_session — sync session dep
  - app.auth.schemas.ResponseMeta — meta envelope

Source refs:
  - task pack §F.1 (GET /me contract)
  - task pack §F.2 (PATCH /me/language contract — 200 NOT 204, DISCREPANCY-1)
  - task pack §G.13 (router file layout)
  - task pack §F.5 (logging contract: BEFORE/AFTER verbose; WARNING always)
  - TECHNICAL_GUIDE §6.2 rows 262, 263

Decisions:
  - G.7: The global RequestValidationError handler in main.py maps 422 → 400
    AUTH_INVALID_PAYLOAD for /api/v1/users/me/language. This router trusts that
    handler; it only needs to handle explicit domain errors.
  - Logging contract: GET /me is high-frequency — BEFORE/AFTER are DEBUG (only
    visible when ENABLE_VERBOSE_LOGGING=true). WARNING+ always visible.
  - get_current_user returns User or JSONResponse (anti-enum auth failure). Router
    checks isinstance and returns early.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.routers._helpers import _get_client_ip, _get_request_id
from app.auth.schemas import ResponseMeta
from app.db.models.user import User
from app.db.session import get_db_session
from app.users.deps import get_current_user
from app.users.schemas import LanguagePatchRequest, UserProfileResponse
from app.users.services.get_current_user_profile import build_user_profile
from app.users.services.update_user_language import patch_user_language

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

me_router = APIRouter(tags=["users"])


# ---------------------------------------------------------------------------
# GET /users/me
# ---------------------------------------------------------------------------

@me_router.get("/me", response_model=UserProfileResponse)
async def get_me(
    request: Request,
    current_user: User | JSONResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserProfileResponse | JSONResponse:
    """Return the current authenticated user's full profile.

    High-frequency endpoint (called on every page navigation in the frontend).
    BEFORE/AFTER logs are DEBUG-level (verbose mode only) to avoid INFO spam.

    Args:
        request: Incoming HTTP request (for request_id extraction).
        current_user: User ORM (authenticated) or JSONResponse (401 anti-enum).
        session: SQLAlchemy sync session (unused for GET; already loaded via dep).

    Returns:
        UserProfileResponse (HTTP 200) on success.
        JSONResponse (HTTP 401) if authentication failed.
    """
    request_id = _get_request_id(request)

    # Auth guard — dep returns JSONResponse on failure (anti-enum G.3).
    if isinstance(current_user, JSONResponse):
        return current_user

    logger.debug(
        "users.routers.me.request_received method=GET request_id=%s ip=%s",
        request_id,
        _get_client_ip(request),
    )  # BEFORE (verbose only)

    profile = build_user_profile(current_user)

    logger.debug(
        "users.routers.me.response_built user_id=%s status=200 request_id=%s",
        str(current_user.id),
        request_id,
    )  # AFTER (verbose only)

    return UserProfileResponse(
        data=profile,
        meta=ResponseMeta(request_id=request_id),
        errors=[],
    )


# ---------------------------------------------------------------------------
# PATCH /users/me/language
# ---------------------------------------------------------------------------

@me_router.patch("/me/language", response_model=UserProfileResponse)
async def patch_me_language(
    request: Request,
    body: LanguagePatchRequest,
    current_user: User | JSONResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserProfileResponse | JSONResponse:
    """Update the current user's preferred language.

    Returns HTTP 200 with the full updated UserProfile (NOT 204 — DISCREPANCY-1
    resolved: §6.2 row 263 says {data: UserProfile}).

    400 AUTH_INVALID_PAYLOAD is produced by the global RequestValidationError
    handler in main.py (G.7) for Pydantic validation failures — this handler
    receives the /api/v1/users/me/language path explicitly.

    Args:
        request: Incoming HTTP request (for request_id, client_ip, user_agent).
        body: Validated language patch request (Pydantic strict — extra fields rejected).
        current_user: User ORM (authenticated) or JSONResponse (401 anti-enum).
        session: SQLAlchemy sync session for DB write.

    Returns:
        UserProfileResponse (HTTP 200) with updated profile on success.
        JSONResponse (HTTP 401) if authentication failed.
    """
    request_id = _get_request_id(request)
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    # Auth guard — dep returns JSONResponse on failure (anti-enum G.3).
    if isinstance(current_user, JSONResponse):
        return current_user

    logger.debug(
        "users.routers.me.language_patch_request received from=%s to=%s user_id=%s request_id=%s",
        current_user.preferred_language,
        body.language,
        str(current_user.id),
        request_id,
    )  # BEFORE (verbose only)

    try:
        profile = patch_user_language(
            session=session,
            user=current_user,
            new_language=body.language,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
    except Exception as exc:
        logger.error(
            "users.routers.me.language_patch_error user_id=%s error=%s request_id=%s",
            str(current_user.id),
            str(exc),
            request_id,
            exc_info=True,
        )
        raise

    logger.debug(
        "users.routers.me.language_patch_success user_id=%s from=%s to=%s request_id=%s",
        str(current_user.id),
        current_user.preferred_language,
        body.language,
        request_id,
    )  # AFTER (verbose only)

    return UserProfileResponse(
        data=profile,
        meta=ResponseMeta(request_id=request_id),
        errors=[],
    )
