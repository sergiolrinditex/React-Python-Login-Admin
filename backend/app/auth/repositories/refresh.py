"""
Hilo People — RefreshToken-specific data layer operations.

Slice:  P01-S02-T003 — POST /api/v1/auth/refresh
Phase:  P01 Auth + Data Foundation
Purpose: Specialized repository for refresh token rotation operations.
         Extracted from `repository.py` (at 300-line cap) per non-negotiables
         §File size + D-RP1 (follow T002 debugger pattern; one concern per file).

Key deps:
  - sqlalchemy==2.0.49 — Session, with_for_update, func
  - app.db.models.auth.RefreshToken — ORM model
  - app.db.models.user.User — status check

Source refs:
  - TECHNICAL_GUIDE §10.3 refresh_tokens schema (id, user_id, token_hash,
    expires_at, revoked_at — NO replaced_by column per D-RP4)
  - task pack P01-S02-T003 §D.3, §D-RP3 (atomic rotation with FOR UPDATE)
  - 01-non-negotiables.md §Database (parametrized queries, transactions)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR per method)

Decisions:
  - D-RP3: `with_for_update()` row-level lock serializes concurrent refresh calls.
    Under PG READ COMMITTED (default), SELECT ... FOR UPDATE blocks the second
    reader until the first commits; after unblocking, the second transaction
    re-evaluates the predicate (revoked_at IS NULL) and finds zero rows (401).
  - D-RP4: No `replaced_by` column — replay detection is rotation-only (KISS/YAGNI).
  - D-T003-REPO: find_active_by_hash returns None when the token is expired,
    revoked, or unknown — the caller maps each case to 401 with its own audit reason.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.auth import RefreshToken
from app.db.models.user import User

logger = logging.getLogger(__name__)


class RefreshTokenRepository:
    """Data-layer operations for refresh token rotation (P01-S02-T003).

    All methods operate on the provided SQLAlchemy Session. Session lifecycle
    (commit/rollback) is managed by the caller (service layer).

    Args:
        session: An active SQLAlchemy Session (sync).
    """

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: SQLAlchemy sync Session for DB operations.
        """
        self._session = session

    def find_active_by_hash_for_update(self, token_hash: str) -> Optional[RefreshToken]:
        """Look up an active (non-revoked, non-expired) refresh token row WITH a row lock.

        Acquires a SELECT ... FOR UPDATE row-level lock so that two concurrent
        /refresh requests serialise: the loser, after unblocking, re-evaluates
        `revoked_at IS NULL AND expires_at > now()` and finds zero rows (401).

        Args:
            token_hash: SHA-256 hex digest of the opaque refresh cookie value.
                        NEVER log the full hash. Use token_hash[:8]+"..." for
                        correlation if absolutely necessary.

        Returns:
            RefreshToken ORM instance (locked) if found + active, else None.
        """
        logger.debug(
            "auth.repo.refresh.find_active_for_update.start hash_prefix=%s",
            token_hash[:8] + "...",
        )  # BEFORE — prefix only, never full hash
        row = (
            self._session.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > func.now(),
            )
            .with_for_update()
            .first()
        )
        found = row is not None
        logger.debug(
            "auth.repo.refresh.find_active_for_update.done found=%s hash_prefix=%s",
            found,
            token_hash[:8] + "...",
        )  # AFTER
        return row

    def find_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """Look up a refresh token row by hash (no lock, no active filter).

        Used by failure-audit paths to determine actor_user_id when the token
        is known but expired or revoked (we still want to log the user_id).

        Args:
            token_hash: SHA-256 hex digest of the opaque refresh cookie value.

        Returns:
            RefreshToken ORM instance (any state) or None if hash unknown.
        """
        logger.debug(
            "auth.repo.refresh.find_by_hash.start hash_prefix=%s",
            token_hash[:8] + "...",
        )  # BEFORE
        row = (
            self._session.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        logger.debug(
            "auth.repo.refresh.find_by_hash.done found=%s",
            row is not None,
        )  # AFTER
        return row

    def revoke(self, token_id: uuid.UUID) -> None:
        """Mark a refresh token row as revoked by setting revoked_at = now().

        Must be called within the same transaction as insert_new (rotation
        atomicity). The caller commits.

        Args:
            token_id: UUID of the refresh_tokens row to revoke.
        """
        logger.debug(
            "auth.repo.refresh.revoke.start token_id=%s",
            str(token_id),
        )  # BEFORE
        self._session.query(RefreshToken).filter(
            RefreshToken.id == token_id
        ).update(
            {"revoked_at": datetime.now(tz=timezone.utc)},
            synchronize_session="fetch",
        )
        logger.debug(
            "auth.repo.refresh.revoke.done token_id=%s",
            str(token_id),
        )  # AFTER

    def insert_new(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Insert a new active refresh token row and flush (no commit).

        The caller must commit. revoked_at defaults to NULL (active).

        Args:
            user_id: UUID of the authenticated user.
            token_hash: SHA-256 hex digest of the new opaque token (NEVER raw).
            expires_at: Timezone-aware UTC datetime for expiry.

        Returns:
            Flushed RefreshToken ORM instance with .id assigned.
        """
        logger.debug(
            "auth.repo.refresh.insert_new.start user_id=%s",
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
            "auth.repo.refresh.insert_new.done user_id=%s new_rt_id=%s",
            str(user_id),
            str(rt.id),
        )  # AFTER
        return rt

    def find_user_active(self, user_id: uuid.UUID) -> Optional[User]:
        """Load the User row and check status == 'active'.

        Args:
            user_id: UUID of the user to verify.

        Returns:
            User ORM instance if found and active, else None.
        """
        logger.debug(
            "auth.repo.refresh.find_user_active.start user_id=%s",
            str(user_id),
        )  # BEFORE
        user = (
            self._session.query(User)
            .filter(User.id == user_id)
            .first()
        )
        active = user is not None and getattr(user, "status", None) == "active"
        logger.debug(
            "auth.repo.refresh.find_user_active.done user_id=%s active=%s",
            str(user_id),
            active,
        )  # AFTER
        return user if active else None

    def revoke_all_active_for_user(
        self,
        user_id: uuid.UUID,
        reason: str = "password_reset",
    ) -> int:
        """Revoke all active refresh tokens for a user (bulk session invalidation).

        Used by the password reset flow (§H-reset-8) to invalidate all open
        sessions after a successful password change. Marks revoked_at = now()
        on every row WHERE user_id = :uid AND revoked_at IS NULL.

        Args:
            user_id: UUID of the user whose sessions are to be invalidated.
            reason:  Audit metadata label (default 'password_reset').

        Returns:
            Number of rows updated (count of sessions invalidated).
        """
        logger.debug(
            "auth.repo.refresh.revoke_all_active.start user_id=%s reason=%s",
            str(user_id),
            reason,
        )  # BEFORE
        now = datetime.now(tz=timezone.utc)
        count = (
            self._session.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .update(
                {"revoked_at": now},
                synchronize_session="fetch",
            )
        )
        logger.debug(
            "auth.repo.refresh.revoke_all_active.done user_id=%s revoked=%d",
            str(user_id),
            count,
        )  # AFTER
        return count
