"""
Hilo People — PasswordResetToken data-layer operations.

Slice:  P01-S02-T005 — POST /api/v1/auth/forgot-password +
                       POST /api/v1/auth/reset-password
Phase:  P01 Auth + Data Foundation
Purpose: Repository for `password_reset_tokens` table — insert, lookup with
         FOR UPDATE, and mark-used. One responsibility per file.

Key deps:
  - sqlalchemy==2.0.49 — Session, with_for_update, func
  - app.db.models.auth.PasswordResetToken — ORM model

Source refs:
  - TECHNICAL_GUIDE §10.3 password_reset_tokens schema
  - task pack §I-3 (repo methods), §H-reset-7 (one-use, FOR UPDATE)
  - 01-non-negotiables.md §Database (parametrized queries, transactions)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR per method)

Decisions:
  - D-PR1: find_active_by_hash_for_update acquires a row-level lock (FOR UPDATE)
    so concurrent reset attempts on the same token serialise — the loser sees
    used_at IS NOT NULL after the winner commits (identical to T003 refresh).
  - D-PR2: Hashing is done by the caller (reset_tokens.hash_token). The
    repository receives pre-hashed values; never the raw token.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.auth import PasswordResetToken

logger = logging.getLogger(__name__)


class PasswordResetTokenRepository:
    """Data-layer operations for the password_reset_tokens table.

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

    def insert(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Insert a new password_reset_tokens row and flush (no commit).

        Args:
            user_id: UUID of the user requesting the reset.
            token_hash: sha256(raw_token).hexdigest() — NEVER the raw token.
            expires_at: Timezone-aware UTC expiry datetime.

        Returns:
            Flushed PasswordResetToken ORM instance with .id assigned.
        """
        logger.debug(
            "auth.repo.password_reset.insert.start user_id=%s",
            str(user_id),
        )  # BEFORE — never log token_hash
        prt = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(prt)
        self._session.flush()
        logger.debug(
            "auth.repo.password_reset.insert.done user_id=%s prt_id=%s",
            str(user_id),
            str(prt.id),
        )  # AFTER
        return prt

    def find_active_by_hash_for_update(
        self, token_hash: str
    ) -> Optional[PasswordResetToken]:
        """Look up an active (not used, not expired) reset token WITH a row lock.

        Acquires SELECT ... FOR UPDATE to serialise concurrent reset attempts.
        The loser, after unblocking, will find used_at IS NOT NULL (one-use
        enforcement). Returns None for unknown, expired, or already-used tokens
        (the caller maps all three cases to 410 — no differentiation, per §H-reset-2).

        Args:
            token_hash: sha256(raw).hexdigest() — never the raw token.
                        NEVER log the full hash.

        Returns:
            PasswordResetToken ORM instance (locked) or None.
        """
        logger.debug(
            "auth.repo.password_reset.find_active_for_update.start hash_prefix=%s",
            token_hash[:8] + "...",
        )  # BEFORE — prefix only
        row = (
            self._session.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > func.now(),
            )
            .with_for_update()
            .first()
        )
        logger.debug(
            "auth.repo.password_reset.find_active_for_update.done found=%s",
            row is not None,
        )  # AFTER
        return row

    def find_by_hash(self, token_hash: str) -> Optional[PasswordResetToken]:
        """Look up a reset token row by hash (no lock, any state).

        Used for expiry-specific error differentiation (T12: expired vs T11: invalid).

        Args:
            token_hash: sha256(raw).hexdigest().

        Returns:
            PasswordResetToken (any state) or None if hash unknown.
        """
        logger.debug(
            "auth.repo.password_reset.find_by_hash.start hash_prefix=%s",
            token_hash[:8] + "...",
        )  # BEFORE
        row = (
            self._session.query(PasswordResetToken)
            .filter(PasswordResetToken.token_hash == token_hash)
            .first()
        )
        logger.debug(
            "auth.repo.password_reset.find_by_hash.done found=%s",
            row is not None,
        )  # AFTER
        return row

    def mark_used(self, token_id: uuid.UUID) -> None:
        """Mark a reset token as consumed (used_at = now()).

        Must be called within the same transaction as password update.

        Args:
            token_id: UUID of the password_reset_tokens row.
        """
        logger.debug(
            "auth.repo.password_reset.mark_used.start token_id=%s",
            str(token_id),
        )  # BEFORE
        self._session.query(PasswordResetToken).filter(
            PasswordResetToken.id == token_id
        ).update(
            {"used_at": datetime.now(tz=timezone.utc)},
            synchronize_session="fetch",
        )
        logger.debug(
            "auth.repo.password_reset.mark_used.done token_id=%s",
            str(token_id),
        )  # AFTER
