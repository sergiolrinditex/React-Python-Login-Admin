"""
Security helpers for Hilo People backend.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

IMPORTANT — P00 STUB CONTRACT:
  This module ships TWO kinds of functionality:

  1. Fernet encrypt/decrypt helpers (`encrypt_secret` / `decrypt_secret`):
     These are the REAL implementation, not a stub. Fernet is the
     production-grade cipher (AEAD) per 01-non-negotiables.md §Security
     and HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 line 431.
     Will be extended in P02-S02-T001 (Provider Key Management slice).

  2. `require_admin` FastAPI dependency:
     P00 STUB — verifies only that the Authorization header is present and
     starts with "Bearer dev-admin-". This gives enough coverage to write
     real auth tests (401 / 403 paths) while P01-S02 is still pending.
     REPLACED IN P01-S02-T001 with the real RS256 JWT verifier.
     The tests for 401/403 continue passing because the real implementation
     enforces a strict superset of this contract.

Key backward-compat note (P01-S01-T002 env var rename):
  The field was renamed PROVIDER_ENCRYPTION_KEY → ENCRYPTION_KEY in T002.
  The local .env file (gitignored, per-dev) may still have the old name.
  _resolve_fernet_key() tries ENCRYPTION_KEY first, then falls back to
  PROVIDER_ENCRYPTION_KEY, then settings.encryption_key. This lets the
  existing dev .env work without a manual update, while docker-compose
  (which sets the new name) works correctly.

Dependencies:
  - cryptography 48.0.0 (Fernet)
  - fastapi 0.136.1
  - app.core.config (get_settings)
  - app.core.logging (get_logger)

Security:
  - Cleartext keys never logged, never returned to caller, never persisted.
  - decrypt_secret() raises CryptoError on tamper/expiry — caller maps to 502.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException, status

from app.core.logging import get_logger

_logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Custom errors
# ---------------------------------------------------------------------------


class CryptoError(Exception):
    """Raised when Fernet decryption fails (tampered, expired, or wrong key).

    Purpose: typed error so callers can map to a 502 without catching generic
    Exception. The raw cryptography.fernet.InvalidToken is caught internally
    and wrapped here to keep the public surface stable.
    """


# ---------------------------------------------------------------------------
# Key resolution (dev-compat backward bridge — P01-S01-T002 rename)
# ---------------------------------------------------------------------------


def _resolve_fernet_key() -> bytes:
    """Return the Fernet key bytes from environment or settings.

    Resolution order (highest priority first):
      1. ENCRYPTION_KEY env var (canonical name after T002 rename)
      2. PROVIDER_ENCRYPTION_KEY env var (legacy dev .env — backward compat)
      3. settings.encryption_key (pydantic-settings resolved value)

    Returns: Fernet key as bytes.
    Raises: ValueError if no key is found in any source.

    Security: never log the key value. Log only 'key_source' (which env var
    was used) at debug level.
    """
    # Try canonical name first
    raw = os.environ.get("ENCRYPTION_KEY", "")
    key_source = "ENCRYPTION_KEY"

    if not raw:
        # Backward compat: dev .env may still have old name (T002 known issue)
        raw = os.environ.get("PROVIDER_ENCRYPTION_KEY", "")
        key_source = "PROVIDER_ENCRYPTION_KEY (legacy fallback)"

    if not raw:
        # Last resort: pydantic-settings (may have loaded from .env via config.py)
        from app.core.config import get_settings  # local import to avoid cycles

        raw = get_settings().encryption_key.get_secret_value()
        key_source = "settings.encryption_key"

    if not raw:
        raise ValueError(
            "No Fernet encryption key found. "
            "Set ENCRYPTION_KEY (or legacy PROVIDER_ENCRYPTION_KEY) env var."
        )

    _logger.debug("BEFORE _resolve_fernet_key: key resolved", key_source=key_source)
    return raw.encode()


# ---------------------------------------------------------------------------
# Fernet helpers (production-grade)
# ---------------------------------------------------------------------------


def encrypt_secret(plaintext: str) -> str:
    """Fernet-encrypt a plaintext credential and return the token string.

    Purpose: store AI provider API keys encrypted at rest per
    01-non-negotiables.md §Security (claves de proveedores externos).

    Params:
      plaintext — the API key or master key to encrypt.
    Returns: URL-safe base64 Fernet token string (safe to store in TEXT column).
    Raises: ValueError — if no encryption key is configured.
            Exception — any other cryptography error (propagated).

    Security: plaintext is never logged. Only success/failure status.
    """
    _logger.debug("BEFORE encrypt_secret: encrypting credential")
    key_bytes = _resolve_fernet_key()
    f = Fernet(key_bytes)
    token = f.encrypt(plaintext.encode()).decode()
    _logger.debug("AFTER encrypt_secret: credential encrypted successfully")
    return token


def decrypt_secret(token: str) -> str:
    """Fernet-decrypt an encrypted credential token and return the plaintext.

    Purpose: recover the API key for an in-flight discovery call. The
    cleartext lives only in the request scope and is never stored or logged.

    Params:
      token — Fernet token string as stored in ai_provider_credentials.encrypted_secret.
    Returns: decrypted plaintext string.
    Raises: CryptoError — if the token is tampered, expired, or the key is wrong.
            ValueError   — if no encryption key is configured.

    Security: plaintext NEVER logged. Error log contains only token length.
    """
    _logger.debug("BEFORE decrypt_secret: decrypting credential")
    key_bytes = _resolve_fernet_key()
    f = Fernet(key_bytes)
    try:
        plaintext = f.decrypt(token.encode()).decode()
    except InvalidToken as exc:
        _logger.warning(
            "ERROR decrypt_secret: Fernet InvalidToken",
            token_length=len(token),
            error_class="InvalidToken",
        )
        raise CryptoError("Credential decryption failed: invalid or expired token") from exc
    _logger.debug("AFTER decrypt_secret: credential decrypted successfully")
    return plaintext


# ---------------------------------------------------------------------------
# P00 auth guard stub — REPLACED IN P01-S02-T001
# ---------------------------------------------------------------------------
#
# This stub fulfils acceptance A4 (endpoint returns 401/403 for auth failures)
# while JWT infrastructure (P01-S02) is pending. It checks:
#   1. Authorization header is present → else 401
#   2. Token starts with "Bearer dev-admin-" → else 403
#
# Why a prefix rather than a full token? Keeps the stub deterministic for tests
# without requiring a real JWT keypair. The real implementation in P01-S02-T001
# will enforce RS256 signature + role=admin claim — a strict superset of this.
# Existing tests continue passing because they use "Bearer dev-admin-<anything>".


async def require_admin(
    authorization: str = Header(
        default="",
        alias="Authorization",
        description=(
            "P00 stub: 'Bearer dev-admin-<anything>'. "
            "Replaced by real RS256 verifier in P01-S02-T001."
        ),
    ),
) -> str:
    """FastAPI dependency: verify admin-level authorization (P00 stub).

    Purpose: gate admin_ai endpoints against unauthenticated/unauthorized
    requests. The stub checks header presence and a 'dev-admin-' prefix.
    Real JWT verification (RS256 + role=admin claim) arrives in P01-S02-T001.

    Params:
      authorization — value of the Authorization request header.
    Returns: the bearer token string (without 'Bearer ' prefix).
    Raises: HTTPException(401) — if Authorization header is absent or empty.
            HTTPException(403) — if token does not start with 'dev-admin-'.

    P00 stub lifecycle:
      Created: P00-S02-T006 (this slice)
      Replaced: P01-S02-T001 (real JWT verifier)
      Tests affected: test_admin_ai_discover_models.py auth suite
    """
    _logger.debug("BEFORE require_admin: checking authorization header")

    if not authorization or not authorization.startswith("Bearer "):
        _logger.warning("ERROR require_admin: Authorization header missing or malformed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "unauthorized", "message": "Authentication required."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    if not token.startswith("dev-admin-"):
        _logger.warning(
            "ERROR require_admin: non-admin token rejected",
            token_prefix=token[:10] if len(token) >= 10 else "<short>",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "forbidden",
                    "message": "Admin role required.",
                }
            },
        )

    _logger.debug("AFTER require_admin: admin token accepted")
    return token
