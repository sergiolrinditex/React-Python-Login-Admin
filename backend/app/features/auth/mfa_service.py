"""
Service layer: MFA enrollment use case — POST /api/v1/auth/2fa/enroll.

Slice: P01-S02-T009 — POST /api/v1/auth/2fa/enroll
Phase: P01 — Auth + Base Capabilities

Business rule (instrucciones.md §3.6 + task-pack §1 + §9 D1 + D2):
  Re-authenticate user via email+password (step-up auth) →
  generate TOTP secret → encrypt → upsert mfa_totp_secrets →
  insert audit_log → return otpauth_url + qr_png_base64.

Decisions applied here:
  D1 — Re-auth with email+password (not Bearer JWT — none issued yet at T009).
  D2 — Rotation policy: re-enroll is allowed; updates secret + resets enabled=false.
  D3 — Recovery codes: OUT OF SCOPE. No mfa_recovery_codes table; not created here.
  D6 — Log hygiene: secret_b32, otpauth_url, qr_png_base64 NEVER appear in any log.

One transaction owned by the caller (FastAPI get_session dependency).

Logging contract (task-pack §11):
  BEFORE auth.mfa.enroll.start      — email_masked, request_id, ip
  AFTER  auth.mfa.enroll.reauth_ok  — user_id, request_id
  AFTER  auth.mfa.enroll.secret_generated — user_id, rotation, enabled=False
  AFTER  auth.mfa.enroll.persisted  — user_id, audit_log_id
  ERROR  auth.mfa.enroll.*         — WARNING level, email_masked, error_class

CWE-532 invariant:
  secret_b32, otpauth_url (full), qr_png_base64 NEVER bound to any logger call.
  Only: email_masked, user_id, request_id, rotation, enabled, audit_log_id.

Dependencies:
  - argon2-cffi 25.1.0 (PasswordHasher for re-auth)
  - pyotp 2.9.0 (TOTP secret generation + provisioning_uri)
  - qrcode[pil] 8.2 (QR PNG generation)
  - app.core.security (encrypt_secret — Fernet AEAD)
  - app.features.auth.mfa_repository (DB operations)
  - app.features.auth.errors (InvalidCredentialsError)
  - app.features.auth.schemas (MfaEnrollRequest, MfaEnrollResponseData)
  - sqlalchemy.ext.asyncio.AsyncSession
"""
from __future__ import annotations

import base64
import io

import pyotp
import qrcode
import structlog.contextvars
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import encrypt_secret
from app.features.auth import mfa_repository as repo
from app.features.auth.errors import InvalidCredentialsError
from app.features.auth.schemas import MfaEnrollRequest, MfaEnrollResponseData

_logger = get_logger(__name__)

# Reuse module-level PasswordHasher (OWASP-2024 defaults: m=65536, t=3, p=4).
# Same instance pattern as service.py (T001) — no custom params needed.
_PH = PasswordHasher()

# TOTP issuer name — must match the provisioning_uri label users see in their app.
# Value: "Hilo People" (task-pack §5.2 + §6.3 step 9).
_TOTP_ISSUER = "Hilo People"


