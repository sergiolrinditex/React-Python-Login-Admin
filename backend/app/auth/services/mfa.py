"""
Hilo People — VerifyMfaChallenge use case (2FA verify service).

Slice:  P01-S02-T006 — POST /api/v1/auth/2fa/verify
Phase:  P01 Auth + Data Foundation
Responsibility: Verify a submitted TOTP code against the mfa_challenge_token
from the sign-in MFA branch. On success: issue access_token + refresh cookie
(same shape as the no-MFA sign-in branch). On any failure: aggregate-401
with dummy-verify for timing equalization.

Refs:
  - TECHNICAL_GUIDE §6.2 row 261 (POST /api/v1/auth/2fa/verify)
  - task pack §F.1..F.9, §G (Front→Back→DB contract)
  - 01-non-negotiables.md §File size (≤300 LOC), §Security

Decisions per task pack §M:
  - D-MFA-REPLAY: in-memory jti consume store (threading.Lock dict)
  - D-MFA-WINDOW: valid_window=1 (±30s, RFC 6238 §5.2)
  - D-MFA-ANTI-ENUM: same 401 body for all failure paths + dummy-verify
  - D-MFA-CRYPTO: mfa_crypto.decrypt_totp_secret facade
  - D-S2: failure audit in independent session (audit_session_scope)
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import pyotp
from sqlalchemy.orm import Session

from app.auth.errors import (
    MfaChallengeExpiredError,
    MfaChallengeInvalidError,
    MfaCodeInvalidError,
    MfaReplayError,
    MfaSecretMissingError,
)
from app.auth.mfa_crypto import decrypt_totp_secret
from app.auth.repositories.mfa import ChallengeReplayStore, MfaRepository
from app.auth.repositories.refresh import RefreshTokenRepository
from app.auth.repository import AuthRepository
from app.auth.tokens import decode_token, encode_access_token
from app.db.models.user import User
from app.db.session import audit_session_scope

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Dummy base32 secret for timing equalization when no MFA secret exists.
# Computed once at module import — same pattern as password.DUMMY_VERIFY_HASH.
_DUMMY_SECRET: str = "JBSWY3DPEHPK3PXP"  # test-known; never used in production auth
_VERIFY_WINDOW: int = int(os.getenv("AUTH_MFA_VERIFY_WINDOW", "1"))
_ACCESS_TTL: int = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "1800"))
_REFRESH_TTL: int = int(os.getenv("AUTH_REFRESH_TTL_SECONDS", "2592000"))


@dataclass(frozen=True)
class VerifyMfaResult:
    """Result returned by VerifyMfaChallenge.execute() on success.

    Attributes:
        user: Loaded User ORM instance (for encode_access_token + response DTO).
        access_token: Short-lived JWT access token (HS256).
        opaque_refresh: Raw opaque refresh token (URL-safe base64 string).
                        NEVER log. Set as HttpOnly cookie by the router.
        expires_in: Access token TTL in seconds.
    """

    user: User
    access_token: str
    opaque_refresh: str
    expires_in: int


@dataclass(frozen=True)
class _MfaCtx:
    """Immutable request context passed to helper methods."""

    request_id: str
    ip: str
    user_agent: str


class VerifyMfaChallenge:
    """Verify an MFA TOTP code against a signed challenge token.

    Business rules implemented:
    - BR1: enabled=true in mfa_totp_secrets is the gate (not role).
    - BR2: every attempt is audited (success + failure paths).
    - BR4: refresh cookie HttpOnly; same attrs as sign-in (T011 contract).
    - BR5: no code, no token, no email-local-part in logs.
    - BR6: verification uses provided data (pyotp.TOTP.now() live).

    Args:
        session: Active SQLAlchemy Session for the main transaction.
    """

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: SQLAlchemy sync Session (main transaction).
        """
        self._session = session
        self._repo = AuthRepository(session)
        self._refresh_repo = RefreshTokenRepository(session)
        self._mfa_repo = MfaRepository(session)
        self._replay = ChallengeReplayStore.instance()

    # -----------------------------------------------------------------------
    # Public orchestrator
    # -----------------------------------------------------------------------

    def execute(
        self,
        challenge_id: str,
        code: str,
        request_id: str,
        ip: str,
        user_agent: str,
    ) -> VerifyMfaResult:
        """Run the full 2FA verify flow.

        Args:
            challenge_id: The full JWT mfa_challenge_token string.
            code: 6-digit TOTP code from the user (validated by Pydantic upstream).
            request_id: X-Request-ID for correlation logging.
            ip: Client IP (for audit metadata).
            user_agent: Client User-Agent (for audit metadata).

        Returns:
            VerifyMfaResult on success.

        Raises:
            MfaChallengeExpiredError: Signature valid, exp in the past (410).
            MfaChallengeInvalidError: Signature invalid / purpose wrong (401).
            MfaReplayError: jti already consumed (401).
            MfaCodeInvalidError: Wrong TOTP code (401).
            MfaSecretMissingError: No enabled MFA secret (401).
        """
        ctx = _MfaCtx(request_id=request_id, ip=ip, user_agent=user_agent)
        logger.info(
            "auth.mfa.verify.received request_id=%s ip=%s",
            request_id, ip,
        )  # BEFORE

        # Step 1: decode + validate challenge token
        user_id, jti, exp_epoch = self._decode_challenge(challenge_id, ctx)

        # Step 2: replay check (BEFORE loading DB data to short-circuit fast)
        self._check_replay(jti, ctx)

        # Step 3: load user (must exist + status active)
        user = self._load_active_user(user_id, code, ctx)

        # Step 4: load TOTP secret + verify code
        self._verify_totp_code(user.id, code, ctx)

        # Step 5: success path — insert refresh row + audit in main tx, then commit
        result = self._issue_tokens_and_commit(user, jti, exp_epoch, ctx)

        logger.info(
            "auth.mfa.verify.success user_id=%s request_id=%s",
            str(user.id), request_id,
        )  # AFTER success
        return result

    # -----------------------------------------------------------------------
    # Step helpers (each ≤50 LOC)
    # -----------------------------------------------------------------------

    def _decode_challenge(
        self, challenge_id: str, ctx: _MfaCtx
    ) -> tuple[uuid.UUID, str, float]:
        """Decode mfa_challenge_token; return (user_id, jti, exp_epoch).

        Args:
            challenge_id: JWT string.
            ctx: Request context for audit.

        Returns:
            Tuple of (user_id, jti, exp_epoch as float Unix timestamp).

        Raises:
            MfaChallengeExpiredError: Token expired (410).
            MfaChallengeInvalidError: Token invalid / purpose mismatch (401).
        """
        try:
            claims = decode_token(challenge_id, expected_purpose="mfa_challenge")
        except jwt.ExpiredSignatureError:
            logger.info(
                "auth.mfa.verify.failure reason=challenge_expired request_id=%s",
                ctx.request_id,
            )
            self._write_failure_audit(ctx, "challenge_expired", None)
            raise MfaChallengeExpiredError()
        except (jwt.InvalidTokenError, ValueError) as exc:
            logger.info(
                "auth.mfa.verify.failure reason=challenge_invalid request_id=%s",
                ctx.request_id,
            )
            self._write_failure_audit(ctx, "challenge_invalid", None)
            raise MfaChallengeInvalidError() from exc

        sub = claims.get("sub", "")
        jti = claims.get("jti", "")
        exp = claims.get("exp", 0)
        # exp may be a datetime (PyJWT) or int — normalise to float
        if isinstance(exp, datetime):
            exp_epoch = exp.timestamp()
        else:
            exp_epoch = float(exp)
        try:
            user_id = uuid.UUID(sub)
        except (ValueError, AttributeError):
            logger.info(
                "auth.mfa.verify.failure reason=challenge_invalid request_id=%s",
                ctx.request_id,
            )
            self._write_failure_audit(ctx, "challenge_invalid", None)
            raise MfaChallengeInvalidError()
        return user_id, jti, exp_epoch

    def _check_replay(self, jti: str, ctx: _MfaCtx) -> None:
        """Reject if jti already consumed.

        Args:
            jti: JWT jti claim.
            ctx: Request context.

        Raises:
            MfaReplayError: jti already in replay store (401).
        """
        if self._replay.is_consumed(jti):
            logger.warning(
                "auth.mfa.verify.failure reason=replay jti_prefix=%s request_id=%s",
                jti[:8] + "...", ctx.request_id,
            )
            self._write_failure_audit(ctx, "replay", None)
            raise MfaReplayError()

    def _load_active_user(
        self, user_id: uuid.UUID, code: str, ctx: _MfaCtx
    ) -> User:
        """Load user and verify status==active; run dummy-verify if inactive.

        Args:
            user_id: UUID from challenge token sub claim.
            code: TOTP code (for timing equalization via dummy-verify).
            ctx: Request context.

        Returns:
            Active User ORM instance.

        Raises:
            MfaCodeInvalidError: User not found or not active (401).
        """
        user = (
            self._session.query(User)
            .filter(User.id == user_id)
            .first()
        )
        if user is None or getattr(user, "status", None) != "active":
            # Dummy verify to equalize timing
            pyotp.TOTP(_DUMMY_SECRET).verify(code, valid_window=_VERIFY_WINDOW)
            reason = "user_inactive"
            logger.info(
                "auth.mfa.verify.failure reason=%s request_id=%s",
                reason, ctx.request_id,
            )
            self._write_failure_audit(ctx, reason, user_id if user else None)
            raise MfaCodeInvalidError(reason=reason)
        return user

    def _verify_totp_code(
        self, user_id: uuid.UUID, code: str, ctx: _MfaCtx
    ) -> None:
        """Load TOTP secret and verify code; run dummy-verify if no secret.

        Args:
            user_id: UUID of the authenticated user.
            code: 6-digit TOTP code.
            ctx: Request context.

        Raises:
            MfaSecretMissingError: No enabled MFA secret (dummy-verify runs; 401).
            MfaCodeInvalidError: TOTP.verify returns False (401).
        """
        secret_row = self._mfa_repo.find_enabled_by_user_id(user_id)
        if secret_row is None:
            # Dummy-verify for timing equalization (D-MFA-ANTI-ENUM)
            pyotp.TOTP(_DUMMY_SECRET).verify(code, valid_window=_VERIFY_WINDOW)
            logger.info(
                "auth.mfa.verify.failure reason=no_secret user_id=%s request_id=%s",
                str(user_id), ctx.request_id,
            )
            self._write_failure_audit(ctx, "no_secret", user_id)
            raise MfaSecretMissingError()

        plaintext_seed = decrypt_totp_secret(secret_row.secret_encrypted)
        if not pyotp.TOTP(plaintext_seed).verify(code, valid_window=_VERIFY_WINDOW):
            logger.info(
                "auth.mfa.verify.failure reason=wrong_code user_id=%s request_id=%s",
                str(user_id), ctx.request_id,
            )
            self._write_failure_audit(ctx, "wrong_code", user_id)
            raise MfaCodeInvalidError(reason="wrong_code")

    def _issue_tokens_and_commit(
        self,
        user: User,
        jti: str,
        exp_epoch: float,
        ctx: _MfaCtx,
    ) -> VerifyMfaResult:
        """Insert refresh_tokens row + success audit; commit; then mark jti consumed.

        Args:
            user: Active User ORM instance.
            jti: JWT jti claim (consumed post-commit).
            exp_epoch: JWT exp as Unix timestamp.
            ctx: Request context.

        Returns:
            VerifyMfaResult with access_token and opaque_refresh.
        """
        access_token = encode_access_token(user, ttl=_ACCESS_TTL)
        opaque_refresh = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(opaque_refresh.encode()).hexdigest()
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=_REFRESH_TTL)

        self._refresh_repo.insert_new(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._repo.write_audit(
            action="auth.mfa.verify",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            metadata={
                "request_id": ctx.request_id,
                "ip": ctx.ip,
                "user_agent": ctx.user_agent[:255],
                "outcome": "success",
            },
        )
        self._session.commit()

        # Mark jti consumed AFTER successful commit (D-MFA-REPLAY §F.1 note)
        self._replay.consume(jti, exp_epoch)

        return VerifyMfaResult(
            user=user,
            access_token=access_token,
            opaque_refresh=opaque_refresh,
            expires_in=_ACCESS_TTL,
        )

    # -----------------------------------------------------------------------
    # Audit helper (D-S2 pattern — independent short session)
    # -----------------------------------------------------------------------

    def _write_failure_audit(
        self,
        ctx: _MfaCtx,
        reason: str,
        user_id: Optional[uuid.UUID],
    ) -> None:
        """Write failure audit row on an independent session (D-S2).

        Commits independently so the audit row survives if the main tx rolls back.

        Args:
            ctx: Request context.
            reason: One of: challenge_expired|challenge_invalid|replay|
                    user_inactive|no_secret|wrong_code|rate_limited|invalid_payload.
            user_id: UUID of the user if known, else None.
        """
        logger.debug(
            "auth.mfa.verify.failure_audit.start reason=%s request_id=%s",
            reason, ctx.request_id,
        )  # BEFORE
        with audit_session_scope() as short_session:
            try:
                short_repo = AuthRepository(short_session)
                short_repo.write_audit(
                    action="auth.mfa.verify",
                    entity_type="user",
                    entity_id=user_id,
                    actor_user_id=user_id,
                    metadata={
                        "request_id": ctx.request_id,
                        "ip": ctx.ip,
                        "user_agent": ctx.user_agent[:255],
                        "outcome": "failure",
                        "reason": reason,
                    },
                )
                short_session.commit()
                logger.debug(
                    "auth.mfa.verify.failure_audit.done reason=%s request_id=%s",
                    reason, ctx.request_id,
                )  # AFTER
            except Exception:
                short_session.rollback()
                logger.error(
                    "auth.mfa.verify.failure_audit.error reason=%s request_id=%s",
                    reason, ctx.request_id, exc_info=True,
                )  # ERROR
