"""
Hilo People — FastAPI dependency: get_current_user (Bearer token → User ORM).

Slice:  P01-S02-T007 — GET /api/v1/users/me + PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: Reusable FastAPI dependency that extracts and validates the Bearer token
         from the Authorization header, decodes it with app.auth.tokens.decode_token,
         and fetches the User ORM instance with eager-loaded employee_profile +
         user_roles. All failure modes emit the same AUTH_SESSION_EXPIRED envelope
         (anti-enumeration per G.3).

Dependencies:
  - fastapi (Request, Header, Depends)
  - app.auth.tokens.decode_token — existing JWT decoder (G.2)
  - app.users.repositories.user_profile.find_by_id_with_employee_and_roles
  - app.users.errors — typed domain errors
  - app.auth.routers._helpers — _get_request_id, _get_client_ip, _error_response
  - app.db.session.get_db_session — sync session dependency

Source refs:
  - task pack §G.1 (dep lives in users/deps.py, not in auth/)
  - task pack §G.2 (decode_token reuse + defensive purpose check)
  - task pack §G.3 (anti-enum: byte-equal 401 envelope for all failure modes)
  - TECHNICAL_GUIDE §6.2 rows 262/263 (401 contract)

Decisions:
  - G.1: New file under users/ — clean architecture, consumers own their deps.
  - G.2: decode_token with expected_purpose=None. Defensively rejects tokens
         with any 'purpose' claim set (e.g. mfa_challenge tokens).
  - G.3: All 401 paths emit AUTH_SESSION_EXPIRED via _error_response.
         The reason is logged as WARNING only — never in the JSON body.
  - G.4/G.5: No audit row on GET /me failures (would flood; GET is read-only).
  - NEVER log Bearer token value or JWT claims jti.
"""

from __future__ import annotations

import logging
import uuid

import jwt
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.auth.tokens import decode_token
from app.db.models.user import User
from app.db.session import get_db_session
from app.users.repositories.user_profile import find_by_id_with_employee_and_roles

logger = logging.getLogger(__name__)

# Sentinel response returned when authentication fails (used as a type alias).
_AUTH_ERROR_CODE = "AUTH_SESSION_EXPIRED"
_AUTH_ERROR_MSG = "Session expired or invalid credentials. Please sign in again."


def _emit_401(request_id: str) -> JSONResponse:
    """Build the anti-enum 401 JSON response (byte-equal across all failure modes).

    Args:
        request_id: X-Request-ID for correlation.

    Returns:
        JSONResponse with status 401 and AUTH_SESSION_EXPIRED envelope.
    """
    return _error_response(
        request_id=request_id,
        code=_AUTH_ERROR_CODE,
        message=_AUTH_ERROR_MSG,
        http_status=401,
    )


async def get_current_user(
    request: Request,
    session: Session = Depends(get_db_session),
) -> User | JSONResponse:
    """FastAPI dependency: decode Bearer token and return authenticated User.

    Returns the User ORM instance with eager-loaded employee_profile and
    user_roles on success.

    Returns a JSONResponse (401) when any authentication check fails:
      - Missing Authorization header.
      - Malformed Bearer scheme.
      - Invalid JWT signature.
      - Expired JWT.
      - Token with a 'purpose' claim (mfa_challenge token replay).
      - sub UUID not found in DB.
      - User.status != 'active'.

    Routers must check `isinstance(result, JSONResponse)` and return early.

    Args:
        request: Incoming FastAPI Request (used for X-Request-ID and client IP).
        session: SQLAlchemy sync Session from get_db_session dependency.

    Returns:
        User ORM instance on success; JSONResponse (HTTP 401) on failure.
    """
    request_id = _get_request_id(request)
    ip = _get_client_ip(request)

    logger.debug(
        "users.deps.get_current_user.start request_id=%s ip=%s", request_id, ip
    )  # BEFORE

    # Step 1: Extract Bearer token from Authorization header.
    auth_header = request.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning(
            "users.deps.auth_failed reason=missing_bearer request_id=%s", request_id
        )
        return _emit_401(request_id)

    raw_token = auth_header[len("Bearer "):]
    if not raw_token:
        logger.warning(
            "users.deps.auth_failed reason=empty_bearer request_id=%s", request_id
        )
        return _emit_401(request_id)

    # Step 2: Decode and validate JWT.
    try:
        decoded = decode_token(raw_token, expected_purpose=None)
    except jwt.ExpiredSignatureError:
        logger.warning(
            "users.deps.auth_failed reason=expired_token request_id=%s", request_id
        )
        return _emit_401(request_id)
    except (jwt.InvalidTokenError, ValueError):
        logger.warning(
            "users.deps.auth_failed reason=invalid_token request_id=%s", request_id
        )
        return _emit_401(request_id)

    # Step 3: G.2 defensive check — reject tokens with any 'purpose' claim.
    if decoded.get("purpose"):
        logger.warning(
            "users.deps.auth_failed reason=purpose_claim_present request_id=%s",
            request_id,
        )
        return _emit_401(request_id)

    # Step 4: Extract sub (user UUID).
    sub = decoded.get("sub")
    if not sub:
        logger.warning(
            "users.deps.auth_failed reason=missing_sub request_id=%s", request_id
        )
        return _emit_401(request_id)

    try:
        user_id = uuid.UUID(str(sub))
    except ValueError:
        logger.warning(
            "users.deps.auth_failed reason=invalid_sub_uuid request_id=%s", request_id
        )
        return _emit_401(request_id)

    # Step 5: Load user from DB with eager-loaded relationships.
    user = find_by_id_with_employee_and_roles(session, user_id)
    if user is None:
        logger.warning(
            "users.deps.auth_failed reason=user_not_found user_id=%s request_id=%s",
            str(user_id),
            request_id,
        )
        return _emit_401(request_id)

    # Step 6: Verify user is active.
    if user.status != "active":
        logger.warning(
            "users.deps.auth_failed reason=user_inactive user_id=%s status=%s request_id=%s",
            str(user.id),
            user.status,
            request_id,
        )
        return _emit_401(request_id)

    logger.debug(
        "users.deps.get_current_user.done user_id=%s request_id=%s",
        str(user.id),
        request_id,
    )  # AFTER
    return user
