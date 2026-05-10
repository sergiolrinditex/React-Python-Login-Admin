"""
Service layer: SignUpUserUseCase — sign-up orchestration.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up
Phase: P01 — Auth + Base Capabilities

Business rule (instrucciones.md §3.1 + §3.2):
  Validate request → check corporate email → check password strength →
  check duplicate → hash password → persist (users + employee_profiles + audit_logs)
  → return {mfa_required: true, user_id}.

All three DB writes happen inside a single transaction owned by the FastAPI
get_session dependency. If any step raises, the transaction is rolled back.

Decisions (task-pack §9):
  D3: mfa_required is always True — sign-up routes the user to /auth/2fa for TOTP
  enrollment. T001 does NOT insert into mfa_totp_secrets (that requires an encrypted
  TOTP secret generated at enrollment time — task-pack §9 D3).

Logging contract (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.5 + task-pack §12):
  BEFORE: auth.sign_up.start — email_masked, request_id
  AFTER:  auth.sign_up.ok   — user_id, mfa_required, request_id
  ERROR:  warning-level with error_class + masked email

Security: password and legal_acceptance NEVER appear in logs.
  The structlog _REDACTED_KEYS processor already covers 'password',
  but we do NOT bind these fields to the log at all (defense-in-depth).

Dependencies:
  - argon2-cffi 25.1.0 (PasswordHasher)
  - app.core.config (get_settings)
  - app.features.auth.errors (typed domain errors)
  - app.features.auth.repository (DB writes)
  - app.features.auth.schemas (SignUpRequest, SignUpResponseData)
  - sqlalchemy.ext.asyncio.AsyncSession
"""
from __future__ import annotations

import re

import structlog.contextvars
from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.features.auth import repository as repo
from app.features.auth.errors import (
    LegalAcceptanceMissingError,
    NonCorporateEmailError,
    WeakPasswordError,
)
from app.features.auth.schemas import SignUpRequest, SignUpResponseData

_logger = get_logger(__name__)

# argon2-cffi 25.1.0 defaults: m=65536 (64MB), t=3, p=4 — OWASP-2024 compliant.
# Reuse the same config as seeds/loader/auth.py (no speculative params added).
_PH = PasswordHasher()

# Password strength regex components (task-pack §6.4 / source: instrucciones §3.2).
_RE_UPPERCASE = re.compile(r"[A-Z]")
_RE_LOWERCASE = re.compile(r"[a-z]")
_RE_DIGIT = re.compile(r"\d")
_RE_SYMBOL = re.compile(r"[^A-Za-z0-9]")
_PASSWORD_MIN_LEN = 12


