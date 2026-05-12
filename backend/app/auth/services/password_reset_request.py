"""
Hilo People — RequestPasswordReset use case (forgot-password flow).

Slice:  P01-S02-T005 — debugger cycle 1 (split per validator F1: extract
                       a single use case to keep file <=300 LOC, "1 use
                       case per file" rule from 01-non-negotiables.md).
Phase:  P01 Auth + Data Foundation
Purpose: One use case — generate a one-use token, persist its sha256 hash,
         write an audit row, and dispatch a localised reset email via the
         configured Mailer. Anti-enumeration is enforced at this layer.

Key deps:
  - app.auth.reset_tokens (generate_raw_token, hash_token)
  - app.auth.repositories.password_reset.PasswordResetTokenRepository
  - app.auth.password (verify_with_dummy_fallback — timing equaliser)
  - app.auth.repository.AuthRepository (find_by_email, write_audit)
  - app.mail (get_mailer — selects OutboxMailer/ResendMailer/SmtpMailer)

Decisions:
  - D-PR-S1: Anti-enum timing: when the email is not found we still call
    verify_with_dummy_fallback(None, "dummy") so the Argon2 work dominates
    the path cost and the two branches stay statistically indistinguishable.
  - D-PR-S2: Each forgot-password call creates a new token without
    invalidating old ones — they TTL-expire naturally (KISS/YAGNI).
  - D-PR-S5: Audit row written for both found and not-found paths
    (user_found=true/false in metadata).

Source refs:
  - task pack P01-S02-T005 §H-forgot (acceptance), §I-5 (services contract).
  - TECHNICAL_GUIDE §6.2 fila 259 (POST /auth/forgot-password).
  - 01-non-negotiables.md §Security (OWASP A07 anti-enum), §File size.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.password import verify_with_dummy_fallback
from app.auth.repositories.password_reset import PasswordResetTokenRepository
from app.auth.repository import AuthRepository
from app.auth.reset_tokens import generate_raw_token, hash_token

logger = logging.getLogger(__name__)

_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
logger.setLevel(logging.DEBUG if _VERBOSE else logging.WARNING)

_DEFAULT_TTL = 3600  # 1 hour


class RequestPasswordReset:
    """Use case: request a forgot-password email.

    Anti-enumeration: this use case never tells the caller whether the
    email exists. The router always returns the same 200 body.

    Business rules:
    - BR1: If user not found OR disabled, DO NOT insert token, DO NOT send mail.
    - BR2: If user found+active, insert token (hash only), send email.
    - BR3: All paths produce the same 200 body (byte-equal, §H-forgot-4).
    - BR4: Timing equalised by dummy Argon2 call on unknown-email path
           (§H-forgot-3).
    - BR5: Audit row written for both found and not-found paths.
    """

    def execute(
        self,
        *,
        session: Session,
        email: str,
        ip: str,
        user_agent: str,  # noqa: ARG002 — kept for symmetry with reset use case
        request_id: str,
    ) -> None:
        """Process a forgot-password request.

        Args:
            session: Active SQLAlchemy Session (this method commits).
            email: Email from the request body (Pydantic-validated).
            ip: Client IP for audit (stored as truncated sha256 hash).
            user_agent: User-Agent header (kept for parity; unused here).
            request_id: X-Request-ID for log/audit correlation.
        """
        log_email = (
            f"email_domain={email.split('@')[-1]}"
            if "@" in email
            else "email_domain=unknown"
        )
        logger.debug(
            "auth.forgot.start %s request_id=%s", log_email, request_id
        )  # BEFORE — no full email, no token

        auth_repo = AuthRepository(session)
        user = auth_repo.find_by_email(email)
        user_found = user is not None and getattr(user, "status", None) == "active"

        # D-PR-S1: Equalise timing via dummy Argon2 on not-found path
        if not user_found:
            verify_with_dummy_fallback(None, "dummy-reset-equaliser")

        raw_token: str | None = None
        if user_found and user is not None:
            raw_token = self._issue_token_and_audit(
                session=session,
                auth_repo=auth_repo,
                user=user,
                email=email,
                ip=ip,
                request_id=request_id,
            )
            # Send email AFTER commit (token persisted; on mail failure user retries).
            self._dispatch_email(
                to=email,
                user_email=email,
                raw_token=raw_token,
                locale=getattr(user, "preferred_language", "es") or "es",
                request_id=request_id,
            )
        else:
            self._audit_unknown(
                session=session,
                auth_repo=auth_repo,
                email=email,
                ip=ip,
                request_id=request_id,
            )

        logger.debug(
            "auth.forgot.done %s user_found=%s sent=%s request_id=%s",
            log_email,
            user_found,
            raw_token is not None,
            request_id,
        )  # AFTER — no raw token, no full email

    def _issue_token_and_audit(
        self,
        *,
        session: Session,
        auth_repo: AuthRepository,
        user,
        email: str,
        ip: str,
        request_id: str,
    ) -> str:
        """Persist a new reset-token row + audit, then commit. Returns raw token."""
        raw_token = generate_raw_token()
        token_hash = hash_token(raw_token)
        ttl = int(os.getenv("AUTH_RESET_TOKEN_TTL_SECONDS", str(_DEFAULT_TTL)))
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)

        prt_repo = PasswordResetTokenRepository(session)
        prt = prt_repo.insert(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        auth_repo.write_audit(
            action="auth.password_reset.requested",
            entity_type="user",
            entity_id=user.id,
            actor_user_id=user.id,
            metadata={
                "request_id": request_id,
                "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:12],
                "email_domain": email.split("@")[-1],
                "user_found": True,
                "token_id": str(prt.id),
            },
        )
        session.commit()
        return raw_token

    def _audit_unknown(
        self,
        *,
        session: Session,
        auth_repo: AuthRepository,
        email: str,
        ip: str,
        request_id: str,
    ) -> None:
        """Write audit row for unknown/disabled email path and commit."""
        auth_repo.write_audit(
            action="auth.password_reset.requested",
            entity_type=None,
            entity_id=None,
            actor_user_id=None,
            metadata={
                "request_id": request_id,
                "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:12],
                "email_domain": email.split("@")[-1],
                "user_found": False,
            },
        )
        session.commit()

    def _dispatch_email(
        self,
        *,
        to: str,
        user_email: str,
        raw_token: str,
        locale: str,
        request_id: str,
    ) -> None:
        """Dispatch the reset email via the configured mailer (best-effort).

        Mail failure is logged at ERROR but does NOT propagate — the router
        already returned 200 (anti-enum). The user can retry the forgot flow.

        Args:
            to: Recipient address.
            user_email: Display address shown in the template.
            raw_token: URL-safe token embedded in the link. NEVER log.
            locale: Preferred locale (es/en/fr).
            request_id: Correlation ID.
        """
        from app.mail import get_mailer  # noqa: PLC0415 — avoid circular at module init

        logger.debug(
            "auth.forgot.dispatch_email.start locale=%s request_id=%s",
            locale,
            request_id,
        )  # BEFORE — no token, no full email
        try:
            mailer = get_mailer()
            mailer.send_reset_email(
                to=to,
                user_email=user_email,
                raw_token=raw_token,
                locale=locale,
                request_id=request_id,
            )
            logger.debug(
                "auth.forgot.dispatch_email.done locale=%s",
                locale,
            )  # AFTER
        except Exception:
            logger.error(
                "auth.forgot.dispatch_email.error locale=%s request_id=%s",
                locale,
                request_id,
                exc_info=True,
            )  # ERROR — best-effort, do not propagate
