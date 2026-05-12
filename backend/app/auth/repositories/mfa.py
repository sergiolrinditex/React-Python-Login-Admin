"""
Hilo People — MFA TOTP secret data layer + in-memory challenge replay store.

Slice:  P01-S02-T006 — POST /api/v1/auth/2fa/verify
Phase:  P01 Auth + Data Foundation
Purpose: Two responsibilities kept in one file intentionally (both are ≤80 LOC total
         and are always co-deployed together — splitting would violate KISS for tiny code):
           1. MfaRepository — read mfa_totp_secrets rows by user_id.
           2. ChallengeReplayStore — in-memory jti consume tracking (threading.Lock dict)
              to implement one-shot MFA challenge consumption (D-MFA-REPLAY).

         WRITE_SET_DRIFT §D-MFA1.B — declared in task pack §I.

Key deps:
  - sqlalchemy==2.0.49 — Session
  - app.db.models.auth.MfaTotpSecret — ORM model
  - threading — Lock for replay store concurrency
  - time — monotonic for TTL cleanup

Source refs:
  - task pack P01-S02-T006 §F.1 (D-MFA-REPLAY — in-memory jti store)
  - task pack P01-S02-T006 §D.B, §I Files Created table
  - TECHNICAL_GUIDE §10.3 mfa_totp_secrets schema
  - 01-non-negotiables.md §Database, §Logging (BEFORE/AFTER/ERROR)

Decisions:
  - D-MFA-REPLAY: in-memory dict _consumed_jtis: dict[str, float] (jti → epoch expiry),
    guarded by threading.Lock. Opportunistic cleanup on every insert.
    Single-worker invariant until P02-S02-T001 Redis upgrade.
  - TODO(P02-S02-T001): Replace with Redis SETNX + TTL for multi-worker safety.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.auth import MfaTotpSecret

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MfaRepository — DB read layer
# ---------------------------------------------------------------------------

class MfaRepository:
    """Data-layer operations for mfa_totp_secrets table.

    Args:
        session: Active SQLAlchemy sync Session.
    """

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: SQLAlchemy sync Session for DB operations.
        """
        self._session = session

    def find_enabled_by_user_id(self, user_id: uuid.UUID) -> Optional[MfaTotpSecret]:
        """Load the mfa_totp_secrets row for the given user if enabled=true.

        Args:
            user_id: UUID of the user whose TOTP secret to look up.

        Returns:
            MfaTotpSecret ORM instance if found and enabled=true, else None.
        """
        logger.debug(
            "auth.repo.mfa.find_enabled.start user_id=%s",
            str(user_id),
        )  # BEFORE
        row = (
            self._session.query(MfaTotpSecret)
            .filter(
                MfaTotpSecret.user_id == user_id,
                MfaTotpSecret.enabled.is_(True),
            )
            .first()
        )
        found = row is not None
        logger.debug(
            "auth.repo.mfa.find_enabled.done user_id=%s found=%s",
            str(user_id),
            found,
        )  # AFTER
        return row


# ---------------------------------------------------------------------------
# ChallengeReplayStore — in-memory jti consume tracker (D-MFA-REPLAY)
# ---------------------------------------------------------------------------

class ChallengeReplayStore:
    """In-memory singleton for one-shot MFA challenge jti consumption.

    Tracks consumed mfa_challenge_token jtis with their expiry epoch so that
    a second POST to /2fa/verify with the same challenge token returns 401.

    Thread-safe: guarded by a threading.Lock.
    Single-worker invariant: state is per-process. Multi-worker deployments
    need Redis SETNX. TODO(P02-S02-T001).

    Usage:
        store = ChallengeReplayStore.instance()
        if store.is_consumed(jti, now=exp):
            raise MfaReplayError()
        # ... verify TOTP ...
        store.consume(jti, exp_epoch)
    """

    _singleton: Optional["ChallengeReplayStore"] = None
    _singleton_lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize internal state (not called directly — use instance())."""
        self._consumed: dict[str, float] = {}  # jti → epoch expiry
        self._lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ChallengeReplayStore":
        """Return the process-singleton ChallengeReplayStore."""
        if cls._singleton is None:
            with cls._singleton_lock:
                if cls._singleton is None:
                    cls._singleton = cls()
        return cls._singleton

    def is_consumed(self, jti: str) -> bool:
        """Return True if jti was already consumed and its expiry is in the future.

        Args:
            jti: JWT jti claim from the mfa_challenge_token.

        Returns:
            True if already consumed (replay), False if first use or expired entry.
        """
        now = time.time()
        with self._lock:
            exp = self._consumed.get(jti)
            return exp is not None and now < exp

    def consume(self, jti: str, exp_epoch: float) -> None:
        """Mark jti as consumed with TTL = exp_epoch + 60s safety margin.

        Also opportunistically prunes expired entries.

        Args:
            jti: JWT jti claim.
            exp_epoch: JWT exp claim as Unix timestamp (float).
        """
        now = time.time()
        ttl_exp = exp_epoch + 60.0  # safety margin
        with self._lock:
            # Opportunistic cleanup
            expired_keys = [k for k, v in self._consumed.items() if now >= v]
            for k in expired_keys:
                del self._consumed[k]
            self._consumed[jti] = ttl_exp
        logger.debug(
            "auth.repo.mfa.replay_store.consumed jti_prefix=%s",
            jti[:8] + "...",
        )  # AFTER — never log full jti
