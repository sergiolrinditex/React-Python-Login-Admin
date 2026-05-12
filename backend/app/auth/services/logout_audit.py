"""
Hilo People — Logout-flow audit writer (D-S2 pattern) and miss classifier.

Slice:  P01-S02-T004 — POST /api/v1/auth/logout
Phase:  P01 Auth + Data Foundation
Responsibility:
  - Encapsulate the D-S2 pattern (write the failure audit on an independent
    short session so it persists even when the main logout transaction is
    rolled back, e.g. on user_mismatch path).
  - Provide classify_logout_miss helper that maps an arbitrary refresh_tokens
    row (any state) to the failure reason string for the audit metadata.
    Returned reasons stay in sync with the aggregate-401 contract: callers
    still raise the same SessionExpiredError; the reason lives only in
    audit_logs.metadata.

Decisions:
  - D-S2: failure audit must be committed independently from the main session
    so audit row survives the caller's rollback.
  - Public AuthRepository import at module level (no lazy imports — validator
    F2 lesson from T003: noqa:PLC0415 on leaf modules is an anti-pattern).
  - Public audit_session_scope() context manager used instead of private
    _SessionLocal factory (validator F3 lesson from T003).
  - Mirrors RefreshAuditWriter in services/refresh_audit.py — same shape.

Source refs:
  - task pack P01-S02-T004 §Audit row contract, §D-S2, failure audit pattern.
  - 01-non-negotiables.md §Security/Audit log (GDPR Art. 30) + §File size.
  - validator review of P01-S02-T003 cycle 1 — F1/F2/F3/F4 (lessons learned).
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.auth.repository import AuthRepository
from app.db.session import audit_session_scope

logger = logging.getLogger(__name__)


def classify_logout_miss(row: object | None) -> str:
    """Determine why find_active_by_hash_for_update returned None for logout.

    Args:
        row: Result of find_by_hash (any-state lookup). None = unknown hash.

    Returns:
        reason string: "unknown_hash" | "revoked" | "expired"
    """
    if row is None:
        return "unknown_hash"
    if getattr(row, "revoked_at", None) is not None:
        return "revoked"
    return "expired"


class LogoutAuditWriter:
    """Audit writer for the /auth/logout use case.

    Encapsulates BOTH halves of the audit contract:
      - write_success: append-to-main-tx audit (caller commits).
      - write_failure: D-S2 independent session that commits the failure
        audit row even if the main logout transaction rolls back.

    Extracted from services/logout.py so the use case file stays under the
    ~300-LOC hard cap (mirrors T003 RefreshAuditWriter split, validator F1).
    """

    def __init__(self, main_session) -> None:
        """
        Args:
            main_session: The use case's main SQLAlchemy Session — used only
                for success audits that share the revocation transaction.
        """
        self._main_session = main_session
        self._main_repo = AuthRepository(main_session)

    def write_success(
        self,
        *,
        request_id: str,
        ip: str,
        user_agent: str,
        user_id: uuid.UUID,
        token_id: uuid.UUID,
    ) -> None:
        """Insert a success audit_log row on the main session (caller commits).

        Args:
            request_id: X-Request-ID correlation.
            ip: Client IP address.
            user_agent: Client User-Agent.
            user_id: UUID of the user who logged out.
            token_id: UUID of the revoked refresh_tokens row.
        """
        logger.debug(
            "auth.logout.success_audit.start user_id=%s request_id=%s",
            str(user_id),
            request_id,
        )  # BEFORE
        self._main_repo.write_audit(
            action="auth.logout",
            entity_type="user",
            entity_id=user_id,
            actor_user_id=user_id,
            metadata={
                "request_id": request_id,
                "ip": ip,
                "user_agent": user_agent[:255],
                "outcome": "success",
                "revoked_token_id": str(token_id),
            },
        )
        logger.debug(
            "auth.logout.success_audit.done user_id=%s request_id=%s",
            str(user_id),
            request_id,
        )  # AFTER

    def write_failure(
        self,
        *,
        request_id: str,
        ip: str,
        user_agent: str,
        reason: str,
        actor_user_id: Optional[uuid.UUID],
    ) -> None:
        """Insert a failure audit_log row on an independent short session (D-S2).

        Commits independently so the audit row persists even if the main
        logout transaction is rolled back (user_mismatch path).

        Args:
            request_id: X-Request-ID correlation.
            ip: Client IP address.
            user_agent: Client User-Agent.
            reason: Failure reason: no_bearer|invalid_bearer|expired_bearer|
                    no_cookie|unknown_hash|expired|revoked|user_mismatch.
            actor_user_id: UUID of the affected user (None if not determinable).
        """
        logger.debug(
            "auth.logout.failure_audit.start reason=%s request_id=%s",
            reason,
            request_id,
        )  # BEFORE
        with audit_session_scope() as short_session:
            try:
                short_repo = AuthRepository(short_session)
                short_repo.write_audit(
                    action="auth.logout",
                    entity_type="user",
                    entity_id=actor_user_id,
                    actor_user_id=actor_user_id,
                    metadata={
                        "request_id": request_id,
                        "ip": ip,
                        "user_agent": user_agent[:255],
                        "outcome": "failure",
                        "reason": reason,
                    },
                )
                short_session.commit()
                logger.debug(
                    "auth.logout.failure_audit.done reason=%s request_id=%s",
                    reason,
                    request_id,
                )  # AFTER
            except Exception:
                # boundary: audit best-effort. We never let an audit failure
                # mask the main transaction outcome or change the 401 envelope
                # (mirrors T003 validator F4 — generic except is acceptable
                # here per 01-non-negotiables.md §Error handling top-level boundary).
                short_session.rollback()
                logger.error(
                    "auth.logout.failure_audit.error reason=%s request_id=%s",
                    reason,
                    request_id,
                    exc_info=True,
                )  # ERROR
