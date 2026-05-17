"""
Hilo People — Admin audit repository (SQLAlchemy queries).

Slice:  P04-S03-T003 — GET /api/v1/admin/audit endpoint
Phase:  P04 Complete Features
Purpose: SQLAlchemy ORM query layer over `audit_logs`. Supports optional
         filters on `created_at`, `actor_user_id`, `action`, and cursor
         pagination over `(created_at DESC, id DESC)`.

Key deps:
  - app.db.models.auth.AuditLog — ORM target
  - sqlalchemy.orm.Session (sync, same as admin/usage.py pattern)

Source refs:
  - task pack P04-S03-T003 §Impact analysis / repository
  - TECHNICAL_GUIDE §10.3 (audit_logs table: indexes on (actor_user_id, created_at)
    and (created_at))
  - 01-non-negotiables.md §Logging, §Database (index-friendly queries)

Decisions:
  - D-REPO-SORT: ORDER BY created_at DESC, id DESC (most-recent first;
    secondary sort on id for stable ordering when created_at ties).
  - D-REPO-CURSOR: opaque base64 over "created_at_iso|id_uuid" (pipe-
    separated). Decoded here; the service encodes the next cursor.
  - D-REPO-LIMIT-PLUS-ONE: fetches limit+1 rows to detect has_more=True
    without a separate COUNT query.
  - D-REPO-FILTER-INDEX: all WHERE clauses use indexed columns only
    (created_at, actor_user_id). `action` filter is not indexed but is
    acceptable for admin-only queries with bounded windows (max 90d).
"""

from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import NamedTuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.models.auth import AuditLog

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


class AuditPage(NamedTuple):
    """Result of a paginated audit query.

    Attributes:
        rows:       Fetched AuditLog ORM instances (up to limit).
        next_cursor: Opaque cursor string for the next page, or None if no more.
        has_more:   True when more rows exist beyond this page.
    """

    rows: list[AuditLog]
    next_cursor: str | None
    has_more: bool


class AuditRepository:
    """Repository for read-only queries on the `audit_logs` table.

    All methods accept an active SQLAlchemy Session (injected by FastAPI).
    No writes are performed here (D-AUDIT-READONLY).

    Refs: task pack P04-S03-T003 §Impact analysis / repository.
    """

    def list_events(
        self,
        session: Session,
        *,
        from_dt: datetime,
        to_dt: datetime,
        actor: uuid.UUID | None = None,
        action: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> AuditPage:
        """Query audit_logs with optional filters and cursor pagination.

        Fetches limit+1 rows to determine has_more without a COUNT query
        (D-REPO-LIMIT-PLUS-ONE). Returns rows sorted created_at DESC, id DESC
        (D-REPO-SORT). Cursor decoding errors are treated as invalid cursor
        and restart from the top of the window (graceful degradation).

        Args:
            session:  SQLAlchemy Session.
            from_dt:  Window start (UTC).
            to_dt:    Window end (UTC).
            actor:    Optional actor_user_id filter.
            action:   Optional action string filter (exact match).
            cursor:   Optional opaque pagination cursor.
            limit:    Page size (1–200).

        Returns:
            AuditPage with rows, next_cursor, has_more.
        """
        if _VERBOSE:
            logger.debug(
                "admin.audit.repository.list.start "
                "from=%s to=%s actor_hash=%s action_truncated=%s cursor_present=%s limit=%d",
                from_dt.isoformat(),
                to_dt.isoformat(),
                _hash_uuid(actor) if actor else None,
                (action[:20] if action else None),
                cursor is not None,
                limit,
            )  # BEFORE

        filters = [
            AuditLog.created_at >= from_dt,
            AuditLog.created_at <= to_dt,
        ]
        if actor is not None:
            filters.append(AuditLog.actor_user_id == actor)
        if action is not None:
            filters.append(AuditLog.action == action)

        # Apply cursor: only return rows older than the cursor position.
        cursor_ts: datetime | None = None
        cursor_id: uuid.UUID | None = None
        if cursor:
            decoded = _decode_cursor(cursor)
            if decoded:
                cursor_ts, cursor_id = decoded
                filters.append(
                    _cursor_filter(cursor_ts, cursor_id)
                )
            else:
                logger.warning(
                    "admin.audit.repository.list.invalid_cursor cursor_len=%d",
                    len(cursor),
                )

        query = (
            session.query(AuditLog)
            .filter(and_(*filters))
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit + 1)
        )

        fetched: list[AuditLog] = query.all()
        has_more = len(fetched) > limit
        rows = fetched[:limit]

        next_cursor: str | None = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = _encode_cursor(last.created_at, last.id)

        if _VERBOSE:
            logger.debug(
                "admin.audit.repository.list.ok count=%d has_more=%s",
                len(rows),
                has_more,
            )  # AFTER

        return AuditPage(rows=rows, next_cursor=next_cursor, has_more=has_more)


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------

def _encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    """Encode a cursor from (created_at, id) using base64 over a pipe-separated string.

    Args:
        created_at: Row's created_at timestamp.
        row_id:     Row's UUID primary key.

    Returns:
        URL-safe base64-encoded cursor string.
    """
    raw = f"{created_at.isoformat()}|{str(row_id)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID] | None:
    """Decode an opaque cursor string to (created_at, id).

    Returns None if the cursor is invalid (malformed base64 or bad format).

    Args:
        cursor: URL-safe base64 cursor string.

    Returns:
        Tuple (created_at, uuid) or None on decode failure.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        parts = raw.split("|", 1)
        if len(parts) != 2:
            return None
        ts_str, id_str = parts
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        row_id = uuid.UUID(id_str)
        return ts, row_id
    except Exception:
        return None


def _cursor_filter(cursor_ts: datetime, cursor_id: uuid.UUID):
    """Build SQLAlchemy filter clause for keyset pagination after (cursor_ts, cursor_id).

    Implements: (created_at < cursor_ts) OR (created_at = cursor_ts AND id < cursor_id)
    which matches ORDER BY created_at DESC, id DESC.

    Args:
        cursor_ts: Cursor created_at timestamp.
        cursor_id: Cursor row id.

    Returns:
        SQLAlchemy filter clause.
    """
    from sqlalchemy import or_
    return or_(
        AuditLog.created_at < cursor_ts,
        and_(
            AuditLog.created_at == cursor_ts,
            AuditLog.id < cursor_id,
        ),
    )


def _hash_uuid(uid: uuid.UUID) -> str:
    """Return a short opaque hash of a UUID for safe logging (no PII).

    Args:
        uid: UUID to hash.

    Returns:
        First 8 hex chars of SHA-256 hash.
    """
    import hashlib
    return hashlib.sha256(str(uid).encode()).hexdigest()[:8]


__all__ = ["AuditRepository", "AuditPage"]