async def enroll_mfa(
    request: MfaEnrollRequest,
    session: AsyncSession,
    *,
    client_ip: str | None,
    user_agent: str | None,
) -> MfaEnrollResponseData:
    """Execute the MFA enrollment use case end-to-end.

    Sequence (task-pack §6.3):
      1. Log BEFORE with masked email.
      2. get_user_for_enroll(email) → None → InvalidCredentialsError (generic).
      3. Verify password hash via argon2. Mismatch → InvalidCredentialsError (generic).
      4. Log AFTER reauth_ok with user_id only.
      5. Check existing mfa_totp_secrets row (determines rotation vs fresh).
      6. Generate TOTP secret with pyotp.random_base32() (32 chars base32).
      7. Encrypt secret with encrypt_secret() (Fernet AEAD).
      8. Upsert mfa_totp_secrets (INSERT or UPDATE per D2).
      9. Build otpauth_url via pyotp.TOTP(...).provisioning_uri(...).
      10. Generate QR PNG via qrcode, encode to base64 (no data: prefix).
      11. Log AFTER secret_generated with user_id + rotation + enabled=False.
      12. Insert audit_log with action='auth.2fa_enroll' + rotation metadata.
      13. Log AFTER persisted with audit_log_id.
      14. Return MfaEnrollResponseData(otpauth_url, qr_png_base64).

    CWE-532 invariant: secret_b32, otpauth_url, qr_png_base64 NEVER logged.

    Params:
      request    — validated MfaEnrollRequest (email: EmailStr, password: SecretStr).
      session    — async SQLAlchemy session; caller (get_session) owns the commit.
      client_ip  — client IP from request.client.host; None if unavailable.
      user_agent — User-Agent header value; None if missing.
    Returns: MfaEnrollResponseData (otpauth_url, qr_png_base64).
    Raises:
      InvalidCredentialsError — email not found OR password mismatch (same response).
      SQLAlchemyError         — unexpected DB failure (propagated to 500).
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")
    email = request.email
    email_masked = _mask_email(email)

    # Step 1 — BEFORE log
    _logger.info(
        "BEFORE auth.mfa.enroll.start",
        email_masked=email_masked,
        request_id=request_id,
        ip=client_ip,
    )

    # Step 2 — look up user (generic error for not-found AND wrong-password)
    user = await repo.get_user_for_enroll(session, email)
    if user is None:
        _logger.warning(
            "ERROR auth.mfa.enroll.invalid_credentials: user not found",
            email_masked=email_masked,
            request_id=request_id,
            error_class="InvalidCredentialsError",
        )
        raise InvalidCredentialsError("email not found")

    # Step 3 — verify password (argon2)
    _verify_password(
        user.password_hash, request.password.get_secret_value(), email_masked, request_id
    )

    # Step 4 — AFTER reauth ok (user_id only — no email in AFTER logs)
    user_id = user.id
    _logger.info(
        "AFTER auth.mfa.enroll.reauth_ok",
        user_id=str(user_id),
        request_id=request_id,
    )

    # Step 5 — check existing row (rotation vs fresh)
    existing = await repo.get_mfa_secret(session, user_id)
    is_rotation = existing is not None

    # Steps 6–8 — generate + encrypt + upsert
    secret_b32 = pyotp.random_base32()  # 32 chars base32 — NEVER logged
    secret_encrypted = encrypt_secret(secret_b32)
    await repo.upsert_mfa_secret(
        session,
        user_id=user_id,
        secret_encrypted=secret_encrypted,
        is_update=is_rotation,
    )

    # Steps 9–10 — build URI + QR (done AFTER DB write to keep it in same scope)
    otpauth_url = _build_otpauth_url(secret_b32, email)
    qr_png_base64 = _build_qr_png_base64(otpauth_url)

    # Step 11 — AFTER secret_generated (rotation + enabled only — NO secret/uri)
    _logger.info(
        "AFTER auth.mfa.enroll.secret_generated",
        user_id=str(user_id),
        rotation=is_rotation,
        enabled=False,
        request_id=request_id,
    )

    # Step 12 — audit_log
    audit = await repo.insert_audit_log_2fa_enroll(
        session,
        user_id=user_id,
        ip=client_ip,
        user_agent=user_agent,
        request_id=request_id,
        rotation=is_rotation,
    )

    # Step 13 — AFTER persisted
    _logger.info(
        "AFTER auth.mfa.enroll.persisted",
        user_id=str(user_id),
        audit_log_id=str(audit.id),
        request_id=request_id,
    )

    return MfaEnrollResponseData(otpauth_url=otpauth_url, qr_png_base64=qr_png_base64)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _verify_password(
    stored_hash: str, raw_password: str, email_masked: str, request_id: str
) -> None:
    """Verify raw_password against the argon2id stored_hash.

    Raises InvalidCredentialsError if verification fails.
    Uses the same PasswordHasher instance as sign-up (identical OWASP defaults).

    Params:
      stored_hash  — argon2id hash from users.password_hash.
      raw_password — plain-text password from MfaEnrollRequest.password.
      email_masked — for logging only (never the raw password).
      request_id   — correlation ID.
    Raises: InvalidCredentialsError on mismatch or verification error.
    """
    try:
        _PH.verify(stored_hash, raw_password)
    except (VerifyMismatchError, VerificationError):
        _logger.warning(
            "ERROR auth.mfa.enroll.invalid_credentials: password mismatch",
            email_masked=email_masked,
            request_id=request_id,
            error_class="InvalidCredentialsError",
        )
        raise InvalidCredentialsError("password mismatch") from None


def _build_otpauth_url(secret_b32: str, email: str) -> str:
    """Build a standard otpauth Key URI for the TOTP secret.

    Format: otpauth://totp/Hilo%20People:<email>?secret=<BASE32>&issuer=Hilo%20People
    Compatible with: Google Authenticator, Microsoft Authenticator, 1Password, Authy.
    Defaults: SHA1, 6 digits, 30-second period (RFC 6238 defaults).

    Params:
      secret_b32 — 32-char base32 secret (pyotp.random_base32()).
      email      — user email (account name label in authenticator app).
    Returns: otpauth URI string.

    Security: this string contains the raw base32 secret in the query param.
    NEVER pass it to a logger — CWE-532 D6.
    """
    totp = pyotp.TOTP(secret_b32)
    return totp.provisioning_uri(name=email, issuer_name=_TOTP_ISSUER)


def _build_qr_png_base64(otpauth_url: str) -> str:
    """Render the otpauth URI as a QR code PNG and return it base64-encoded.

    Uses qrcode[pil] (qrcode 8.2 + Pillow 12.2.0) — pure PNG output.
    Target size: ~200x200 px (box_size=6, border=2).
    Output: base64-encoded PNG bytes WITHOUT the data:image/png;base64, prefix.

    Params:
      otpauth_url — the otpauth Key URI to encode in the QR (contains secret).
    Returns: base64 string of PNG bytes.

    Security: this blob contains the secret indirectly (QR encodes the URI).
    NEVER log this value — CWE-532 D6.
    """
    qr = qrcode.QRCode(version=None, box_size=6, border=2)
    qr.add_data(otpauth_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _mask_email(email: str) -> str:
    """Return a masked email for safe logging (e.g. 'm***@gmail.com').

    Purpose: prevent PII from appearing in log payloads.
    Params: email — full email address.
    Returns: masked string (first char + '***' + '@' + domain).
    """
    try:
        local, domain = email.rsplit("@", 1)
        return f"{local[0]}***@{domain}"
    except Exception:  # noqa: BLE001
        return "***@***"
