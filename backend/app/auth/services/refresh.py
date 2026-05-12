"""
Hilo People — RefreshTokenUser use case (token rotation service).

Slice:  P01-S02-T003 — POST /api/v1/auth/refresh
        Debugger cycle 1: extracted audit helpers + classifier to
        services/refresh_audit.py to respect the ~200-LOC use-case target
        (validator F1). Removed lazy AuthRepository imports (F2) and the
        private _SessionLocal factory import (F3); the D-S2 short session
        now goes through app.db.session.audit_session_scope (public surface).
Phase:  P01 Auth + Data Foundation
Responsibility: Orchestrate one POST /auth/refresh request:
  1. Validate opaque refresh cookie (present, hash found, active, not expired).
  2. Acquire row-level lock (FOR UPDATE) to serialize concurrent calls.
  3. Atomically revoke the old token + insert the new token + verify user active.
  4. Encode a new access JWT.
  5. Write audit log (success or failure with reason) — delegated to
     RefreshAuditWriter in services/refresh_audit.py.
  Returns RefreshResult on success, raises SessionExpiredError on any failure.

Decisions:
  - D-RP3: SELECT ... FOR UPDATE serializes concurrent rotations; the loser
    sees revoked_at NOT NULL after unblocking and returns 401.
  - D-RP4: No token-family revocation (schema has no replaced_by column);
    just rotate-and-revoke per use.
  - D-S2: Failure audit committed via RefreshAuditWriter on its own short
    session (audit_session_scope) so it persists even when the main tx
    rolls back.
  - Module-level imports only — no lazy imports, no private cross-module
    symbols (validator F2/F3).

Source refs:
  - TECHNICAL_GUIDE §6.2 POST /api/v1/auth/refresh; §10.2 JWT claims; §10.3 DB
  - task pack P01-S02-T003 §D-RP3, §D-RP4, §D.3, §D.4, §F.1..F.14
  - 01-non-negotiables.md §File size, §Security/Audit log, §Logging
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.errors import SessionExpiredError
from app.auth.repositories.refresh import RefreshTokenRepository
from app.auth.services.refresh_audit import (
    RefreshAuditWriter,
    classify_failure_reason,
)
from app.auth.tokens import encode_access_token

logger = logging.getLogger(__name__)

_REFRESH_TTL: int = int(os.getenv("AUTH_REFRESH_TTL_SECONDS", "2592000"))
_ACCESS_TTL: int = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "1800"))


@dataclass(frozen=True)
class RefreshResult:
    """Output of a successful token rotation.

    Attributes:
        access_token: New short-lived JWT (HS256).
        new_refresh_token: New opaque refresh token string (raw, for cookie).
        expires_in: Access token TTL in seconds.
        old_token_id: UUID of the revoked refresh_tokens row (for audit).
        new_token_id: UUID of the new refresh_tokens row (for audit).
        user_id: UUID of the authenticated user.
    """

    access_token: str
    new_refresh_token: str
    expires_in: int
    old_token_id: uuid.UUID
    new_token_id: uuid.UUID
    user_id: uuid.UUID


class RefreshTokenUser:
    """Use case: rotate a refresh token and issue a new access JWT.

    Business rule (instrucciones.md §3.1): "refresh tokens se guardan
    hasheados y rotan" — each call invalidates the old token, creates a new
    one, and returns a new access token.

    Raises:
        SessionExpiredError: For any failure (missing, unknown, expired,
            revoked, user inactive). The 401 body is byte-identical for all
            cases (aggregate anti-enumeration). Audit row carries the reason.

    Args:
        session: Active SQLAlchemy Session (main transaction).
    """

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: SQLAlchemy sync Session for the main transaction.
        """
        self._session = session
        self._repo = RefreshTokenRepository(session)
        self._audit = RefreshAuditWriter(session)

    def execute(
        self,
        raw_cookie: str | None,
        request_id: str,
        ip: str,
        user_agent: str,
    ) -> RefreshResult:
        """Rotate a refresh token and return a new access token.

        Args:
            raw_cookie: Raw opaque refresh token from the HttpOnly cookie.
                        May be None if the cookie was absent.
            request_id: X-Request-ID correlation string.
            ip: Client IP address.
            user_agent: Client User-Agent string.

        Returns:
            RefreshResult with new access_token, new_refresh_token, metadata.

        Raises:
            SessionExpiredError: Token absent / unknown / expired / revoked
                / user inactive. Byte-identical 401 for all reasons.
        """
        logger.debug(
            "auth.refresh.execute.start request_id=%s ip=%s",
            request_id,
            ip,
        )  # BEFORE

        if not raw_cookie:
            logger.debug(
                "auth.refresh.rejected reason=no_cookie request_id=%s",
                request_id,
            )
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="no_cookie",
                actor_user_id=None,
            )
            raise SessionExpiredError()

        token_hash = hashlib.sha256(raw_cookie.encode()).hexdigest()
        return self._rotate(
            token_hash=token_hash,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )

    def _rotate(
        self,
        token_hash: str,
        request_id: str,
        ip: str,
        user_agent: str,
    ) -> RefreshResult:
        """Perform the atomic rotation: find → lock → verify → revoke → insert → commit.

        Args:
            token_hash: SHA-256 hex of the raw refresh cookie value.
            request_id: X-Request-ID correlation.
            ip: Client IP.
            user_agent: Client User-Agent.

        Returns:
            RefreshResult on success.

        Raises:
            SessionExpiredError: On any failure reason.
        """
        # --- Find the active token row WITH a row-level lock (D-RP3) --------
        old_row = self._repo.find_active_by_hash_for_update(token_hash)

        if old_row is None:
            # Distinguish expired/revoked from unknown for audit detail.
            any_row = self._repo.find_by_hash(token_hash)
            reason, actor_uid = classify_failure_reason(any_row)
            logger.debug(
                "auth.refresh.rejected reason=%s request_id=%s",
                reason,
                request_id,
            )
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason=reason,
                actor_user_id=actor_uid,
            )
            raise SessionExpiredError()

        # --- Verify user is still active ------------------------------------
        user = self._repo.find_user_active(old_row.user_id)
        if user is None:
            logger.debug(
                "auth.refresh.rejected reason=user_inactive user_id=%s request_id=%s",
                str(old_row.user_id),
                request_id,
            )
            self._session.rollback()  # no rotation visible
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="user_inactive",
                actor_user_id=old_row.user_id,
            )
            raise SessionExpiredError()

        # --- Atomic rotation: revoke old, insert new -----------------------
        old_id = old_row.id
        self._repo.revoke(old_id)

        new_opaque = secrets.token_urlsafe(48)
        new_hash = hashlib.sha256(new_opaque.encode()).hexdigest()
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=_REFRESH_TTL)
        new_row = self._repo.insert_new(
            user_id=old_row.user_id,
            token_hash=new_hash,
            expires_at=expires_at,
        )

        # --- Encode new access JWT -----------------------------------------
        access_token = encode_access_token(user, ttl=_ACCESS_TTL)

        # --- Write success audit + commit (same tx) -------------------------
        self._audit.write_success(
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            user_id=old_row.user_id,
            old_token_id=old_id,
            new_token_id=new_row.id,
        )
        self._session.commit()

        logger.debug(
            "auth.refresh.execute.done user_id=%s old_token_id=%s new_token_id=%s "
            "request_id=%s",
            str(old_row.user_id),
            str(old_id),
            str(new_row.id),
            request_id,
        )  # AFTER

        return RefreshResult(
            access_token=access_token,
            new_refresh_token=new_opaque,
            expires_in=_ACCESS_TTL,
            old_token_id=old_id,
            new_token_id=new_row.id,
            user_id=old_row.user_id,
        )
