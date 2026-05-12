"""
Hilo People — SignInUser use case (sign-in service).

Slice:  P01-S02-T002 — POST /api/v1/auth/sign-in (debugger cycle 1 extract).
Phase:  P01 Auth + Data Foundation
Responsibility: orchestrate one POST /sign-in request — aggregate-401, lockout,
MFA branch, success branch, opportunistic rehash, audit-every-attempt.

Refs: TECHNICAL_GUIDE §6.2/§10.2/§10.5; task pack §F.1..F.9, BR1..BR9;
01-non-negotiables.md §File size/§Security; validator P01-S02-T002 F1..F8.

Decisions:
  - D-S2: rejection audit commits in its own short transaction (audit survives
    a rolled-back main tx).
  - Module-level imports only — no lazy imports, no private cross-module symbols.
    Public `verify_with_dummy_fallback` replaces previous `_DUMMY_HASH` leak (F4).
  - `_ReqContext` packs (request_id, ip, user_agent) so helpers stay ≤50 LOC.
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

from app.auth.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidPayloadError,
)
from app.auth.password import (
    hash_password,
    needs_rehash,
    verify_with_dummy_fallback,
)
from app.auth.repository import AuthRepository
from app.auth.tokens import encode_access_token, encode_mfa_challenge_token
from app.db.models.auth import MfaTotpSecret

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignInResult:
    """No-MFA: mfa_required=False, access_token + refresh_token set.
    MFA:    mfa_required=True,  mfa_challenge_token set."""

    user_id: uuid.UUID
    mfa_required: bool
    access_token: str | None = None
    refresh_token: str | None = None
    mfa_challenge_token: str | None = None
    expires_in: int = 1800


@dataclass(frozen=True)
class _ReqContext:
    """Immutable request correlation context shared by all helpers."""

    request_id: str
    ip: str
    user_agent: str


class SignInUser:
    """Authenticate an employee and issue tokens.

    Public entry-point is `execute(...)`. Internal helpers (each ≤50 LOC) keep
    the orchestrator readable per 01-non-negotiables.md §File size.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = AuthRepository(session)

    # --- Public orchestrator -----------------------------------------
    def execute(
        self,
        email: str,
        password_plain: str,
        request_id: str,
        ip: str,
        user_agent: str,
    ) -> SignInResult:
        """Run the full sign-in flow.

        Raises:
            InvalidPayloadError: empty/whitespace email or password (BR9).
            InvalidCredentialsError: unknown email or wrong password (BR1+BR3).
            AccountLockedError: lockout threshold exceeded (BR4).
        """
        ctx = _ReqContext(request_id=request_id, ip=ip, user_agent=user_agent)
        email_domain = email.split("@")[-1] if "@" in email else "unknown"
        logger.info(
            "auth.sign_in.starting request_id=%s email_domain=%s",
            request_id, email_domain,
        )  # BEFORE

        self._validate_payload(email, password_plain, ctx)

        user = self._repo.find_by_email(email)
        if user is None:
            self._handle_unknown_email(password_plain, email_domain, ctx)
            raise InvalidCredentialsError()  # unreachable — _handle_unknown_email raised

        logger.info(
            "auth.sign_in.user_found user_id=%s request_id=%s",
            str(user.id), request_id,
        )

        self._reject_if_inactive(user, password_plain, ctx)
        self._check_lockout(user.id, ctx)
        self._verify_password_or_reject(user, password_plain, ctx)

        if self._is_mfa_enabled(user.id):
            return self._issue_mfa_challenge(user, password_plain, ctx)
        return self._issue_session_tokens(user, password_plain, ctx)

    # --- Step helpers (each ≤50 LOC) ---------------------------------
    def _validate_payload(self, email: str, password_plain: str, ctx: _ReqContext) -> None:
        """BR9 — reject empty/whitespace email/password with 400 + audit row.

        Pydantic rejects EmailStr="" (422); this service-layer 400 branch is
        the only way to produce `audit_logs(reason='invalid_payload')`
        end-to-end (closed validator F6 gap — see test_signin_invalid_payload_*).
        """
        if not email or not email.strip():
            logger.warning("auth.sign_in.rejected reason=EMPTY_EMAIL request_id=%s", ctx.request_id)
            self._write_rejection_audit(ctx, "failure", "invalid_payload", None)
            raise InvalidPayloadError(field="email")
        if not password_plain or not password_plain.strip():
            logger.warning("auth.sign_in.rejected reason=EMPTY_PASSWORD request_id=%s", ctx.request_id)
            self._write_rejection_audit(ctx, "failure", "invalid_payload", None)
            raise InvalidPayloadError(field="password")

    def _handle_unknown_email(
        self, password_plain: str, email_domain: str, ctx: _ReqContext
    ) -> None:
        """BR1+BR2 — dummy verify (timing equaliser) + audit + raise 401."""
        logger.info(
            "auth.sign_in.unknown_email email_domain=%s request_id=%s",
            email_domain, ctx.request_id,
        )
        verify_with_dummy_fallback(None, password_plain)
        self._write_rejection_audit(ctx, "failure", "unknown_email", None)
        raise InvalidCredentialsError()

    def _reject_if_inactive(self, user, password_plain: str, ctx: _ReqContext) -> None:
        """BR3 — disabled/pending users get the same 401 as wrong password (timing-equal)."""
        if user.status == "active":
            return
        logger.info(
            "auth.sign_in.rejected reason=USER_INACTIVE user_id=%s request_id=%s",
            str(user.id), ctx.request_id,
        )
        verify_with_dummy_fallback(user.password_hash, password_plain)
        self._write_rejection_audit(ctx, "failure", "user_inactive", user.id)
        raise InvalidCredentialsError()

    def _check_lockout(self, user_id: uuid.UUID, ctx: _ReqContext) -> None:
        """BR4 — recent-failure count via audit_logs; raise 423 over threshold.

        Gated by `find_by_email != None` (caller guarantee) so unknown emails
        cannot trigger lockout (no enumeration oracle).
        TODO(P02-S02-T001): replace audit-log scan with Redis counter.
        """
        threshold = int(os.getenv("AUTH_SIGNIN_LOCKOUT_THRESHOLD", "5"))
        window = int(os.getenv("AUTH_SIGNIN_LOCKOUT_WINDOW_SECONDS", "900"))
        failures = self._repo.count_recent_signin_failures(user_id=user_id, window_seconds=window)
        if failures < threshold:
            return
        logger.warning(
            "auth.sign_in.locked user_id=%s failures=%d request_id=%s",
            str(user_id), failures, ctx.request_id,
        )
        self._write_rejection_audit(ctx, "blocked", "account_locked", user_id)
        raise AccountLockedError()

    def _verify_password_or_reject(self, user, password_plain: str, ctx: _ReqContext) -> None:
        """Verify password; mismatch → 401 AUTH_INVALID_CREDENTIALS + audit."""
        if verify_with_dummy_fallback(user.password_hash, password_plain):
            return
        logger.info(
            "auth.sign_in.wrong_password user_id=%s request_id=%s",
            str(user.id), ctx.request_id,
        )
        self._write_rejection_audit(ctx, "failure", "wrong_password", user.id)
        raise InvalidCredentialsError()

    def _is_mfa_enabled(self, user_id: uuid.UUID) -> bool:
        """Look up `mfa_totp_secrets`; return True iff `enabled=True`."""
        row = (
            self._session.query(MfaTotpSecret)
            .filter(MfaTotpSecret.user_id == user_id)
            .first()
        )
        return bool(row and row.enabled)

    def _issue_mfa_challenge(self, user, password_plain: str, ctx: _ReqContext) -> SignInResult:
        """BR5 — issue 5-min JWT challenge; no access/refresh, no cookie."""
        mfa_ttl = int(os.getenv("AUTH_MFA_CHALLENGE_TTL_SECONDS", "300"))
        challenge_token = encode_mfa_challenge_token(user_id=user.id, ttl=mfa_ttl)
        self._write_success_audit(ctx, "mfa_challenge_issued", user.id)
        self._maybe_rehash(user, password_plain, ctx.request_id)
        self._session.commit()
        logger.info(
            "auth.sign_in.mfa_challenge_issued user_id=%s request_id=%s",
            str(user.id), ctx.request_id,
        )  # AFTER mfa
        return SignInResult(
            user_id=user.id,
            mfa_required=True,
            mfa_challenge_token=challenge_token,
            expires_in=mfa_ttl,
        )

    def _issue_session_tokens(self, user, password_plain: str, ctx: _ReqContext) -> SignInResult:
        """BR6 — access JWT + opaque refresh + sha256 storage + audit (one commit)."""
        access_ttl = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "1800"))
        refresh_ttl = int(os.getenv("AUTH_REFRESH_TTL_SECONDS", "2592000"))
        access_token = encode_access_token(user, ttl=access_ttl)
        opaque_refresh = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(opaque_refresh.encode()).hexdigest()
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=refresh_ttl)

        self._repo.insert_refresh_token(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
        self._maybe_rehash(user, password_plain, ctx.request_id)
        self._write_success_audit(ctx, "success", user.id)
        self._session.commit()

        logger.info(
            "auth.sign_in.success user_id=%s request_id=%s",
            str(user.id), ctx.request_id,
        )  # AFTER success
        return SignInResult(
            user_id=user.id,
            mfa_required=False,
            access_token=access_token,
            refresh_token=opaque_refresh,
            expires_in=access_ttl,
        )

    def _maybe_rehash(self, user, password_plain: str, request_id: str) -> None:
        """BR7 — opportunistic Argon2 upgrade; rides the caller's commit."""
        if not needs_rehash(user.password_hash):
            return
        user.password_hash = hash_password(password_plain)
        logger.info(
            "auth.sign_in.password_rehashed user_id=%s request_id=%s",
            str(user.id), request_id,
        )

    # --- Audit helpers -----------------------------------------------
    @staticmethod
    def _audit_meta(ctx: _ReqContext, outcome: str, reason: str | None = None) -> dict:
        """Shape the audit_logs.metadata jsonb dict for sign-in rows."""
        meta = {"request_id": ctx.request_id, "ip": ctx.ip,
                "user_agent": ctx.user_agent, "outcome": outcome}
        if reason is not None:
            meta["reason"] = reason
        return meta

    def _write_rejection_audit(
        self, ctx: _ReqContext, outcome: str, reason: str,
        actor_user_id: uuid.UUID | None,
    ) -> None:
        """D-S2 — rejection audit in its own short transaction."""
        logger.debug(
            "auth.sign_in.rejection_audit.start outcome=%s reason=%s request_id=%s",
            outcome, reason, ctx.request_id,
        )
        try:
            self._repo.write_audit(
                action="auth.sign_in", entity_type="user",
                entity_id=actor_user_id, actor_user_id=actor_user_id,
                metadata=self._audit_meta(ctx, outcome, reason),
            )
            self._session.commit()
        except Exception:
            logger.error(
                "auth.sign_in.rejection_audit.error outcome=%s reason=%s request_id=%s",
                outcome, reason, ctx.request_id, exc_info=True,
            )
            self._session.rollback()

    def _write_success_audit(self, ctx: _ReqContext, outcome: str, user_id: uuid.UUID) -> None:
        """Success / mfa_challenge_issued audit (caller commits)."""
        self._repo.write_audit(
            action="auth.sign_in", entity_type="user",
            entity_id=user_id, actor_user_id=user_id,
            metadata=self._audit_meta(ctx, outcome),
        )
