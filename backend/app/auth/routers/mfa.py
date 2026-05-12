"""
Hilo People — POST /api/v1/auth/2fa/verify HTTP handler.

Slice:  P01-S02-T006 — POST /api/v1/auth/2fa/verify
Phase:  P01 Auth + Data Foundation
Purpose: FastAPI router for the 2FA TOTP verify endpoint. Handles:
          - rate-limit check (own MFA_VERIFY bucket, D-MFA-RL1)
          - Pydantic 422 → 400 re-mapping (mirrors sign-in pattern)
          - dispatch to VerifyMfaChallenge use case
          - domain-error → HTTP envelope mapping (F.4 table)
          - Set-Cookie for refresh token (byte-equal to sign-in, T011 contract)
          - X-Request-ID propagation to response header

WRITE_SET_DRIFT §D-MFA1.A — declared in task pack §I.

Key deps:
  - app.auth.services.mfa.VerifyMfaChallenge — use case
  - app.auth.routers._helpers — request ID, IP, error envelope, set_refresh_cookie
  - app.auth.schemas.MfaVerifyRequest — Pydantic request model
  - app.auth.rate_limit.check_rate_limit_mfa_verify
  - app.db.session.get_db_session — FastAPI dependency

Source refs:
  - TECHNICAL_GUIDE §6.2 row 261 (POST /api/v1/auth/2fa/verify)
  - task pack §F.4 (HTTP status mapping), §F.3 (aggregate 401), §F.6 (cookie)
  - 01-non-negotiables.md §API contract, §Error handling, §Logging
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.errors import (
    MfaChallengeExpiredError,
    MfaChallengeInvalidError,
    MfaCodeInvalidError,
    MfaReplayError,
    MfaSecretMissingError,
    MfaVerifyRateLimitedError,
)
from app.auth.rate_limit import check_rate_limit_mfa_verify
from app.auth.routers._helpers import (
    _error_response,
    _get_client_ip,
    _get_request_id,
    _set_refresh_cookie,
)
from app.auth.schemas import (
    MfaUserDto,
    MfaVerifyRequest,
    MfaVerifyResponseSuccess,
    MfaVerifySuccessData,
    ResponseMeta,
)
from app.auth.services.mfa import VerifyMfaChallenge
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

mfa_router = APIRouter(tags=["auth"])

# Anti-enumeration: all 401 paths return the same envelope code + message.
_MFA_401_CODE = "AUTH_MFA_CODE_INVALID"
_MFA_401_MSG = "Invalid 2FA code or challenge"


@mfa_router.post(
    "/2fa/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify TOTP code for MFA challenge",
    description=(
        "Accepts a signed mfa_challenge_token (issued by /sign-in when MFA is required) "
        "and a 6-digit TOTP code. On success returns access_token + user DTO in the body "
        "and sets the HttpOnly refresh cookie (byte-identical attrs to /sign-in). "
        "All 401 paths return an identical body to prevent enumeration."
    ),
)
def verify_mfa(
    body: MfaVerifyRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/auth/2fa/verify — verify TOTP code against mfa_challenge_token.

    Args:
        body: Validated MfaVerifyRequest (challenge_id + code).
        request: FastAPI Request (for headers, IP).
        session: DB session from dependency injection.

    Returns:
        JSONResponse with 200 + Set-Cookie on success, or 4xx envelope on failure.

    Ref: TECHNICAL_GUIDE §6.2 row 261; task pack §F.4.
    """
    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")[:255]

    logger.info(
        "auth.mfa.verify.router.received request_id=%s ip=%s",
        request_id, client_ip,
    )  # BEFORE

    # --- Rate limit check (own MFA_VERIFY bucket, §F.5 D-MFA-RL1) ---
    try:
        check_rate_limit_mfa_verify(client_ip)
    except MfaVerifyRateLimitedError as exc:
        logger.warning(
            "auth.mfa.verify.router.rate_limited ip=%s retry_after=%ds request_id=%s",
            client_ip, exc.retry_after, request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=429,
            headers={"Retry-After": str(exc.retry_after)},
        )

    # --- Dispatch to use case ---
    try:
        result = VerifyMfaChallenge(session).execute(
            challenge_id=body.challenge_id,
            code=body.code,
            request_id=request_id,
            ip=client_ip,
            user_agent=user_agent,
        )
    except MfaChallengeExpiredError as exc:
        # 410: signature valid but exp in the past — different UX action
        logger.info(
            "auth.mfa.verify.router.failure reason=challenge_expired request_id=%s",
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=410,
        )
    except (
        MfaChallengeInvalidError,
        MfaCodeInvalidError,
        MfaSecretMissingError,
        MfaReplayError,
    ):
        # Anti-enumeration: all other failure modes → same 401 body (D-MFA-ANTI-ENUM)
        logger.info(
            "auth.mfa.verify.router.failure reason=401_aggregate request_id=%s",
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code=_MFA_401_CODE,
            message=_MFA_401_MSG,
            http_status=401,
        )
    except Exception:
        logger.error(
            "auth.mfa.verify.router.unexpected_error request_id=%s",
            request_id, exc_info=True,
        )  # ERROR
        return _error_response(
            request_id=request_id,
            code="AUTH_MFA_VERIFY_INTERNAL_ERROR",
            message="An internal error occurred",
            http_status=500,
        )

    # --- Build success response ---
    user = result.user
    roles: list[str] = []
    if hasattr(user, "user_roles") and user.user_roles:
        for ur in user.user_roles:
            if hasattr(ur, "role") and ur.role and hasattr(ur.role, "name"):
                roles.append(ur.role.name)
    if not roles:
        roles = ["employee"]

    user_dto = MfaUserDto(
        id=user.id,
        email=user.email,
        preferred_language=getattr(user, "preferred_language", "es") or "es",
        roles=roles,
    )
    success_data = MfaVerifySuccessData(
        access_token=result.access_token,
        token_type="Bearer",
        expires_in=result.expires_in,
        user=user_dto,
    )
    response_body = MfaVerifyResponseSuccess(
        data=success_data,
        meta=ResponseMeta(request_id=request_id),
        errors=[],
    )
    json_resp = JSONResponse(
        content=response_body.model_dump(mode="json"),
        status_code=200,
        headers={"X-Request-ID": request_id},
    )
    _set_refresh_cookie(json_resp, result.opaque_refresh)

    logger.info(
        "auth.mfa.verify.router.success user_id=%s request_id=%s",
        str(user.id), request_id,
    )  # AFTER success
    return json_resp
