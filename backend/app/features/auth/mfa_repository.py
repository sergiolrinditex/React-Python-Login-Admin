"""
Repository: MFA enrollment — DB reads/writes for POST /api/v1/auth/2fa/enroll.

Slice: P01-S02-T009 — POST /api/v1/auth/2fa/enroll
Phase: P01 — Auth + Base Capabilities

Single responsibility: async DB operations for the MFA enrollment use case.
The session is NEVER committed here; the FastAPI get_session dependency commits
(same design as repository.py from T001).

Public interface:
  - get_user_for_enroll(session, email) → User | None
  - get_mfa_secret(session, user_id)    → MfaTotpSecret | None
  - upsert_mfa_secret(session, user_id, secret_encrypted, is_update)
                                         → MfaTotpSecret
  - insert_audit_log_2fa_enroll(session, user_id, ip, ua, request_id, rotation)
                                         → AuditLog

Error handling:
  - All typed SQLAlchemy errors propagate to service (no domain-error mapping needed
    here — the service maps them to InvalidCredentialsError or HTTPException 500).

Logging contract (task-pack §11):
  BEFORE / AFTER per public function.
  No secret, no otpauth_url, no qr_png_base64, no password_hash in any log.
  Only: user_id, is_update, rotation, enabled, audit_log_id.

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - app.db.models.user (User)
  - app.db.models.auth (MfaTotpSecret, AuditLog)
  - app.core.logging (get_logger)
"""
from __future__ import annotations

import uuid

import structlog.contextvars
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.auth import AuditLog, MfaTotpSecret
from app.db.models.user import User

_logger = get_logger(__name__)


async def get_user_for_enroll(session: AsyncSession, email: str) -> User | None:
    """Fetch a user by email for the MFA enrollment re-auth check.

    Purpose: retrieve the user record so the service can verify the password hash.
    Only the user's id, email, and password_hash fields are needed.

    Params:
      session — active async SQLAlchemy session.
      email   — raw email string from MfaEnrollRequest.
    Returns: User ORM instance or None if not found.
    Errors: SQLAlchemyError propagates (unexpected DB failure).
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")

    _logger.debug(
        "BEFORE auth.mfa.repository.get_user_for_enroll",
        email_masked=_mask_email(email),
        request_id=request_id,
    )

    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    _logger.debug(
        "AFTER auth.mfa.repository.get_user_for_enroll",
        found=user is not None,
        request_id=request_id,
    )
    return user


async def get_mfa_secret(
    session: AsyncSession, user_id: uuid.UUID
) -> MfaTotpSecret | None:
    """Fetch an existing mfa_totp_secrets row for a user.

    Purpose: service checks for an existing secret to determine if this is
    a fresh enroll or a rotation (idempotency policy D2).

    Params:
      session — active async SQLAlchemy session.
      user_id — UUID of the user to look up.
    Returns: MfaTotpSecret ORM instance or None if no row exists.
    Errors: SQLAlchemyError propagates.
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")

    _logger.debug(
        "BEFORE auth.mfa.repository.get_mfa_secret",
        user_id=str(user_id),
        request_id=request_id,
    )

    stmt = select(MfaTotpSecret).where(MfaTotpSecret.user_id == user_id)
    result = await session.execute(stmt)
    secret = result.scalar_one_or_none()

    _logger.debug(
        "AFTER auth.mfa.repository.get_mfa_secret",
        user_id=str(user_id),
        exists=secret is not None,
        request_id=request_id,
    )
    return secret


