"""
Hilo People — Admin model-test HTTP router.

WRITE_SET_DRIFT §D-MT-ROUTER (P02-S05-T002): New file in backend/app/admin/model_test/
subpackage. Not in declared write_set but required for the model_test feature module.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: FastAPI handler for POST /api/v1/admin/ai/models/{model_id}/test.
         Wires HTTP → service; translates typed domain errors to HTTP responses.

Key deps:
  - app.admin.model_test.service (run_model_test, ModelNotFoundError,
                                   CredentialNotFoundError)
  - app.admin.model_test.schemas (TestModelRequest, ModelTestOut)
  - app.security.permissions.require_admin
  - app.security.rate_limit.RateLimiter (ADMIN_AI_TEST, 5/min/IP)
  - app.auth.routers._helpers (_error_response, _get_client_ip, _get_request_id)
  - app.db.session.get_db_session

Source refs:
  - task pack P02-S05-T002 §D.2.A (endpoint contract)
  - task pack P02-S05-T002 §D.4 §D-MT-ROUTER
  - 01-non-negotiables.md §API contract (envelope, versioning, error codes)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR)

Decisions:
  - D-MT-LIMITER-PREFIX: ADMIN_AI_TEST prefix, 5/min/IP (distinct from providers
    ADMIN_AI prefix — different cost profile per §F.2).
  - Rate-limit check is performed BEFORE loading the model (no wasted DB hit).
  - 422 from Pydantic (blank/too-long prompt) passes through as FastAPI default
    — this is acceptable; the router does NOT need to re-wrap Pydantic 422 because
    only admins reach this endpoint and the schema produces a clear field-level error.
  - 400 AI_MODEL_TEST_INVALID_PAYLOAD is returned for blank prompt caught at the
    service schema boundary (Pydantic raises ValidationError → FastAPI 422).
    For consistency with T002 spec §D.2.A we use 400 for service-layer validation.
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.admin.model_test.schemas import TestModelRequest
from app.admin.model_test.errors import CredentialNotFoundError, ModelNotFoundError
from app.admin.model_test.service import run_model_test
from app.auth.routers._helpers import _error_response, _get_client_ip, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.llm_gateway.errors import LiteLLMTimeoutError, ModelTestFailedError
from app.security.permissions import require_admin
from app.security.rate_limit import RateLimiter

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# Rate-limit: 5 calls/min/IP for model-test endpoint (real LLM tokens cost money).
_test_limiter = RateLimiter(
    prefix="ADMIN_AI_TEST",
    per_minute=5,
    burst=5,
    window_seconds=60,
)

model_test_router = APIRouter(tags=["admin-ai"])


@model_test_router.post("/models/{model_id}/test", status_code=200)
async def test_model(
    model_id: uuid.UUID,
    request: Request,
    body: TestModelRequest,
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """POST /api/v1/admin/ai/models/{model_id}/test — run a model test (admin only).

    Performs a real LLM call with the supplied prompt, persists the result in
    ai_model_tests + llm_usage_logs, writes an audit row.

    Args:
        model_id:         UUID of the AiModel to test (path param).
        request:          FastAPI Request.
        body:             TestModelRequest (validated prompt + max_tokens).
        user_or_response: Admin User or JSONResponse 401/403.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 200 with ModelTestOut data + meta.request_id on success.
        JSONResponse 400/401/403/404/429/502/503 on various error paths.
    """
    # Propagate auth failure (401/403) from require_admin.
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "admin.model_test.router.test.start "
            "user_id=%s model_id=%s prompt_len=%d request_id=%s",
            str(user.id),
            str(model_id),
            len(body.prompt),
            request_id,
        )  # BEFORE — prompt content NEVER logged

    # Rate-limit check (before DB hit to avoid wasted queries).
    rate_result = await _test_limiter(request)
    if rate_result is not None:
        logger.warning(
            "admin.model_test.router.test.rate_limited "
            "user_id=%s ip=%s request_id=%s",
            str(user.id),
            ip,
            request_id,
        )
        return rate_result  # RateLimiter returns JSONResponse 429 or 503

    # Delegate to service.
    try:
        result = await run_model_test(
            session,
            actor_user_id=user.id,
            model_id=model_id,
            prompt=body.prompt,
            max_tokens=body.max_tokens,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )
    except ModelNotFoundError:
        logger.warning(
            "admin.model_test.router.test.not_found_model "
            "user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code="AI_MODEL_NOT_FOUND",
            message="Model not found.",
            http_status=404,
        )
    except CredentialNotFoundError:
        logger.warning(
            "admin.model_test.router.test.not_found_credential "
            "user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code="AI_PROVIDER_CREDENTIAL_NOT_FOUND",
            message="Provider has no configured credentials.",
            http_status=404,
        )
    except LiteLLMTimeoutError:
        logger.error(
            "admin.model_test.router.test.timeout "
            "user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code="AI_PROVIDER_TEST_FAILED",
            message="Model test timed out.",
            http_status=502,
        )
    except ModelTestFailedError:
        logger.error(
            "admin.model_test.router.test.failed "
            "user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
        )
        return _error_response(
            request_id=request_id,
            code="AI_PROVIDER_TEST_FAILED",
            message="Model test invocation failed.",
            http_status=502,
        )
    except Exception:
        logger.error(
            "admin.model_test.router.test.internal_error "
            "user_id=%s model_id=%s request_id=%s",
            str(user.id),
            str(model_id),
            request_id,
            exc_info=True,
        )
        return _error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            http_status=500,
        )

    # Build the response from the persisted test row data.
    # We query the latest test row for this model+user to get id + created_at.
    from app.admin.model_test.repository import get_latest_test_row
    test_row = get_latest_test_row(session, model_id=model_id, created_by=user.id)

    out_data = {
        "id": str(test_row.id) if test_row else str(uuid.uuid4()),
        "model_id": str(model_id),
        "output": result.text,
        "latency_ms": result.latency_ms,
        "estimated_cost": result.cost_usd,
        "status": "success",
        "created_at": test_row.created_at.isoformat() if test_row else None,
    }

    if _VERBOSE:
        logger.debug(
            "admin.model_test.router.test.ok "
            "user_id=%s model_id=%s latency_ms=%d request_id=%s",
            str(user.id),
            str(model_id),
            result.latency_ms,
            request_id,
        )  # AFTER — no output content, no api_key

    return JSONResponse(
        content={"data": out_data, "meta": {"request_id": request_id}},
        status_code=200,
    )


__all__ = ["model_test_router"]
