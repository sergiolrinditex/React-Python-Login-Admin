"""
Hilo People — Admin usage aggregation HTTP endpoint.

WRITE_SET_DRIFT §D-USAGE-FILE (P02-S05-T002): IN declared write_set.
WRITE_SET_DRIFT §D-USAGE-SPLIT (P02-S05-T002): File exceeded 300 LoC;
  aggregation SQL extracted to admin/_usage_aggregator.py.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: GET /api/v1/admin/usage — aggregated LLM usage summary over
         llm_usage_logs, grouped by model, day, or model+day.
         Read-only; no audit row (consistent with T001 GET endpoints).

Key deps:
  - app.admin._usage_aggregator.aggregate_usage — SQL query
  - app.db.session.get_db_session
  - app.security.permissions.require_admin
  - app.auth.routers._helpers (_error_response, _get_request_id)

Source refs:
  - task pack P02-S05-T002 §D.2.B, §D.4 §D-USAGE-FILE, §D-USAGE-SPLIT
  - 01-non-negotiables.md §API contract, §Logging

Decisions:
  - D-USAGE-WINDOW-DEFAULT: from + to are REQUIRED; 422 if missing.
  - D-USAGE-GROUPBY-DEFAULT: default group_by='model'.
  - R-USAGE-WINDOW: window must be ≤90 days; 422 ADMIN_USAGE_WINDOW_TOO_WIDE.
  - No audit row for GET /admin/usage (consistent with T001 GETs).
  - No rate limit (read-only admin, consistent with T001 GET).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.admin._usage_aggregator import aggregate_usage
from app.auth.routers._helpers import _error_response, _get_request_id
from app.db.models.user import User
from app.db.session import get_db_session
from app.security.permissions import require_admin

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_MAX_WINDOW_DAYS = 90
_VALID_GROUP_BY = {"model", "day", "model_day"}

usage_router = APIRouter(tags=["admin-usage"])


@usage_router.get("/usage", status_code=200)
async def get_usage(
    request: Request,
    from_dt: datetime = Query(..., alias="from", description="Start datetime (ISO 8601)"),
    to_dt: datetime = Query(..., alias="to", description="End datetime (ISO 8601)"),
    group_by: str = Query(default="model", description="'model' | 'day' | 'model_day'"),
    model_id: uuid.UUID | None = Query(default=None, description="Optional model UUID filter"),
    provider_id: uuid.UUID | None = Query(default=None, description="Optional provider UUID filter"),
    user_or_response: User | JSONResponse = Depends(require_admin),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """GET /api/v1/admin/usage — admin LLM usage summary (admin only, read-only).

    Args:
        request:          FastAPI Request.
        from_dt:          Window start (required, ISO 8601).
        to_dt:            Window end (required, ISO 8601).
        group_by:         Grouping ('model' | 'day' | 'model_day').
        model_id:         Optional model UUID filter.
        provider_id:      Optional provider UUID filter.
        user_or_response: Admin User or JSONResponse 401/403.
        session:          SQLAlchemy Session.

    Returns:
        JSONResponse 200 with aggregated usage data + meta.
        JSONResponse 422 for invalid params or window >90 days.
        JSONResponse 401/403 for auth failures.
    """
    if isinstance(user_or_response, JSONResponse):
        return user_or_response

    request_id = _get_request_id(request)
    user: User = user_or_response

    if _VERBOSE:
        logger.debug(
            "admin.usage.list.start user_id=%s from=%s to=%s group_by=%s request_id=%s",
            str(user.id), from_dt.isoformat(), to_dt.isoformat(), group_by, request_id,
        )  # BEFORE

    if group_by not in _VALID_GROUP_BY:
        return _error_response(
            request_id=request_id,
            code="ADMIN_USAGE_INVALID_PAYLOAD",
            message=f"Invalid group_by '{group_by}'. Must be: model, day, model_day.",
            http_status=422,
        )

    from_utc = _to_utc(from_dt)
    to_utc = _to_utc(to_dt)

    if from_utc >= to_utc:
        return _error_response(
            request_id=request_id,
            code="ADMIN_USAGE_INVALID_PAYLOAD",
            message="'from' must be earlier than 'to'.",
            http_status=422,
        )

    if (to_utc - from_utc).days > _MAX_WINDOW_DAYS:
        return _error_response(
            request_id=request_id,
            code="ADMIN_USAGE_WINDOW_TOO_WIDE",
            message=f"Window exceeds {_MAX_WINDOW_DAYS} days maximum.",
            http_status=422,
        )

    try:
        rows, totals = aggregate_usage(
            session,
            from_utc=from_utc,
            to_utc=to_utc,
            group_by=group_by,
            model_id=model_id,
            provider_id=provider_id,
        )
    except Exception as exc:
        logger.error(
            "admin.usage.list.error user_id=%s request_id=%s error=%s",
            str(user.id), request_id, type(exc).__name__, exc_info=True,
        )
        return _error_response(
            request_id=request_id,
            code="INTERNAL_ERROR",
            message="Failed to compute usage summary.",
            http_status=500,
        )

    data: dict[str, Any] = {
        "from": from_utc.isoformat(),
        "to": to_utc.isoformat(),
        "group_by": group_by,
        "rows": rows,
        "totals": totals,
    }

    if _VERBOSE:
        logger.debug(
            "admin.usage.list.ok user_id=%s rows=%d invocations=%d request_id=%s",
            str(user.id), len(rows), totals.get("invocations", 0), request_id,
        )  # AFTER
    else:
        logger.info(
            "admin.usage.list.ok user_id=%s rows=%d invocations=%d",
            str(user.id), len(rows), totals.get("invocations", 0),
        )

    return JSONResponse(
        content={"data": data, "meta": {"request_id": request_id}},
        status_code=200,
    )


def _to_utc(dt: datetime) -> datetime:
    """Normalize datetime to UTC. Naive datetimes assumed UTC.

    Args:
        dt: Input datetime (tz-aware or naive).

    Returns:
        Timezone-aware UTC datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


__all__ = ["usage_router"]
