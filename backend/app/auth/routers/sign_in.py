"""
Hilo People — POST /api/v1/auth/sign-in router.

Slice:  P01-S02-T002 — POST /api/v1/auth/sign-in
        (Extracted from `app/auth/router.py` in debugger cycle 1 per validator
        F1 "file size hard cap"; F5 "use Depends(get_db_session)".)
        P01-S02-T003 — refactored to use shared `_set_refresh_cookie` helper
        (D-RP2: byte-identical cookie attrs with /refresh).
Phase:  P01 Auth + Data Foundation
Responsibility: parse SignInRequest, rate-limit, dispatch to SignInUser,
                map domain errors to the envelope, set HttpOnly refresh cookie
                on the no-MFA branch, return 200 envelope.

Decisions:
  - Cookie attributes: HttpOnly; Secure; SameSite=lax; Path=/auth (§F.7).
    Delegated to _set_refresh_cookie (D-RP2) so cookie shape stays identical
    across sign-in, refresh, and future 2FA-verify.
  - Access token is body-only; refresh token is cookie-only (D-RP5).
  - On the MFA branch we DO NOT set a refresh cookie (§F.2).

Source refs:
  - TECHNICAL_GUIDE §6.2, §10.2; task pack P01-S02-T002 §C, §E, §F.
  - task pack P01-S02-T003 §D-RP2 (shared _set_refresh_cookie).
  - 01-non-negotiables.md §API contract, §Security/Token storage (web).
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidPayloadError,
    SignInRateLimitedError,
)
from app.auth.rate_limit import check_rate_limit_signin
from app.auth.routers._helpers import (
    _error_response,
    _get_client_ip,
    _get_request_id,
    _set_refresh_cookie,
)
from app.auth.schemas import (
    ResponseMeta,
    SignInRequest,
    SignInResponseMfaChallenge,
    SignInResponseSuccess,
)
from app.auth.services import SignInUser
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)


sign_in_router = APIRouter(tags=["auth"])


@sign_in_router.post(
    "/sign-in",
    status_code=status.HTTP_200_OK,
    summary="Authenticate an employee and issue tokens",
    description=(
        "Verifies Argon2id password for a registered employee. "
        "Returns a short-lived JWT access token + HttpOnly refresh token cookie "
        "on success (no MFA), or an mfa_challenge_token when TOTP is enabled. "
        "Implements aggregate-401 (unknown email and wrong password return the "
        "same response body) to prevent user enumeration."
    ),
)
def sign_in(
    body: SignInRequest,
    request: Request,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/auth/sign-in — authenticate employee, issue tokens."""
    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    email_domain = body.email.split("@")[-1] if "@" in body.email else "unknown"

    logger.info(
        "auth.sign_in.received email_domain=%s request_id=%s",
        email_domain, request_id,
    )  # BEFORE

    try:
        check_rate_limit_signin(client_ip)
    except SignInRateLimitedError as exc:
        logger.warning(
            "auth.sign_in.rejected reason=RATE_LIMITED ip=%s request_id=%s",
            client_ip, request_id,
        )
        return _error_response(
            request_id=request_id,
            code=exc.code,
            message=str(exc),
            http_status=exc.http_status,
            headers={"Retry-After": str(exc.retry_after)},
        )

    try:
        result = SignInUser(session=session).execute(
            email=body.email,
            password_plain=body.password,
            request_id=request_id,
            ip=client_ip,
            user_agent=user_agent,
        )
    except InvalidPayloadError as exc:
        return _error_response(request_id, exc.code, str(exc), exc.http_status, field=exc.field)
    except AccountLockedError as exc:
        return _error_response(request_id, exc.code, str(exc), exc.http_status)
    except InvalidCredentialsError as exc:
        return _error_response(request_id, exc.code, str(exc), exc.http_status)
    except Exception:
        logger.error("auth.sign_in.error request_id=%s", request_id, exc_info=True)
        return _error_response(
            request_id=request_id,
            code="AUTH_SIGNIN_INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ----------------- Response: MFA branch vs no-MFA branch ----------------
    if result.mfa_required:
        envelope = SignInResponseMfaChallenge(
            data={
                "mfa_required": True,
                "mfa_challenge_token": result.mfa_challenge_token,
                "expires_in": result.expires_in,
            },
            meta=ResponseMeta(request_id=request_id),
        )
        logger.info(
            "auth.sign_in.mfa_challenge_issued user_id=%s request_id=%s",
            str(result.user_id), request_id,
        )  # AFTER mfa branch
        return JSONResponse(
            content=envelope.model_dump(mode="json"),
            status_code=status.HTTP_200_OK,
            headers={"X-Request-ID": request_id},
        )

    # No-MFA success — set refresh cookie + return access token in body
    envelope = SignInResponseSuccess(
        data={
            "mfa_required": False,
            "access_token": result.access_token,
            "token_type": "Bearer",
            "expires_in": result.expires_in,
        },
        meta=ResponseMeta(request_id=request_id),
    )
    logger.info(
        "auth.sign_in.success user_id=%s request_id=%s",
        str(result.user_id), request_id,
    )  # AFTER success

    json_resp = JSONResponse(
        content=envelope.model_dump(mode="json"),
        status_code=status.HTTP_200_OK,
        headers={"X-Request-ID": request_id},
    )
    # D-RP2: use shared _set_refresh_cookie to ensure byte-identical cookie
    # attrs with /refresh and future /2fa/verify (P01-S02-T003).
    # NEVER log raw refresh_token — only user_id is logged above.
    _set_refresh_cookie(json_resp, result.refresh_token)
    return json_resp
