"""
Hilo People — JWT token encoding/decoding for auth endpoints.

Slice:  P01-S02-T002 — POST /api/v1/auth/sign-in (initial)
        P02-S02-T002 — Fix module-level _JWT_KEY lazy getter (import-order-resilient)
Phase:  P01 Auth + Data Foundation / P02 Core Features
Purpose: Thin wrapper around PyJWT==2.12.1 for encoding and decoding the
         JWT tokens used by the auth module:
           - Access tokens (short-lived, HS256, full claims set)
           - MFA challenge tokens (very short-lived, purpose-scoped)
         Decode is used by downstream endpoints (2FA verify, protected routes).

Key deps:
  - PyJWT==2.12.1 — jwt.encode / jwt.decode
  - app.db.models.user.User — source of claims for access tokens
  - os — JWT_PRIVATE_KEY, JWT_ALGORITHM env vars
  - functools.lru_cache — lazy singleton getter for JWT_PRIVATE_KEY

Source refs:
  - TECHNICAL_GUIDE §10.2 (JWT strategy, claims set: sub/email/roles/preferred_language/
    employee_profile_id/iat/exp/jti)
  - task pack §F.2 (mfa_challenge claims: sub/purpose/iat/exp/jti TTL 300s)
  - task pack §F.5, §F.6 (access TTL 1800s via AUTH_ACCESS_TTL_SECONDS)
  - official-doc-notes/P01-S02-T002-pyjwt-cookies-argon2.md RESOLVED
    (PyJWT==2.12.1, encode returns str, HS256 key ≥32 bytes,
     datetime for iat/exp, uuid4().hex for jti)
  - 01-non-negotiables.md §Security (no tokens in logs)
  - task pack P02-S02-T002 §F.3 (lru_cache Option A; mirrors app/security/encryption.py)

Decisions:
  - D-TK1: HS256 with shared secret (JWT_PRIVATE_KEY) for V1. Algorithm kept
    symmetric for simplicity; upgrade path to RS256 documented here.
    To upgrade: generate RSA key pair, set JWT_PRIVATE_KEY=PEM private key,
    JWT_PUBLIC_KEY=PEM public key, change JWT_ALGORITHM=RS256 in env.
  - D-TK2: `iat`/`exp` set as Python datetime objects — PyJWT 2.x accepts
    datetime and serialises to int internally. Cleaner code than manual int().
  - D-TK3: `jti` = uuid4().hex — RFC 7519 §4.1.7 compliant; 32-char hex;
    no server-side deny-list for V1 (access tokens are short-lived;
    refresh token rotation via refresh_tokens.revoked_at handles revocation).
  - D-TK4: NEVER log the returned token strings. Callers must enforce this.
  - D-TK5: employee_profile_id may be None for users without a profile row.
    Serialised as None (null in JSON); downstream guards must handle.
  - D-TK6 (P02-S02-T002): JWT_PRIVATE_KEY is now read lazily via _get_jwt_key()
    (lru_cache, maxsize=1). The getter raises RuntimeError on empty env so the
    cache never pins "". Mirrors app/security/encryption.py:_get_fernet() pattern.
    _JWT_ALGORITHM / _ACCESS_TTL / _MFA_CHALLENGE_TTL remain at-import (KISS/YAGNI;
    no fixture rotates them in any test).
  - D-TK7 (P02-S02-T002): At-import advisory warnings (missing / too_short) are
    preserved for prod-ops visibility. They read os.getenv into a local _startup_key
    variable which is del'ed afterwards — no closure kept, no interference with the
    lazy getter.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import jwt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT configuration from environment (static constants — not rotated at runtime)
# ---------------------------------------------------------------------------
_JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
_ACCESS_TTL: int = int(os.getenv("AUTH_ACCESS_TTL_SECONDS", "1800"))
_MFA_CHALLENGE_TTL: int = int(os.getenv("AUTH_MFA_CHALLENGE_TTL_SECONDS", "300"))


# ---------------------------------------------------------------------------
# Lazy JWT key getter (P02-S02-T002 fix)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_jwt_key() -> str:
    """Read JWT_PRIVATE_KEY lazily; raises RuntimeError if missing or empty.

    Lazy so that pytest fixtures / dev tooling that set the env var AFTER the
    first module import still work — the getter is only called on the first
    real encode/decode, not at import time. Cached (lru_cache maxsize=1) for a
    stable per-process value after the first successful read.

    Mirrors app/security/encryption.py:_get_fernet() (D-TK6).

    NEVER log the returned value. The key is a secret.

    Returns:
        Non-empty JWT signing key string from JWT_PRIVATE_KEY env var.

    Raises:
        RuntimeError: If JWT_PRIVATE_KEY env var is empty or missing at
                      the time of the first call.
    """
    key = os.getenv("JWT_PRIVATE_KEY", "")
    if not key:
        raise RuntimeError(
            "JWT_PRIVATE_KEY env var is not set; "
            "JWT encoding/decoding will not work. "
            "Set the variable and restart, or call _clear_jwt_key_cache() after setting it."
        )
    verbose = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"
    if verbose:
        logger.debug(
            "tokens.jwt_key.resolved bytes=%d",
            len(key.encode()),
        )
    return key


def _clear_jwt_key_cache() -> None:
    """Clear the lru_cache for _get_jwt_key().

    Test-only helper: call this after rotating JWT_PRIVATE_KEY in os.environ
    to force the next call to _get_jwt_key() to re-read the env var.
    Also useful in dev tooling (e.g. gen-dev-secrets.sh rotation workflows).

    Example:
        os.environ["JWT_PRIVATE_KEY"] = new_key
        _clear_jwt_key_cache()
        # Next encode/decode will use new_key.
    """
    logger.debug("tokens.jwt_key.cache_cleared")
    _get_jwt_key.cache_clear()


# ---------------------------------------------------------------------------
# At-import advisory warnings (preserved for prod-ops / startup observability)
# D-TK7: reads env into a LOCAL variable, then del's it — no closure kept,
# no interference with _get_jwt_key() lazy cache.
# ---------------------------------------------------------------------------
_startup_key: str = os.getenv("JWT_PRIVATE_KEY", "")
if not _startup_key:
    logger.warning(
        "tokens.jwt_key.missing JWT_PRIVATE_KEY env var is not set; "
        "JWT encoding will raise at runtime"
    )
elif len(_startup_key.encode()) < 32:
    logger.warning(
        "tokens.jwt_key.too_short JWT_PRIVATE_KEY is %d bytes; "
        "RFC 7518 §3.2 requires ≥32 bytes for HS256",
        len(_startup_key.encode()),
    )
del _startup_key  # no closure; do not keep a reference to the secret


def encode_access_token(user: Any, ttl: int | None = None) -> str:
    """Encode a JWT access token for a fully authenticated user.

    Claims per §10.2: sub, email, roles, preferred_language,
    employee_profile_id, iat, exp, jti.

    Args:
        user: User ORM instance (must have .id, .email, .preferred_language,
              .employee_profile_id attributes). Role list built from user.roles
              relationship if populated; defaults to ['employee'].
        ttl: Token TTL in seconds. Defaults to AUTH_ACCESS_TTL_SECONDS env.

    Returns:
        Encoded JWT string (HS256). NEVER log this value.

    Raises:
        jwt.PyJWTError: On encoding failure (e.g. missing key).
    """
    effective_ttl = ttl if ttl is not None else _ACCESS_TTL
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(seconds=effective_ttl)

    # Build roles list: use relationship if loaded, else default to 'employee'
    roles: list[str] = []
    if hasattr(user, "user_roles") and user.user_roles:
        for ur in user.user_roles:
            if hasattr(ur, "role") and ur.role and hasattr(ur.role, "name"):
                roles.append(ur.role.name)
    if not roles:
        roles = ["employee"]

    # employee_profile_id may be None (no profile row yet for this user)
    emp_profile_id: str | None = None
    if hasattr(user, "employee_profile_id") and user.employee_profile_id:
        emp_profile_id = str(user.employee_profile_id)

    payload: dict[str, Any] = {
        "sub": str(user.id),
        "email": user.email,
        "roles": roles,
        "preferred_language": getattr(user, "preferred_language", "es") or "es",
        "employee_profile_id": emp_profile_id,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": exp,
    }

    logger.debug("tokens.encode_access.start sub=%s ttl=%ds", str(user.id), effective_ttl)  # BEFORE
    token: str = jwt.encode(payload, _get_jwt_key(), algorithm=_JWT_ALGORITHM)
    logger.debug("tokens.encode_access.done sub=%s exp=%s", str(user.id), exp.isoformat())  # AFTER
    return token


def encode_mfa_challenge_token(user_id: uuid.UUID, ttl: int | None = None) -> str:
    """Encode a short-lived JWT MFA challenge token.

    Claims: sub, purpose="mfa_challenge", iat, exp, jti.
    Consumed by POST /api/v1/auth/2fa/verify (T006) which must verify
    that purpose=="mfa_challenge" before accepting the token.

    Args:
        user_id: UUID of the user requiring MFA verification.
        ttl: Challenge TTL in seconds. Defaults to AUTH_MFA_CHALLENGE_TTL_SECONDS env.

    Returns:
        Encoded JWT string (HS256). NEVER log this value.

    Raises:
        jwt.PyJWTError: On encoding failure.
    """
    effective_ttl = ttl if ttl is not None else _MFA_CHALLENGE_TTL
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(seconds=effective_ttl)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "purpose": "mfa_challenge",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": exp,
    }

    logger.debug(
        "tokens.encode_mfa_challenge.start user_id=%s ttl=%ds",
        str(user_id),
        effective_ttl,
    )  # BEFORE
    token: str = jwt.encode(payload, _get_jwt_key(), algorithm=_JWT_ALGORITHM)
    logger.debug(
        "tokens.encode_mfa_challenge.done user_id=%s exp=%s",
        str(user_id),
        exp.isoformat(),
    )  # AFTER
    return token


def decode_token(
    token: str,
    expected_purpose: str | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Validates signature, expiry, and required claims (exp, iat, sub, jti).
    Optionally checks that `purpose` claim matches `expected_purpose`.

    Args:
        token: Encoded JWT string.
        expected_purpose: If set, raises ValueError if token.purpose != expected_purpose.
                          Use "mfa_challenge" when validating MFA challenge tokens.

    Returns:
        Decoded payload dict.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token signature invalid or malformed.
        jwt.MissingRequiredClaimError: Required claim (exp/iat/sub/jti) missing.
        ValueError: `purpose` claim does not match expected_purpose.
    """
    logger.debug("tokens.decode.start")  # BEFORE — no token value in log
    decoded: dict[str, Any] = jwt.decode(
        token,
        _get_jwt_key(),
        algorithms=[_JWT_ALGORITHM],
        options={"require": ["exp", "iat", "sub", "jti"]},
    )
    if expected_purpose is not None and decoded.get("purpose") != expected_purpose:
        logger.warning(
            "tokens.decode.purpose_mismatch expected=%s got=%s",
            expected_purpose,
            decoded.get("purpose"),
        )
        raise ValueError(
            f"Token purpose mismatch: expected '{expected_purpose}', "
            f"got '{decoded.get('purpose')}'"
        )
    logger.debug("tokens.decode.ok sub=%s", decoded.get("sub"))  # AFTER
    return decoded
