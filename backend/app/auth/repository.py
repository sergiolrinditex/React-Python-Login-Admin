"""
Hilo People — Auth persistence repository.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Data layer for the auth module. Provides User and AuditLog persistence
         operations needed for sign-up. Additional methods (find_by_email for
         sign-in, refresh token ops) will be added in T002/T003.

Key deps:
  - sqlalchemy==2.0.49 (Session, exc.IntegrityError)
  - app.db.models.user.User — ORM identity model
  - app.db.models.auth.AuditLog — ORM audit model
  - app.auth.errors.EmailAlreadyExistsError — raised on UniqueViolation

Source refs:
  - TECHNICAL_GUIDE §10.3 DB schema (users, audit_logs)
  - task pack §C.5 (no employee_profiles write at sign-up — F.7)
  - task pack §F.5 (audit synchronous in same transaction)
  - task pack §F.6 (transaction strategy: BEGIN→INSERT users→INSERT audit→COMMIT)
  - task pack §L (extra_metadata vs metadata Python/DB attribute gotcha)
  - 01-non-negotiables.md §Database (parametrized queries, transactions)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR per method)

Decisions:
  - D-R1: UniqueViolation on users.email is caught and re-raised as
    EmailAlreadyExistsError (typed domain error) so the service layer does not
    need to know about psycopg3 exception types.
  - D-R2: AuditLog.extra_metadata is the Python attribute; DB column is 'metadata'.
    This is the P01-S01-T001 decision. See model docstring.
  - D-R3: Repository receives an already-hashed password (the service layer hashes).
    Repository never sees plain passwords.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.errors import EmailAlreadyExistsError
from app.db.models.auth import AuditLog
from app.db.models.user import User

logger = logging.getLogger(__name__)

# Psycopg3 unique-violation SQLSTATE code
_PG_UNIQUE_VIOLATION = "23505"


class AuthRepository:
    """Data-layer operations for the auth module (sign-up slice).

    All methods operate on the provided SQLAlchemy Session. The session
    lifecycle (commit/rollback) is managed by the caller (service layer).

    Args:
        session: An active SQLAlchemy Session (sync).
    """

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: SQLAlchemy sync Session for DB operations.
        """
        self._session = session

    # -----------------------------------------------------------------------
    # User operations
    # -----------------------------------------------------------------------

    def find_by_email(self, email: str) -> User | None:
        """Lookup a User row by email (case-insensitive via LOWER).

        Args:
            email: Lowercase-normalised email to look up.

        Returns:
            User ORM instance if found, else None.
        """
        logger.debug("auth.repo.find_by_email.start email_domain=%s", email.split("@")[-1])
        result = (
            self._session.query(User)
            .filter(User.email == email.lower())
            .first()
        )
        found = result is not None
        logger.debug("auth.repo.find_by_email.done found=%s", found)
        return result

    def create_user(
        self,
        email: str,
        password_hash: str,
        full_name: str,
    ) -> User:
        """Insert a new user row.

        The caller must commit/flush the session to write to DB.
        On UniqueViolation (duplicate email), re-raises EmailAlreadyExistsError.

        Args:
            email: Corporate email (lowercase-normalised).
            password_hash: Argon2id PHC hash string (NEVER the plain password).
            full_name: User's display name.

        Returns:
            The newly created and flushed User ORM instance (has .id assigned).

        Raises:
            EmailAlreadyExistsError: If email already exists in users table.
        """
        logger.info(
            "auth.repo.create_user.start email_domain=%s",
            email.split("@")[-1],
        )  # BEFORE — domain only at INFO
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
            status="active",
            # preferred_language defaults to 'es' at DB level
        )
        self._session.add(user)
        try:
            self._session.flush()  # assigns user.id without committing
        except IntegrityError as exc:
            self._session.rollback()
            # Check for UniqueViolation on users.email
            orig = getattr(exc, "orig", None)
            pgcode = getattr(orig, "sqlstate", None) if orig else None
            if pgcode == _PG_UNIQUE_VIOLATION or (
                orig and "unique" in str(orig).lower()
            ):
                logger.info(
                    "auth.repo.create_user.duplicate email_domain=%s",
                    email.split("@")[-1],
                )  # AFTER rejection
                raise EmailAlreadyExistsError() from exc
            logger.error(
                "auth.repo.create_user.error email_domain=%s",
                email.split("@")[-1],
                exc_info=True,
            )  # ERROR
            raise
        logger.info(
            "auth.repo.create_user.done user_id=%s", str(user.id)
        )  # AFTER
        return user

    # -----------------------------------------------------------------------
    # Audit log operations
    # -----------------------------------------------------------------------

    def write_audit(
        self,
        action: str,
        entity_type: str | None,
        entity_id: uuid.UUID | None,
        actor_user_id: uuid.UUID | None,
        metadata: dict[str, Any],
    ) -> AuditLog:
        """Insert an audit_logs row and flush (no commit).

        The session lifecycle is managed by the caller. This method only
        adds and flushes; commit or rollback is the caller's responsibility.

        Args:
            action: Audit action string (e.g. 'auth.sign_up').
            entity_type: Polymorphic entity type (e.g. 'user') or None.
            entity_id: UUID of the affected entity or None.
            actor_user_id: UUID of the acting user; NULL for pre-creation rejects.
            metadata: JSONB payload dict (request_id, ip, outcome, reason, etc.).
                      MUST NOT contain passwords, full emails (domain only), tokens.

        Returns:
            Flushed AuditLog ORM instance with .id assigned.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On unexpected DB error.
        """
        logger.debug(
            "auth.repo.write_audit.start action=%s actor_user_id=%s",
            action,
            str(actor_user_id) if actor_user_id else "NULL",
        )  # BEFORE
        # Ensure metadata is JSON-serialisable (handle UUID values, etc.)
        safe_meta = json.loads(json.dumps(metadata, default=str))
        audit = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            extra_metadata=safe_meta,
        )
        self._session.add(audit)
        self._session.flush()
        logger.debug(
            "auth.repo.write_audit.done audit_id=%s action=%s",
            str(audit.id),
            action,
        )  # AFTER
        return audit

    # -----------------------------------------------------------------------
    # Sign-in operations (added P01-S02-T002)
    # -----------------------------------------------------------------------

    def count_recent_signin_failures(
        self,
        user_id: uuid.UUID,
        window_seconds: int,
    ) -> int:
        """Count recent failed sign-in attempts for a user_id (lockout query).

        Queries audit_logs for rows where:
          - action = 'auth.sign_in'
          - metadata->>'outcome' = 'failure'
          - actor_user_id = :user_id
          - created_at > now() - interval (window_seconds)

        Used for §F.3 lockout check: if count >= threshold → return 423.

        TODO(P02-S02-T001): replace audit-log scan with Redis counter once
        Redis-backed rate-limit lands. This O(n) scan is acceptable for V1
        single-user lockout queries.

        Args:
            user_id: UUID of the authenticated user to check.
            window_seconds: Rolling time window in seconds.

        Returns:
            Number of recent failure audit rows.
        """
        from sqlalchemy import text as _text  # noqa: PLC0415 — lazy import avoids circular

        logger.debug(
            "auth.repo.count_signin_failures.start user_id=%s window=%ds",
            str(user_id),
            window_seconds,
        )  # BEFORE
        result = self._session.execute(
            _text(
                "SELECT COUNT(*) FROM audit_logs "
                "WHERE action = 'auth.sign_in' "
                "  AND actor_user_id = :uid "
                "  AND metadata->>'outcome' = 'failure' "
                "  AND created_at > now() - CAST(:window || ' seconds' AS INTERVAL)"
            ),
            {"uid": str(user_id), "window": str(window_seconds)},
        ).scalar()
        count = int(result or 0)
        logger.debug(
            "auth.repo.count_signin_failures.done user_id=%s count=%d",
            str(user_id),
            count,
        )  # AFTER
        return count

    def insert_refresh_token(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: object,  # datetime-like; avoid circular import (use typing.Any if needed)
    ) -> None:
        """Insert a new refresh_token row and flush (no commit).

        Stores the SHA-256 hash of the opaque refresh token (never the raw token).
        The caller must commit. revoked_at defaults to NULL (active token).

        Args:
            user_id: UUID of the authenticated user.
            token_hash: SHA-256 hex digest of the opaque token string.
            expires_at: Expiry timestamp (timezone-aware UTC).

        Raises:
            sqlalchemy.exc.SQLAlchemyError: On unexpected DB error.
        """
        from app.db.models.auth import RefreshToken  # noqa: PLC0415 — avoid circular

        logger.debug(
            "auth.repo.insert_refresh_token.start user_id=%s",
            str(user_id),
        )  # BEFORE — NEVER log token_hash
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(rt)
        self._session.flush()
        logger.debug(
            "auth.repo.insert_refresh_token.done user_id=%s rt_id=%s",
            str(user_id),
            str(rt.id),
        )  # AFTER
