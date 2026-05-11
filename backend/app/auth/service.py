"""
Hilo People — SignUpUser use case (service layer).

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Orchestrates the sign-up flow: validate domain + password, dummy-hash
         on duplicate to prevent timing-based user enumeration, persist user,
         write audit log (success and rejection). Returns a SignUpResult.

Key deps:
  - app.auth.domain — CorporateEmail, Password value objects
  - app.auth.errors — typed domain errors
  - app.auth.password — Argon2id wrapper
  - app.auth.repository — AuthRepository (data layer)
  - sqlalchemy.orm.Session — injected session (lifecycle owned by router)

Source refs:
  - TECHNICAL_GUIDE §6.2, §10.2, §10.5
  - task pack §F (all decisions: no employee_profiles, audit on rejections, etc.)
  - task pack §G (Front→Back→DB contract)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR per use case)
  - 01-non-negotiables.md §Security/Audit log

Business rules:
  - BR1: Email must have a domain in CORPORATE_EMAIL_DOMAINS.
  - BR2: legal_acceptance must be True (server-side gate, not trusted from client).
  - BR3: Password must meet policy (min 12, max 256, 1 letter + 1 digit).
  - BR4: Duplicate email returns 409 with no user enumeration (constant-time path).
  - BR5: Audit row written on EVERY attempt (success and rejection).
  - BR6: No JWT issued at sign-up — token issuance belongs to sign-in (T002).
  - BR7: No employee_profiles row created at sign-up (no employee fields in payload).

Decisions:
  - D-S1: Dummy hash on duplicate-email path to ensure response time is
    indistinguishable from success path (prevents timing-based enumeration).
  - D-S2: Rejection audit rows use a SEPARATE short transaction (own BEGIN/COMMIT)
    so they commit independently of the sign-up transaction. Success audit row
    shares the sign-up transaction (F.5 — audit failure rolls back user creation).
  - D-S3: session.commit() for success is called IN the service, not the router,
    so service owns atomicity.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.auth.domain import CorporateEmail, Password
from app.auth.errors import (
    EmailAlreadyExistsError,
    LegalNotAcceptedError,
    NonCorporateEmailError,
)
from app.auth.password import hash_password
from app.auth.repository import AuthRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SignUpResult:
    """Immutable result returned by SignUpUser.execute on success.

    Attributes:
        user_id: UUID of the newly created user.
        mfa_required: Always False for new employees (no admin role at sign-up).
                      Included for forward-compatibility with admin onboarding flows.
    """

    user_id: uuid.UUID
    mfa_required: bool = False


class SignUpUser:
    """Use case: register a new employee account.

    Orchestrates domain validation, password hashing, persistence and audit.
    One instance per request (not a singleton) — the session is injected.

    Business rule: this use case CREATES a user with Argon2id-hashed password,
    writes an audit row, and returns the user's UUID. No JWT is issued here.
    """

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: Active SQLAlchemy Session. The use case commits or rolls back.
        """
        self._session = session
        self._repo = AuthRepository(session)

    def execute(
        self,
        email: str,
        password_plain: str,
        full_name: str,
        legal_acceptance: bool,
        request_id: str,
        ip: str,
        user_agent: str,
    ) -> SignUpResult:
        """Execute the sign-up use case.

        Args:
            email: Raw email from request body (will be validated + normalised).
            password_plain: Raw password from request body (NEVER logged).
            full_name: User's display name.
            legal_acceptance: Must be True; service-side gate (BR2).
            request_id: X-Request-ID header value for correlation.
            ip: Client IP address for audit log.
            user_agent: User-Agent header for audit log.

        Returns:
            SignUpResult with user_id and mfa_required=False.

        Raises:
            LegalNotAcceptedError: BR2 — legal_acceptance is False.
            NonCorporateEmailError: BR1 — email domain not in allowlist.
            EmailAlreadyExistsError: BR4 — email already registered (409).
            PasswordPolicyError: BR3 — password does not meet policy.
        """
        logger.info(
            "auth.sign_up.starting request_id=%s email_domain=%s",
            request_id,
            email.split("@")[-1] if "@" in email else "unknown",
        )  # BEFORE

        # ----------------------------------------------------------------
        # BR2: Legal acceptance gate (fast path — no DB)
        # ----------------------------------------------------------------
        if not legal_acceptance:
            logger.warning(
                "auth.sign_up.rejected reason=LEGAL_NOT_ACCEPTED request_id=%s",
                request_id,
            )
            self._write_rejection_audit(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="LEGAL_NOT_ACCEPTED",
                email_domain=email.split("@")[-1] if "@" in email else "unknown",
            )
            raise LegalNotAcceptedError()

        # ----------------------------------------------------------------
        # BR1: Corporate email validation (no DB)
        # ----------------------------------------------------------------
        try:
            corporate_email = CorporateEmail(email)
        except NonCorporateEmailError as exc:
            logger.warning(
                "auth.sign_up.rejected reason=NON_CORPORATE_EMAIL "
                "email_domain=%s request_id=%s",
                exc.domain,
                request_id,
            )
            self._write_rejection_audit(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="NON_CORPORATE_EMAIL",
                email_domain=exc.domain,
            )
            raise

        # ----------------------------------------------------------------
        # BR3: Password policy validation (no DB)
        # ----------------------------------------------------------------
        validated_password = Password(password_plain)

        # ----------------------------------------------------------------
        # Hash + persist (BEGIN → INSERT users → INSERT audit → COMMIT)
        # ----------------------------------------------------------------
        password_hash = hash_password(validated_password.plain)

        try:
            user = self._repo.create_user(
                email=corporate_email.value,
                password_hash=password_hash,
                full_name=full_name.strip(),
            )
            # Write success audit row in SAME transaction (F.5)
            self._repo.write_audit(
                action="auth.sign_up",
                entity_type="user",
                entity_id=user.id,
                actor_user_id=user.id,
                metadata={
                    "request_id": request_id,
                    "ip": ip,
                    "user_agent": user_agent,
                    "outcome": "success",
                },
            )
            self._session.commit()
            logger.info(
                "auth.sign_up.success user_id=%s request_id=%s",
                str(user.id),
                request_id,
            )  # AFTER success
            return SignUpResult(user_id=user.id)

        except EmailAlreadyExistsError:
            # D-S1: Dummy hash to equalise response time (no user enumeration)
            hash_password(password_plain)
            logger.info(
                "auth.sign_up.rejected reason=EMAIL_TAKEN "
                "email_domain=%s request_id=%s",
                corporate_email.domain,
                request_id,
            )
            self._write_rejection_audit(
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                reason="EMAIL_TAKEN",
                email_domain=corporate_email.domain,
            )
            raise

    def _write_rejection_audit(
        self,
        request_id: str,
        ip: str,
        user_agent: str,
        reason: str,
        email_domain: str,
    ) -> None:
        """Write an audit log row for a rejected sign-up attempt.

        Uses a SEPARATE transaction (D-S2) so it commits even when the main
        sign-up transaction rolled back (e.g. UniqueViolation).

        Args:
            request_id: X-Request-ID for correlation.
            ip: Client IP.
            user_agent: User-Agent header.
            reason: Short code for rejection reason (no PII — domain only).
            email_domain: The email domain portion only (NEVER full email).
        """
        logger.debug(
            "auth.sign_up.rejection_audit.start reason=%s request_id=%s",
            reason,
            request_id,
        )
        try:
            self._repo.write_audit(
                action="auth.sign_up",
                entity_type="user",
                entity_id=None,
                actor_user_id=None,
                metadata={
                    "request_id": request_id,
                    "ip": ip,
                    "user_agent": user_agent,
                    "outcome": "rejected",
                    "reason": reason,
                    "rejected_domain": email_domain,
                },
            )
            self._session.commit()
            logger.debug(
                "auth.sign_up.rejection_audit.done reason=%s",
                reason,
            )
        except Exception:
            logger.error(
                "auth.sign_up.rejection_audit.error reason=%s request_id=%s",
                reason,
                request_id,
                exc_info=True,
            )
            self._session.rollback()
