"""
Hilo People — Admin audit service (use case: list audit events).

Slice:  P04-S03-T003 — GET /api/v1/admin/audit endpoint
Phase:  P04 Complete Features
Purpose: Orchestrates the list_events use case: validates the time window,
         delegates to AuditRepository, maps ORM rows to AuditLogOut DTOs,
         builds the response envelope.

Key deps:
  - app.admin.audit.repository.AuditRepository
  - app.admin.audit.schemas.AuditLogOut, ListAuditQuery
  - sqlalchemy.orm.Session (sync)

Source refs:
  - task pack P04-S03-T003 §Impact analysis / service
  - 01-non-negotiables.md §Logging, §Error handling

Decisions:
  - D-SVC-WINDOW: `from_dt` + `to_dt` are required; window must be > 0 and
    ≤ _MAX_WINDOW_DAYS (90). Window cap mirrors admin/usage.py precedent.
    Returns {"code": "AUDIT_WINDOW_TOO_WIDE"} error dict if cap exceeded.
    Returns {"code": "AUDIT_WINDOW_INVALID"} if from >= to.
  - D-SVC-UTC: naive datetimes normalised to UTC before DB query.
  - D-SVC-RESPONSE: success returns dict ready for JSONResponse wrapping.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.admin.audit.repository import AuditRepository
from app.admin.audit.schemas import AuditLogOut, ListAuditQuery

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_MAX_WINDOW_DAYS = 90


class AuditService:
    """Use case: list audit events with filters and cursor pagination.

    Stateless; instantiated per-request or as a singleton (no internal state).

    Refs: task pack P04-S03-T003 §Impact analysis / service.
    """

    def __init__(self) -> None:
        """Initialize AuditService with an AuditRepository instance."""
        self._repo = AuditRepository()

    def list_events(
        self,
        *,
        session: Session,
        query: ListAuditQuery,
        actor_user_id: uuid.UUID,
        request_id: str,
    ) -> dict[str, Any]:
        """Execute the list-audit-events use case.

        Validates the time window, queries the repository, and maps rows to
        AuditLogOut DTOs. Returns a ready-to-serialise dict.

        Args:
            session:       Active SQLAlchemy Session.
            query:         Validated query parameters.
            actor_user_id: UUID of the authenticated auditor (for logging).
            request_id:    X-Request-ID for correlation.

        Returns:
            Dict with keys `data` (list[dict]) and `meta` (dict), or
            with key `error` (dict) on validation failure.
        """
        if _VERBOSE:
            logger.debug(
                "admin.audit.service.list_events.start "
                "actor_user_id_hash=%s request_id=%s",
                _short_hash(str(actor_user_id)),
                request_id,
            )  # BEFORE

        from_utc = _to_utc(query.from_dt)
        to_utc = _to_utc(query.to_dt)

        if from_utc >= to_utc:
            logger.warning(
                "admin.audit.service.list_events.invalid_window "
                "from=%s to=%s request_id=%s",
                from_utc.isoformat(),
                to_utc.isoformat(),
                request_id,
            )
            return {
                "error": {
                    "code": "AUDIT_WINDOW_INVALID",
                    "message": "'from' must be earlier than 'to'.",
                    "http_status": 422,
                }
            }

        window_days = (to_utc - from_utc).total_seconds() / 86400
        if window_days > _MAX_WINDOW_DAYS:
            logger.warning(
                "admin.audit.service.list_events.window_too_wide "
                "days=%.1f max=%d request_id=%s",
                window_days,
                _MAX_WINDOW_DAYS,
                request_id,
            )
            return {
                "error": {
                    "code": "AUDIT_WINDOW_TOO_WIDE",
                    "message": f"Window exceeds {_MAX_WINDOW_DAYS} days maximum.",
                    "http_status": 422,
                }
            }

        try:
            page = self._repo.list_events(
                session,
                from_dt=from_utc,
                to_dt=to_utc,
                actor=query.actor,
                action=query.action,
                cursor=query.cursor,
                limit=query.limit,
            )
        except Exception as exc:
            logger.error(
                "admin.audit.service.list_events.error "
                "actor_user_id_hash=%s request_id=%s error=%s",
                _short_hash(str(actor_user_id)),
                request_id,
                type(exc).__name__,
                exc_info=True,
            )
            return {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Failed to query audit events.",
                    "http_status": 500,
                }
            }

        items = [AuditLogOut.from_orm_row(row).model_dump(mode="json") for row in page.rows]

        if _VERBOSE:
            logger.debug(
                "admin.audit.service.list_events.ok "
                "actor_user_id_hash=%s count=%d has_more=%s request_id=%s",
                _short_hash(str(actor_user_id)),
                len(items),
                page.has_more,
                request_id,
            )  # AFTER
        else:
            logger.info(
                "admin.audit.service.list_events.ok count=%d has_more=%s",
                len(items),
                page.has_more,
            )

        return {
            "data": items,
            "meta": {
                "request_id": request_id,
                "next_cursor": page.next_cursor,
                "has_more": page.has_more,
                "count": len(items),
            },
        }


def _to_utc(dt: datetime) -> datetime:
    """Normalize datetime to UTC; naive datetimes assumed UTC.

    Args:
        dt: Input datetime (tz-aware or naive).

    Returns:
        Timezone-aware UTC datetime.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _short_hash(value: str) -> str:
    """Return 8-char SHA-256 prefix for safe opaque logging.

    Args:
        value: String to hash.

    Returns:
        First 8 hex characters of SHA-256 digest.
    """
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()[:8]


__all__ = ["AuditService"]
