"""
Hilo People — Argon2id password hashing wrapper.

Slice:  P01-S02-T001 — POST /api/v1/auth/sign-up
Phase:  P01 Auth + Data Foundation
Purpose: Thin, testable wrapper around argon2-cffi PasswordHasher.
         Encapsulates Argon2id configuration in one place so every auth slice
         (sign-up, sign-in, reset) imports from here and never duplicates params.

Key deps:
  - argon2-cffi==25.1.0 — Argon2id password hashing
  - app.auth.errors — (unused here; callers handle VerifyMismatchError)

Source refs:
  - TECHNICAL_GUIDE §10.2 "Passwords hashed with Argon2"
  - task pack §F.3 Argon2 parameters (library defaults EXCEED OWASP 2026 minimums)
  - official-doc-notes/P01-S02-T001-argon2-owasp-params-2026-05-11.md (RESOLVED:
    argon2-cffi 25.1.0 PasswordHasher() defaults EXCEED OWASP 2026 Argon2id
    minimums — 64 MiB / t=3 / p=4 vs 12 MiB / t=3 / p=1 minimum)
  - official-doc-notes/P00-S02-T003-argon2-cffi-2026-05-11.md (RESOLVED:
    argon2-cffi==25.1.0, API: hash/verify/check_needs_rehash; no verify_and_update)

Decisions:
  - Library defaults used: time_cost=3, memory_cost=65536 (64 MiB),
    parallelism=4, hash_len=32, salt_len=16. These EXCEED OWASP 2026 Argon2id
    minimums (closest minimum config: m=12288 KiB / t=3 / p=1) — defaults use
    5x more memory and 4x parallelism. Source: official-doc-notes/
    P01-S02-T001-argon2-owasp-params-2026-05-11.md RESOLVED.
  - check_needs_rehash is called at sign-in (T002), not here.
  - NEVER log plain text password or hash value. Callers must also enforce this.
"""

from __future__ import annotations

import logging

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level PasswordHasher singleton — created once, thread-safe, reused.
# Defaults: Argon2id, time_cost=3, memory_cost=65536 KiB (64 MiB),
#           parallelism=4, hash_len=32, salt_len=16.
# NOTE: These defaults EXCEED OWASP 2026 Argon2id minimums. OWASP requires
# at minimum m=12288 KiB (12 MiB) at t=3,p=1. The argon2-cffi defaults use
# 5x more memory and 4x the parallelism — production-grade and well above
# minimums. Source: OWASP Password Storage Cheat Sheet §Argon2id (2026),
# official-doc-notes/P01-S02-T001-argon2-owasp-params-2026-05-11.md RESOLVED.
# ---------------------------------------------------------------------------
_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    """Hash a plain-text password with Argon2id.

    Args:
        plain: The raw password string. NEVER log this value.

    Returns:
        The PHC-formatted Argon2id hash string (starts with '$argon2id$').

    Raises:
        Exception: Unexpected argon2-cffi error (should not occur in practice).

    Security note: the returned hash is safe to store in `users.password_hash`.
    Do NOT log it — it contains the salt and can be subject to offline attacks
    if leaked.
    """
    logger.debug("password.hash.start")  # BEFORE — no plain in log
    result = _ph.hash(plain)
    logger.debug("password.hash.done")  # AFTER — no hash value in log
    return result


def verify_password(stored_hash: str, plain: str) -> bool:
    """Verify a plain-text password against a stored Argon2id hash.

    Used at sign-in (P01-S02-T002). Not called during sign-up.

    Args:
        stored_hash: The PHC-formatted Argon2id hash from `users.password_hash`.
        plain: The raw password attempt. NEVER log this value.

    Returns:
        True if the password matches the hash.

    Raises:
        VerifyMismatchError: Password does not match.
        VerificationError: Other verification failure (e.g. hash format issue).
        InvalidHashError: Hash string is malformed.
    """
    logger.debug("password.verify.start")  # BEFORE — no plain or hash in log
    try:
        _ph.verify(stored_hash, plain)
        logger.debug("password.verify.ok")  # AFTER
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        logger.debug("password.verify.mismatch")  # AFTER — no details (prevents timing leaks)
        raise


def needs_rehash(stored_hash: str) -> bool:
    """Check whether a stored hash needs to be upgraded to current parameters.

    Called at sign-in (P01-S02-T002) after successful verify. If True, the
    service layer re-hashes and updates `users.password_hash`.

    Args:
        stored_hash: The PHC-formatted Argon2id hash.

    Returns:
        True if the hash was generated with outdated parameters.
    """
    return _ph.check_needs_rehash(stored_hash)


# ---------------------------------------------------------------------------
# Dummy hash for user-enumeration mitigation (added P01-S02-T002)
# ---------------------------------------------------------------------------
# DUMMY_VERIFY_HASH is computed ONCE at module import time so the sign-in
# unknown-email path has a valid Argon2id hash to call verify_password() against,
# making the wall-clock time of the "unknown email" path statistically
# indistinguishable from the "wrong password" path. Both paths call
# verify_password() and the Argon2 work dominates the timing.
#
# The constant plaintext "dummy-equaliser-not-a-real-password-12345" can never
# appear as a user password (it does not meet sign-up policy) and the hash is
# never stored in DB or returned in any response. NEVER log this value.
#
# Source: task pack §F.1, T001 service.py:208 pattern (hash_password on dupe-email path).
# Public symbol per validator P01-S02-T002 cycle 1 finding F4 (was `_DUMMY_HASH`,
# the underscore-prefixed private name leaked across module boundaries — now
# a public constant + a public helper `verify_with_dummy_fallback`).
DUMMY_VERIFY_HASH: str = hash_password("dummy-equaliser-not-a-real-password-12345")


def verify_with_dummy_fallback(stored_hash: str | None, plain: str) -> bool:
    """Verify a password against a real hash, or use the dummy hash when None.

    Centralises the aggregate-401 / anti-enumeration pattern for sign-in:
    callers MUST invoke this even when `find_by_email` returned None, so the
    wall-clock time of unknown-email and wrong-password paths is dominated by
    the same Argon2 verify call. The dummy hash never matches any real
    password, so this returns False on the unknown-email path.

    Args:
        stored_hash: The user's stored Argon2id hash, or None when the user
            was not found by find_by_email.
        plain: The raw password attempt. NEVER log this value.

    Returns:
        True if `stored_hash` is provided and matches `plain`. False in all
        other cases (no user, wrong password, malformed hash).

    Security note: callers MUST raise the SAME error code on both
    `stored_hash is None` and `verify failure` to avoid an enumeration oracle.
    This helper only equalises timing — it does not equalise the response.
    """
    target_hash = stored_hash if stored_hash is not None else DUMMY_VERIFY_HASH
    logger.debug("password.verify_with_dummy.start has_real_hash=%s", stored_hash is not None)
    try:
        _ph.verify(target_hash, plain)
        logger.debug("password.verify_with_dummy.ok")
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        logger.debug("password.verify_with_dummy.mismatch")
        return False
