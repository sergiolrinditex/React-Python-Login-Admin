"""
Hilo People — ResetPassword use case (reset-password flow, token consumption).

Slice:  P01-S02-T005 — debugger cycle 1 (split per validator F1: extract
                       a single use case to keep file <=300 LOC, "1 use
                       case per file" rule from 01-non-negotiables.md).
Phase:  P01 Auth + Data Foundation
Purpose: One use case — validate the password policy, lock+consume the
         one-use token (SELECT FOR UPDATE), re-hash the password, revoke
         all active refresh tokens, and write the audit row. Single atomic
         transaction (commit or rollback).

Key deps:
  - app.auth.reset_tokens (hash_token, is_expired)
  - app.auth.repositories.password_reset.PasswordResetTokenRepository
  - app.auth.repositories.refresh.RefreshTokenRepository
  - app.auth.password (hash_password — Argon2)
  - app.auth.repository.AuthRepository (write_audit)
  - app.db.models.user.User

Decisions:
  - D-PR-S3: Password policy: min 12 chars, >=1 upper, >=1 digit, >=1 symbol.
    Raises InvalidPayloadError with a concatenated field-level message.
  - D-PR-S4: Reset flow does NOT emit a new JWT/cookie — the client must
    sign-in again after reset (TECHNICAL_GUIDE §10.2 strategy note).
  - D-PR-S5: Audit row includes sessions_revoked count.

Source refs:
  - task pack P01-S02-T005 §H-reset (acceptance), §I-8 (services contract).
  - TECHNICAL_GUIDE §6.2 fila 260 (POST /auth/reset-password).
  - 01-non-negotiables.md §Security (Argon2, session invalidation), §File size.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re

from sqlalchemy.orm import Session

from app.auth.errors import (
    InvalidPayloadError,
    ResetTokenExpiredError,
    ResetTokenInvalidError,
)
from app.auth.password import hash_password
from app.auth.repositories.password_reset import PasswordResetTokenRepository
from app.auth.repositories.refresh import RefreshTokenRepository
from app.auth.repository import AuthRepository
from app.auth.reset_tokens import hash_token, is_expired

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)


def _validate_password_policy(password: str) -> list[dict]:
    """Check password meets policy (min 12 chars, upper, digit, symbol).

    Args:
        password: Plain text password candidate.

    Returns:
        List of field-level error dicts (empty when policy satisfied).
    """
    errors: list[dict] = []
    if len(password) < 12:
        errors.append({
            "field": "password",
            "code": "too_short",
            "message": "Minimum 12 characters required",
        })
    if not re.search(r"[A-Z]", password):
        errors.append({
            "field": "password",
            "code": "no_uppercase",
            "message": "Must contain at least one uppercase letter",
        })
    if not re.search(r"[0-9]", password):
        errors.append({
            "field": "password",
            "code": "no_digit",
            "message": "Must contain at least one digit",
        })
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append({
            "field": "password",
            "code": "no_symbol",
            "message": "Must contain at least one symbol",
        })
    return errors


class ResetPassword:
    """Use case: consume a reset token and set a new password.

    Business rules:
    - BR1: Token must be valid (not used, not expired). FOR UPDATE concurrency.
    - BR2: Password must meet policy (min 12, upper, digit, symbol).
    - BR3: Update users.password_hash + mark token used + revoke all sessions.
    - BR4: All three updates in ONE atomic transaction (COMMIT or ROLLBACK).
    - BR5: Audit row includes sessions_revoked count.
    """

    def execute(
        self,
        *,
        session: Session,
        raw_token: str,
        new_password: str,
        ip: str,
        user_agent: str,  # noqa: ARG002 — kept for parity with request use case
        request_id: str,
    ) -> None:
        """Process a reset-password request.

        Args:
            session: Active SQLAlchemy Session (this method commits).
            raw_token: Raw token from the request body. NEVER log.
            new_password: New plaintext password. NEVER log.
            ip: Client IP for audit (truncated sha256 hash, never raw).
            user_agent: User-Agent header (kept for parity; unused).
            request_id: X-Request-ID for log/audit correlation.

        Raises:
            InvalidPayloadError: Password does not meet policy.
            ResetTokenExpiredError: Token has expired.
            ResetTokenInvalidError: Token is invalid, used, or unknown.
        """
        logger.debug(
            "auth.reset.start request_id=%s",
            request_id,
        )  # BEFORE — no token, no password

        policy_errors = _validate_password_policy(new_password)
        if policy_errors:
            raise InvalidPayloadError(
                field="password",
                reason="; ".join(e["message"] for e in policy_errors),
            )

        token_hash = hash_token(raw_token)
        prt_repo = PasswordResetTokenRepository(session)

        prt = prt_repo.find_active_by_hash_for_update(token_hash)
        if prt is None:
            self._raise_for_missing_active(prt_repo, token_hash, request_id)

        user_id = prt.user_id
        token_id = prt.id

        sessions_revoked = self._apply_password_change(
            session=session,
            prt_repo=prt_repo,
            user_id=user_id,
            token_id=token_id,
            new_password=new_password,
        )

        AuthRepository(session).write_audit(
            action="auth.password_reset.completed",
            entity_type="user",
            entity_id=user_id,
            actor_user_id=user_id,
            metadata={
                "request_id": request_id,
                "token_id": str(token_id),
                "sessions_revoked": sessions_revoked,
                "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:12],
            },
        )

        session.commit()

        logger.debug(
            "auth.reset.done user_id=%s sessions_revoked=%d request_id=%s",
            str(user_id),
            sessions_revoked,
            request_id,
        )  # AFTER — no token, no password, no PII

    def _raise_for_missing_active(
        self,
        prt_repo: PasswordResetTokenRepository,
        token_hash: str,
        request_id: str,
    ) -> None:
        """Disambiguate expired vs invalid for audit clarity and raise.

        Both branches result in 410 at the HTTP layer; the differentiated
        error code lives in the audit log only (§H-reset-3 anti-enum oracle
        is acceptable per task pack).
        """
        existing = prt_repo.find_by_hash(token_hash)
        if existing is not None and is_expired(existing.expires_at):
            logger.warning(
                "auth.reset.expired request_id=%s",
                request_id,
            )
            raise ResetTokenExpiredError()
        logger.warning(
            "auth.reset.invalid request_id=%s",
            request_id,
        )
        raise ResetTokenInvalidError()

    def _apply_password_change(
        self,
        *,
        session: Session,
        prt_repo: PasswordResetTokenRepository,
        user_id,
        token_id,
        new_password: str,
    ) -> int:
        """Update password, mark token used, revoke active sessions. No commit.

        Returns:
            Number of refresh tokens revoked (>=0).
        """
        new_hash = hash_password(new_password)

        from app.db.models.user import User  # noqa: PLC0415 — avoid eager import

        session.query(User).filter(User.id == user_id).update(
            {"password_hash": new_hash},
            synchronize_session="fetch",
        )
        prt_repo.mark_used(token_id)

        rt_repo = RefreshTokenRepository(session)
        return rt_repo.revoke_all_active_for_user(
            user_id=user_id,
            reason="password_reset",
        )
