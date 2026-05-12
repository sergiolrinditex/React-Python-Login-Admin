"""
Hilo People — Refresh-flow audit writer (D-S2 pattern) and miss classifier.

Slice:  P01-S02-T003 — debugger cycle 1 (extracted from services/refresh.py to
        respect the use-case ~200-LOC target; see validator F1 in handoff
        P01-S02-T003.md).
Phase:  P01 Auth + Data Foundation
Responsibility:
  - Encapsulate the D-S2 pattern (write the failure audit on an independent
    short session so it persists even when the main rotation transaction is
    rolled back, e.g. on user_inactive path).
  - Provide the `classify_failure_reason` helper that maps an arbitrary
    refresh_tokens row (any state) to (reason, actor_user_id) for the audit
    metadata. Returned reasons stay in sync with the aggregate-401 contract:
    callers still raise the same SessionExpiredError; the reason lives only
    in audit_logs.metadata.

Decisions:
  - D-S2: failure audit must be committed independently from the main session
    so audit row survives the caller's rollback.
  - Public AuthRepository import at module level (no lazy imports — validator
    F2 ruled there is no circular dep, since sign_up.py / sign_in.py already
    import it at module level).
  - Public `audit_session_scope()` context manager from app.db.session is used
    instead of the private `_SessionLocal` factory (validator F3 — public
    surface for cross-module session creation).

Source refs:
  - task pack P01-S02-T003 §D.4 audit rows; §D-RP3 D-S2 separate-session.
  - 01-non-negotiables.md §Security/Audit log (GDPR Art. 30) + §File size.
  - validator review of P01-S02-T003 cycle 1 — F1/F2/F3/F4.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.auth.repository import AuthRepository
from app.db.session import audit_session_scope

logger = logging.getLogger(__name__)


def classify_failure_reason(
    row: object | None,
) -> tuple[str, Optional[uuid.UUID]]:
    """Determine why find_active_by_hash_for_update returned None.

    Args:
        row: Result of find_by_hash (any-state lookup). None = unknown hash.

    Returns:
        Tuple (reason, actor_user_id) for the failure audit row.
        - reason: "unknown_hash" | "revoked" | "expired"
        - actor_user_id: UUID of the affected user, or None for unknown hashes.
    """
    if row is None:
        return "unknown_hash", None
    # Row exists but was filtered by revoked_at IS NULL / expires_at > now().
    if getattr(row, "revoked_at", None) is not None:
        return "revoked", getattr(row, "user_id", None)
    return "expired", getattr(row, "user_id", None)


class RefreshAuditWriter:
    """Audit writer for the /auth/refresh use case.

    Encapsulates BOTH halves of the audit contract:
      - `write_success`: append-to-main-tx audit (caller commits).
      - `write_failure`: D-S2 independent session that commits the failure
        audit row even if the main rotation transaction rolls back.

    Per validator F1 (P01-S02-T003 cycle 1) this is extracted so
    services/refresh.py stays at or below the use-case ~200-LOC target.
    """

    def __init__(self, main_session) -> None:
        """
        Args:
            main_session: The use case's main SQLAlchemy Session — used only
                for success audits that share the rotation transaction.
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
        old_token_id: uuid.UUID,
        new_token_id: uuid.UUID,
    ) -> None:
        """Insert a success audit_log row on the main session (caller commits).

        Args:
            request_id: X-Request-ID correlation.
            ip: Client IP address.
            user_agent: Client User-Agent.
            user_id: UUID of the user whose session was refreshed.
            old_token_id: UUID of the revoked refresh_tokens row.
            new_token_id: UUID of the new refresh_tokens row.
        """
        logger.debug(
            "auth.refresh.success_audit.start user_id=%s request_id=%s",
            str(user_id),
            request_id,
        )  # BEFORE
        self._main_repo.write_audit(
            action="auth.refresh",
            entity_type="user",
            entity_id=user_id,
            actor_user_id=user_id,
            metadata={
                "request_id": request_id,
                "ip": ip,
                "user_agent": user_agent,
                "outcome": "success",
                "old_token_id": str(old_token_id),
                "new_token_id": str(new_token_id),
            },
        )
        logger.debug(
            "auth.refresh.success_audit.done user_id=%s request_id=%s",
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
        rotation transaction is rolled back (user_inactive path).

        Args:
            request_id: X-Request-ID correlation.
            ip: Client IP address.
            user_agent: Client User-Agent.
            reason: Failure reason: no_cookie|unknown_hash|expired|revoked|user_inactive.
            actor_user_id: UUID of the affected user (None if hash unknown).
        """
        logger.debug(
            "auth.refresh.failure_audit.start reason=%s request_id=%s",
            reason,
            request_id,
        )  # BEFORE
        with audit_session_scope() as short_session:
            try:
                short_repo = AuthRepository(short_session)
                short_repo.write_audit(
                    action="auth.refresh",
                    entity_type="user",
                    entity_id=actor_user_id,
                    actor_user_id=actor_user_id,
                    metadata={
                        "request_id": request_id,
                        "ip": ip,
                        "user_agent": user_agent,
                        "outcome": "failure",
                        "reason": reason,
                    },
                )
                short_session.commit()
                logger.debug(
                    "auth.refresh.failure_audit.done reason=%s request_id=%s",
                    reason,
                    request_id,
                )  # AFTER
            except Exception:
                # boundary: audit best-effort. We never let an audit failure
                # mask the main transaction outcome or change the 401 envelope
                # (validator F4 — generic except is acceptable here per
                # 01-non-negotiables.md §Error handling top-level boundary).
                short_session.rollback()
                logger.error(
                    "auth.refresh.failure_audit.error reason=%s request_id=%s",
                    reason,
                    request_id,
                    exc_info=True,
                )  # ERROR
