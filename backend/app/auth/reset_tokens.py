"""
Hilo People — Reset token domain utilities (pure functions, no I/O).

Slice:  P01-S02-T005 — POST /api/v1/auth/forgot-password +
                       POST /api/v1/auth/reset-password
Phase:  P01 Auth + Data Foundation
Purpose: Generate and hash one-time URL-safe reset tokens. One responsibility:
         token generation + hashing. No DB, no mail, no HTTP concerns.

Key deps:
  - secrets (stdlib) — CSPRNG for URL-safe token bytes
  - hashlib  (stdlib) — SHA-256 for DB storage (token already has 256-bit entropy)

Security:
  - Token raw value: secrets.token_urlsafe(32) → ~43 URL-safe chars,
    256 bits of entropy (CSPRNG).
  - DB stores sha256(raw).hexdigest() — 64 hex chars. The hash is a
    defence-in-depth measure against a DB-dump leaking live tokens;
    it provides no additional entropy (token is already 256 bits, so
    sha256 is NOT stretched — HMAC/PBKDF2 would be redundant).
    Source: OWASP Authentication Cheat Sheet §Password Reset Process
            (plain sha256 is the recommended pattern when the token itself
             is a CSPRNG byte string of ≥128 bits).
  - NEVER log the raw token. Log only prefixes for correlation when needed.

Source refs:
  - task pack §H 6 (token format), §H-reset-7 (one-use), §I-5 (util file)
  - TECHNICAL_GUIDE §10.2 (auth strategy — reset token is opaque, NOT JWT)
  - 01-non-negotiables.md §Security (OWASP top 10, A02)
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone


def generate_raw_token() -> str:
    """Generate a cryptographically secure URL-safe reset token.

    Returns:
        ~43-character URL-safe base64 string (256-bit entropy).
        This raw value is emailed to the user and MUST NOT be stored in DB.
        Use hash_token() to get the DB-safe digest.
    """
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    """Compute the SHA-256 hex digest of a raw reset token for DB storage.

    Args:
        raw: The URL-safe raw token returned by generate_raw_token().
             NEVER log this value.

    Returns:
        64-character lowercase hex string (SHA-256 digest).
        This is safe to store in password_reset_tokens.token_hash.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


def is_expired(expires_at: datetime) -> bool:
    """Check whether a token's expiry has passed.

    Args:
        expires_at: Timezone-aware UTC datetime from password_reset_tokens.

    Returns:
        True if the token is expired (expires_at <= now()).
    """
    now = datetime.now(tz=timezone.utc)
    # Make expires_at tz-aware if it arrives tz-naive from the DB driver
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now