async def upsert_mfa_secret(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    secret_encrypted: str,
    is_update: bool,
) -> MfaTotpSecret:
    """INSERT or UPDATE a row in mfa_totp_secrets for the given user.

    Business rule (D2, task-pack §9 D2):
      Fresh enroll  → INSERT a new row (enabled=false).
      Re-enroll     → UPDATE secret_encrypted + reset enabled=false (rotation).
    The 'enabled' column remains FALSE until /2fa/verify (T006) confirms the secret.

    Params:
      session          — active async SQLAlchemy session.
      user_id          — UUID of the user being enrolled.
      secret_encrypted — Fernet-encrypted TOTP base32 secret (NOT the raw secret).
      is_update        — True if the user already has a row (rotation path).
    Returns: flushed MfaTotpSecret ORM instance (not yet committed).
    Errors: SQLAlchemyError propagates.

    Security: secret_encrypted is the Fernet token, NOT the base32 seed.
    The raw seed is NEVER stored. No secret value logged here.
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")

    _logger.debug(
        "BEFORE auth.mfa.repository.upsert_mfa_secret",
        user_id=str(user_id),
        is_update=is_update,
        request_id=request_id,
    )

    if is_update:
        # Rotation: fetch existing row and update it in-place
        stmt = select(MfaTotpSecret).where(MfaTotpSecret.user_id == user_id)
        result = await session.execute(stmt)
        row = result.scalar_one()
        row.secret_encrypted = secret_encrypted
        row.enabled = False  # type: ignore[assignment]
        await session.flush()
    else:
        # Fresh enroll: insert new row
        row = MfaTotpSecret(
            user_id=user_id,
            secret_encrypted=secret_encrypted,
            enabled=False,
        )
        session.add(row)
        await session.flush()

    _logger.debug(
        "AFTER auth.mfa.repository.upsert_mfa_secret",
        user_id=str(user_id),
        is_update=is_update,
        enabled=False,
        request_id=request_id,
    )
    return row


async def insert_audit_log_2fa_enroll(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
    request_id: str,
    rotation: bool,
) -> AuditLog:
    """Insert an audit_logs row for the auth.2fa_enroll action.

    GDPR Art. 30 — every MFA enrollment (fresh or rotation) is a sensitive action.
    Leaves a traza with rotation metadata so auditors can detect suspicious patterns
    (per D2 design, task-pack §9 D2).

    Params:
      session    — active async SQLAlchemy session.
      user_id    — UUID of the enrolling user (actor + entity).
      ip         — client IP from request.client.host; None if unavailable.
      user_agent — User-Agent header; None if missing.
      request_id — X-Request-ID correlation string.
      rotation   — True if this is a re-enrollment (existing secret rotated).
    Returns: flushed AuditLog ORM instance.
    Errors: SQLAlchemyError propagates.

    Action name: 'auth.2fa_enroll' (convention: action.scope with dots, matches
    'auth.sign_up' from T001 — task-pack §7.2 + R7 note on naming).
    """
    _logger.debug(
        "BEFORE auth.mfa.repository.insert_audit_log_2fa_enroll",
        user_id=str(user_id),
        action="auth.2fa_enroll",
        rotation=rotation,
        request_id=request_id,
    )

    log = AuditLog(
        actor_user_id=user_id,
        action="auth.2fa_enroll",
        entity_type="user",
        entity_id=user_id,
        metadata_col={"enabled": False, "rotation": rotation},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
        resource="POST /api/v1/auth/2fa/enroll",
    )
    session.add(log)
    await session.flush()

    _logger.debug(
        "AFTER auth.mfa.repository.insert_audit_log_2fa_enroll",
        user_id=str(user_id),
        audit_log_id=str(log.id),
        rotation=rotation,
        request_id=request_id,
    )
    return log


def _mask_email(email: str) -> str:
    """Return a masked email for safe logging (e.g. 'm***@gmail.com').

    Purpose: prevent PII from appearing in log payloads.
    Params: email — full email address.
    Returns: masked string (first char + '***' + '@' + domain).
    Errors: any malformed email string falls back to '***@***'.
    """
    try:
        local, domain = email.rsplit("@", 1)
        return f"{local[0]}***@{domain}"
    except Exception:  # noqa: BLE001
        return "***@***"
