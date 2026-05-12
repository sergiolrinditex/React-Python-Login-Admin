"""
Hilo People — LogoutUser use case (single-session revocation service).

Slice:  P01-S02-T004 — POST /api/v1/auth/logout
Phase:  P01 Auth + Data Foundation
Responsibility: Orchestrate one POST /auth/logout request:
  1. Validate Bearer access token (present, signature valid, not expired).
  2. Validate refresh cookie (present, hash found and active, not expired).
  3. Assert Bearer.sub == refresh_token.user_id (user-mismatch check — D2).
  4. Revoke the matching refresh_tokens row (single-session — D3).
  5. Write audit log (success or failure) — delegated to LogoutAuditWriter
     in services/logout_audit.py (extracted per non-negotiables file-size rule).
  Returns None on success, raises SessionExpiredError on any failure.

Decisions:
  - D1: Idempotency is 401 — a second logout with a revoked cookie always
    returns 401 AUTH_SESSION_EXPIRED. Backend is truthful; no valid session → 401.
  - D2: Both Bearer AND refresh cookie required. Bearer identifies the user
    (sub), cookie identifies the specific session. Mismatch → 401 + reason
    user_mismatch in audit.
  - D3: Single-session revocation only — revoke ONLY the row whose hash
    matches the cookie. Other active rows for the same user are untouched.
  - D-S2 (logout): Failure audit committed via an independent short session
    (audit_session_scope) so it persists even when the main tx rolls back.
    Delegated to LogoutAuditWriter.write_failure (mirrors T003 pattern).
  - Module-level imports only — no lazy imports (validator F2 lesson from T003).
  - classify_logout_miss + LogoutAuditWriter extracted to logout_audit.py
    (same split as RefreshTokenUser + RefreshAuditWriter in T003; satisfies
    non-negotiables §File size use-case ~200-LOC target).

Source refs:
  - TECHNICAL_GUIDE §6.2 POST /api/v1/auth/logout; §10.2 JWT claims; §10.3 DB
  - task pack P01-S02-T004 §D1, §D2, §D3, §D-S2, §Audit row contract
  - 01-non-negotiables.md §Security/Audit log, §Logging, §File size
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Optional

import jwt
from sqlalchemy.orm import Session

from app.auth.errors import SessionExpiredError
from app.auth.repositories.refresh import RefreshTokenRepository
from app.auth.services.logout_audit import LogoutAuditWriter, classify_logout_miss
from app.auth.tokens import decode_token

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)


class LogoutUser:
    """Use case: revoke a single refresh token session (logout).

    Business rule (instrucciones.md §3.1):
      - "todo logout queda auditado" — audit row is mandatory for ALL paths.
      - "refresh tokens se guardan hasheados" — revocation sets revoked_at,
        never deletes.

    Raises:
        SessionExpiredError: For any failure (missing/invalid Bearer, missing/
            unknown/expired/revoked cookie, or user_mismatch). Byte-identical
            401 body for all reasons; reason only in audit_logs.metadata.

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
        self._audit = LogoutAuditWriter(session)

    def execute(
        self,
        access_bearer: Optional[str],
        raw_cookie: Optional[str],
        request_id: str,
        ip: str,
        user_agent: str,
    ) -> None:
        """Revoke the refresh token identified by the cookie and clear the session.

        Args:
            access_bearer: Raw Bearer access token from Authorization header.
                           May be None if the header is absent.
            raw_cookie: Raw opaque refresh token from the HttpOnly cookie.
                        May be None if the cookie is absent.
            request_id: X-Request-ID correlation string.
            ip: Client IP address.
            user_agent: Client User-Agent string.

        Raises:
            SessionExpiredError: For any validation failure. Byte-identical
                401 body for all reasons; reason only in audit_logs.metadata.
        """
        logger.debug(
            "auth.logout.execute.start request_id=%s ip=%s",
            request_id,
            ip,
        )  # BEFORE

        # --- Step 1: Validate Bearer access token --------------------------------
        bearer_user_id_str = self._validate_bearer(
            access_bearer=access_bearer,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
        )

        # --- Step 2: Validate refresh cookie ------------------------------------
        if not raw_cookie:
            logger.debug(
                "auth.logout.rejected reason=no_cookie request_id=%s",
                request_id,
            )
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="no_cookie",
                actor_user_id=_safe_uuid(bearer_user_id_str),
            )
            raise SessionExpiredError()

        token_hash = hashlib.sha256(raw_cookie.encode()).hexdigest()

        # --- Step 3: Load active token row WITH row lock (reuses T003 lock) ----
        rt_row = self._repo.find_active_by_hash_for_update(token_hash)

        if rt_row is None:
            any_row = self._repo.find_by_hash(token_hash)
            reason = classify_logout_miss(any_row)
            logger.debug(
                "auth.logout.rejected reason=%s request_id=%s",
                reason,
                request_id,
            )
            actor_uid = _safe_uuid(bearer_user_id_str)
            if any_row is not None:
                actor_uid = getattr(any_row, "user_id", actor_uid)
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason=reason,
                actor_user_id=actor_uid,
            )
            raise SessionExpiredError()

        # --- Step 4: Validate user_id match (D2) --------------------------------
        cookie_user_id = rt_row.user_id
        bearer_uuid = _safe_uuid(bearer_user_id_str)
        if bearer_uuid is None or bearer_uuid != cookie_user_id:
            logger.debug(
                "auth.logout.rejected reason=user_mismatch request_id=%s",
                request_id,
            )
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="user_mismatch",
                actor_user_id=cookie_user_id,
            )
            raise SessionExpiredError()

        # --- Step 5: Revoke the token and write audit (same tx, D3) ------------
        token_id = rt_row.id
        self._repo.revoke(token_id)
        self._audit.write_success(
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            user_id=cookie_user_id,
            token_id=token_id,
        )
        self._session.commit()

        logger.debug(
            "auth.logout.execute.done user_id=%s token_id=%s request_id=%s",
            str(cookie_user_id),
            str(token_id),
            request_id,
        )  # AFTER

    def _validate_bearer(
        self,
        access_bearer: Optional[str],
        request_id: str,
        ip: str,
        user_agent: str,
    ) -> str:
        """Decode and validate the Bearer JWT. Returns Bearer sub claim on success.

        Args:
            access_bearer: Raw Bearer token string (may be None).
            request_id: X-Request-ID correlation.
            ip: Client IP.
            user_agent: Client User-Agent.

        Returns:
            JWT sub claim string (user UUID string).

        Raises:
            SessionExpiredError: On missing/invalid/expired Bearer.
        """
        if not access_bearer:
            logger.debug(
                "auth.logout.rejected reason=no_bearer request_id=%s",
                request_id,
            )
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="no_bearer",
                actor_user_id=None,
            )
            raise SessionExpiredError()

        try:
            claims = decode_token(access_bearer)
            return claims.get("sub", "")
        except jwt.ExpiredSignatureError:
            logger.debug(
                "auth.logout.rejected reason=expired_bearer request_id=%s",
                request_id,
            )
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="expired_bearer",
                actor_user_id=None,
            )
            raise SessionExpiredError() from None
        except Exception:
            logger.debug(
                "auth.logout.rejected reason=invalid_bearer request_id=%s",
                request_id,
            )
            self._audit.write_failure(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="invalid_bearer",
                actor_user_id=None,
            )
            raise SessionExpiredError() from None


def _safe_uuid(value: str) -> Optional[uuid.UUID]:
    """Parse a UUID string safely, returning None on failure.

    Args:
        value: String to parse as UUID.

    Returns:
        uuid.UUID if parseable, else None.
    """
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
