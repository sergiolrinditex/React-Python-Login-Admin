"""
Repository: auth feature — user, employee_profile, and audit_log DB writes.

Slice: P01-S02-T001 — POST /api/v1/auth/sign-up
Phase: P01 — Auth + Base Capabilities

Single responsibility: async DB writes inside a transaction managed by the caller.
The session is NEVER committed here; the FastAPI get_session dependency commits.

Public interface:
  - get_user_by_email(session, email) → User | None
  - insert_user(session, email, password_hash, full_name) → User
  - insert_employee_profile(session, user_id) → EmployeeProfile
  - insert_audit_log(session, user_id, ip, user_agent, request_id) → AuditLog

Error handling:
  - insert_user catches sqlalchemy.exc.IntegrityError (duplicate email UNIQUE
    constraint) and re-raises as EmailAlreadyExistsError — the repository is
    the canonical place for DB constraint → domain-error mapping (per task-pack §6.3).
  - All other SQLAlchemy errors propagate to the service layer → FastAPI 500.

Logging contract (HILO_PEOPLE_TECHNICAL_GUIDE.md §10.5 + task-pack §12):
  BEFORE / AFTER / ERROR per operation.  No password, no PII beyond masked email.

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - app.db.models.user (User, EmployeeProfile)
  - app.db.models.auth (AuditLog)
  - app.features.auth.errors (EmailAlreadyExistsError)
  - app.core.logging (get_logger)
"""
from __future__ import annotations

import hashlib
import uuid

import structlog.contextvars
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.auth import AuditLog
from app.db.models.user import EmployeeProfile, User
from app.features.auth.errors import EmailAlreadyExistsError

_logger = get_logger(__name__)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Fetch a user row by email address (case-sensitive lookup).

    Purpose: used by sign-in and duplicate-email check (optimistic — race handled by
    UNIQUE constraint + IntegrityError catch in insert_user).

    Params:
      session — active async SQLAlchemy session.
      email   — raw email string.
    Returns: User ORM instance or None if not found.
    Errors: SQLAlchemyError propagates (unexpected DB failure).
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")

    _logger.debug(
        "BEFORE auth.repository.get_user_by_email",
        email_masked=_mask_email(email),
        request_id=request_id,
    )

    stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    _logger.debug(
        "AFTER auth.repository.get_user_by_email",
        found=user is not None,
        request_id=request_id,
    )
    return user


async def insert_user(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    full_name: str,
) -> User:
    """Insert a new row into the users table.

    Business rule (task-pack §6.3 + §13 R on-conflict):
      Rely on the DB UNIQUE constraint for atomicity — do NOT SELECT-then-INSERT.
      If a race condition causes a duplicate INSERT, the UNIQUE constraint fires an
      IntegrityError which is mapped to EmailAlreadyExistsError here.

    Params:
      session       — active async SQLAlchemy session.
      email         — validated corporate email (stored as-is — unique index exists).
      password_hash — Argon2id hash string (never the plain password).
      full_name     — trimmed display name.
    Returns: flushed User ORM instance (id assigned by DB; not yet committed).
    Errors:
      EmailAlreadyExistsError — email already registered (UNIQUE violation).
      SQLAlchemyError         — unexpected DB failure (propagated).
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")

    _logger.debug(
        "BEFORE auth.repository.insert_user",
        email_masked=_mask_email(email),
        request_id=request_id,
    )

    user = User(
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        status="active",
        preferred_language="es",
    )
    session.add(user)

    try:
        await session.flush()  # assign id + detect UNIQUE constraint violations
    except IntegrityError as exc:
        await session.rollback()
        _logger.warning(
            "ERROR auth.repository.insert_user: IntegrityError (duplicate email)",
            email_masked=_mask_email(email),
            request_id=request_id,
            error_class="IntegrityError",
        )
        raise EmailAlreadyExistsError(email_masked=_mask_email(email)) from exc

    _logger.debug(
        "AFTER auth.repository.insert_user",
        user_id=str(user.id),
        request_id=request_id,
    )
    return user


async def insert_employee_profile(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> EmployeeProfile:
    """Insert a row into employee_profiles for a newly created user.

    Purpose: every user created via sign-up gets an employee profile with
    placeholder HR values. Real HR attributes (brand, society, center, etc.)
    will be updated via admin or HRIS integration in a future slice.

    employee_id derivation: SHA-256 of the user_id UUID string, first 8 hex chars,
    upper-cased. Guaranteed unique because user_id is UUID and SHA-256 is collision-
    resistant at this output length for the expected user volume.

    Params:
      session — active async SQLAlchemy session.
      user_id — UUID of the just-created User row.
    Returns: flushed EmployeeProfile ORM instance.
    Errors: SQLAlchemyError propagates (unexpected DB failure).
    """
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", "")

    _logger.debug(
        "BEFORE auth.repository.insert_employee_profile",
        user_id=str(user_id),
        request_id=request_id,
    )

    employee_id = "EMP-" + hashlib.sha256(str(user_id).encode()).hexdigest()[:8].upper()

    profile = EmployeeProfile(
        user_id=user_id,
        employee_id=employee_id,
        brand="Hilo",
        society="Hilo People",
        center="HQ",
        country="ES",
        department="",
        metadata_col={},
    )
    session.add(profile)
    await session.flush()

    _logger.debug(
        "AFTER auth.repository.insert_employee_profile",
        user_id=str(user_id),
        employee_id=employee_id,
        request_id=request_id,
    )
    return profile


async def insert_audit_log(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    ip: str | None,
    user_agent: str | None,
    request_id: str,
) -> AuditLog:
    """Insert an audit_logs row for the auth.sign_up action.

    GDPR Art. 30 — every sign-up is a sensitive action that must be audited.
    The ip, user_agent, request_id, and resource columns are the T005 compliance
    columns; they are populated directly now that migration 0002 has landed.

    Params:
      session    — active async SQLAlchemy session.
      user_id    — the newly created user (actor_user_id = entity_id for sign-up).
      ip         — client IP from request.client.host; None if unavailable.
      user_agent — User-Agent header; None if missing.
      request_id — X-Request-ID correlation string.
    Returns: flushed AuditLog ORM instance.
    Errors: SQLAlchemyError propagates (unexpected DB failure).
    """
    _logger.debug(
        "BEFORE auth.repository.insert_audit_log",
        user_id=str(user_id),
        action="auth.sign_up",
        request_id=request_id,
    )

    log = AuditLog(
        actor_user_id=user_id,
        action="auth.sign_up",
        entity_type="user",
        entity_id=user_id,
        metadata_col={},  # no extra JSONB payload needed; fields in native columns
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
        resource="POST /api/v1/auth/sign-up",
    )
    session.add(log)
    await session.flush()

    _logger.debug(
        "AFTER auth.repository.insert_audit_log",
        user_id=str(user_id),
        audit_log_id=str(log.id),
        request_id=request_id,
    )
    return log


def _mask_email(email: str) -> str:
    """Return a masked email for safe logging (e.g. 's.l***@gmail.com').

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