async def sign_up(
    request: SignUpRequest,
    session: AsyncSession,
    *,
    client_ip: str | None,
    user_agent: str | None,
) -> SignUpResponseData:
    """Execute the sign-up use case end-to-end.

    Sequence (task-pack §6.3):
      1. Log BEFORE with masked email.
      2. Validate legal_acceptance is True.
      3. Validate corporate-email rule (config-driven allowlist).
      4. Validate password strength.
      5. Hash password with Argon2id.
      6. INSERT into users (catches duplicate → EmailAlreadyExistsError).
      7. INSERT into employee_profiles.
      8. INSERT into audit_logs.
      9. Log AFTER with user_id.
      10. Return SignUpResponseData(mfa_required=True, user_id=...).

    Params:
      request    — validated SignUpRequest (email, password, full_name, legal_acceptance).
      session    — async SQLAlchemy session; caller (get_session) owns the commit.
      client_ip  — client IP from request.client.host; None if unavailable.
      user_agent — User-Agent header; None if missing.
    Returns: SignUpResponseData with mfa_required=True and the new user's UUID.
    Raises:
      LegalAcceptanceMissingError — legal_acceptance is False.
      NonCorporateEmailError      — email domain not in allowlist (when allowlist non-empty).
      WeakPasswordError           — password does not meet strength policy.
      EmailAlreadyExistsError     — email already registered (raised by repository).
      SQLAlchemyError             — unexpected DB failure (propagated).
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")
    email_masked = _mask_email(request.email)

    _logger.debug(
        "BEFORE auth.sign_up.start: validating sign-up request",
        email_masked=email_masked,
        request_id=request_id,
    )

    # Step 2: legal acceptance
    _validate_legal_acceptance(request.legal_acceptance)

    # Step 3: corporate email
    settings = get_settings()
    _validate_corporate_email(request.email, settings.corporate_email_domains_list)

    # Step 4: password strength
    _validate_password_strength(request.password)

    # Step 5: hash password
    password_hash = _PH.hash(request.password)

    # Steps 6-8: persist (single transaction — session commit is in get_session)
    user = await repo.insert_user(
        session,
        email=request.email,
        password_hash=password_hash,
        full_name=request.full_name,
    )
    await repo.insert_employee_profile(session, user_id=user.id)
    await repo.insert_audit_log(
        session,
        user_id=user.id,
        ip=client_ip,
        user_agent=user_agent,
        request_id=request_id,
    )

    _logger.debug(
        "AFTER auth.sign_up.ok: user created",
        user_id=str(user.id),
        mfa_required=True,
        request_id=request_id,
    )

    return SignUpResponseData(mfa_required=True, user_id=user.id)


# ---------------------------------------------------------------------------
# Private validation helpers
# ---------------------------------------------------------------------------


def _validate_legal_acceptance(accepted: bool) -> None:
    """Assert legal_acceptance is True; raise LegalAcceptanceMissingError otherwise.

    Business rule: instrucciones.md §3.2 — 'aceptación legal en sign-up'.
    Params: accepted — raw bool from SignUpRequest.
    Raises: LegalAcceptanceMissingError when accepted is False.
    """
    if not accepted:
        _logger.warning(
            "ERROR auth.sign_up.legal_acceptance_missing: legal_acceptance=false",
            error_class="LegalAcceptanceMissingError",
        )
        raise LegalAcceptanceMissingError()


def _validate_corporate_email(email: str, allowed_domains: list[str]) -> None:
    """Check email domain against the corporate allowlist (task-pack §9 R3).

    When allowed_domains is empty → permissive (dev/test mode).
    When non-empty → strict allowlist match (case-insensitive domain comparison).

    Params:
      email          — full email address (already Pydantic-validated as EmailStr).
      allowed_domains — list[str] from CORPORATE_EMAIL_DOMAINS setting.
    Raises: NonCorporateEmailError when allowlist is non-empty and domain not in it.
    """
    if not allowed_domains:
        return  # permissive in dev
    domain = email.rsplit("@", 1)[-1].lower()
    if domain not in [d.lower() for d in allowed_domains]:
        _logger.warning(
            "ERROR auth.sign_up.non_corporate_email: domain not in allowlist",
            domain=domain,
            error_class="NonCorporateEmailError",
        )
        raise NonCorporateEmailError(domain=domain)


def _validate_password_strength(password: str) -> None:
    """Validate password meets the project strength policy (task-pack §6.4).

    Policy:
      - Minimum 12 characters.
      - At least 1 uppercase letter.
      - At least 1 lowercase letter.
      - At least 1 digit.
      - At least 1 symbol (non-alphanumeric character).

    Params: password — plain-text password (NEVER logged).
    Raises: WeakPasswordError with a specific reason.
    """
    if len(password) < _PASSWORD_MIN_LEN:
        raise WeakPasswordError(f"must be at least {_PASSWORD_MIN_LEN} characters")
    if not _RE_UPPERCASE.search(password):
        raise WeakPasswordError("must contain at least one uppercase letter")
    if not _RE_LOWERCASE.search(password):
        raise WeakPasswordError("must contain at least one lowercase letter")
    if not _RE_DIGIT.search(password):
        raise WeakPasswordError("must contain at least one digit")
    if not _RE_SYMBOL.search(password):
        raise WeakPasswordError("must contain at least one symbol")


def _mask_email(email: str) -> str:
    """Return a masked email for safe logging (e.g. 's.l***@gmail.com').

    Purpose: prevent PII from appearing in log payloads.
    Params: email — full email address.
    Returns: masked string (first char + '***' + '@' + domain).
    """
    try:
        local, domain = email.rsplit("@", 1)
        return f"{local[0]}***@{domain}"
    except Exception:  # noqa: BLE001
        return "***@***"
