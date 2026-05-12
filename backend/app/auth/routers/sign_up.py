"""
Hilo People — POST /api/v1/auth/sign-up router.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
        (Extracted from `app/auth/router.py` in P01-S02-T002 debugger cycle 1
        per validator F1 "file size hard cap"; F5 "use Depends(get_db_session)
        instead of `_SessionLocal()`".)
Phase:  P01 Auth + Data Foundation
Responsibility: parse SignUpRequest, rate-limit, dispatch to SignUpUser,
                map domain errors to the envelope, return 201 envelope.

Source refs:
  - TECHNICAL_GUIDE §6.2; task pack P01-S02-T001 §C, §F.
  - 01-non-negotiables.md §API contract, §Security.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.errors import (
    EmailAlreadyExistsError,
    LegalNotAcceptedError,
    NonCorporateEmailError,
    PasswordPolicyError,
    RateLimitExceededError,
)
from app.auth.rate_limit import check_rate_limit
from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.auth.schemas import (
    ResponseMeta,
    SignUpData,
    SignUpRequest,
    SignUpResponse,
)
from app.auth.services import SignUpUser
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)


sign_up_router = APIRouter(tags=["auth"])


@sign_up_router.post(
    "/sign-up",
    status_code=status.HTTP_201_CREATED,
    response_model=SignUpResponse,
    summary="Register a new employee account",
    description=(
        "Creates a new user account for a corporate employee. "
        "Validates corporate email domain, password policy and legal acceptance. "
        "No JWT is issued — the client must sign in after registration."
    ),
)
def sign_up(
    body: SignUpRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/auth/sign-up — register a new employee account."""
    request_id = _get_request_id(request)
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    email_domain = body.email.split("@")[-1] if "@" in body.email else "unknown"

    logger.info(
        "auth.sign_up.received email_domain=%s request_id=%s",
        email_domain, request_id,
    )  # BEFORE

    try:
        check_rate_limit(client_ip)
    except RateLimitExceededError as exc:
        logger.warning(
            "auth.sign_up.rejected reason=RATE_LIMITED ip=%s request_id=%s",
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
        result = SignUpUser(session=session).execute(
            email=body.email,
            password_plain=body.password,
            full_name=body.full_name,
            legal_acceptance=body.legal_acceptance,
            request_id=request_id,
            ip=client_ip,
            user_agent=user_agent,
        )
    except LegalNotAcceptedError as exc:
        return _error_response(request_id, exc.code, str(exc), exc.http_status, field="legal_acceptance")
    except NonCorporateEmailError as exc:
        return _error_response(request_id, exc.code, str(exc), exc.http_status, field="email")
    except PasswordPolicyError as exc:
        return _error_response(request_id, exc.code, str(exc), exc.http_status, field="password")
    except EmailAlreadyExistsError as exc:
        return _error_response(request_id, exc.code, str(exc), exc.http_status)
    except Exception:
        logger.error("auth.sign_up.error request_id=%s", request_id, exc_info=True)
        return _error_response(
            request_id=request_id,
            code="AUTH_SIGNUP_INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again.",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    envelope = SignUpResponse(
        data=SignUpData(user_id=result.user_id, mfa_required=result.mfa_required),
        meta=ResponseMeta(request_id=request_id),
    )
    logger.info(
        "auth.sign_up.response_sent user_id=%s request_id=%s",
        str(result.user_id), request_id,
    )  # AFTER
    return JSONResponse(
        content=envelope.model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
        headers={"X-Request-ID": request_id},
    )
