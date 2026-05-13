"""
Hilo People — Fernet AEAD encryption service for AI/MCP provider credentials.

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: Provides encrypt_secret / decrypt_secret using Fernet (AES-128-CBC +
         HMAC-SHA256) keyed by the ENCRYPTION_KEY env var. This is separate
         from MFA_ENCRYPTION_KEY (used by verification_data/crypto.py for TOTP
         secrets). The blast-radius isolation is intentional — see R2 in the
         task pack.

         Future consumers:
           - P02-S05-T001: ai_provider_credentials.encrypted_secret
           - P02-S07-T001: mcp_credentials.encrypted_secret + encrypted_refresh_token

Key deps:
  - cryptography==48.0.0 (already pinned — cryptography.fernet.Fernet)
  - ENCRYPTION_KEY env var — must be a valid Fernet key (32-byte url-safe base64)

Source refs:
  - task pack P02-S02-T001 §R2 (key split rationale)
  - 01-non-negotiables.md §Security/External provider keys (Fernet AEAD, never plaintext)
  - TECHNICAL_GUIDE §10.3 (ai_provider_credentials.encrypted_secret)

Decisions:
  - D-ENC1: Lazy key validation — the Fernet instance is created on first
    call (not at module import) to avoid import-time failures in code that
    imports the module but never calls encrypt/decrypt (e.g., test files
    that only test encryption by monkeypatching ENCRYPTION_KEY).
  - D-ENC2: Placeholder detection — 'replace-with-dev-key' (from .env.example)
    is explicitly checked because Fernet would raise a generic ValueError
    that is not user-friendly.
  - D-ENC3: NEVER log plaintext, ciphertext, or any portion of the key.
  - TODO(P04 hardening): Key rotation via ENCRYPTION_KEY_PREVIOUS env var —
    dual-decrypt window, then batch re-encrypt, then decommission old key.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.security.errors import EncryptionError, EncryptionKeyError

logger = logging.getLogger(__name__)

_PLACEHOLDER = "replace-with-dev-key"
_KEY_ENV = "ENCRYPTION_KEY"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Load ENCRYPTION_KEY and return a cached Fernet instance.

    Called lazily on first encrypt/decrypt call. Cached via lru_cache so
    the key is read once per process life (no per-call env lookup overhead).

    Returns:
        Fernet instance ready to encrypt/decrypt.

    Raises:
        EncryptionKeyError: If ENCRYPTION_KEY is missing, placeholder, or
            not a valid 32-byte url-safe base64 Fernet key.
    """
    raw = os.getenv(_KEY_ENV, "")

    logger.debug("security.encryption.load_key key_env=%s present=%s", _KEY_ENV, bool(raw))  # BEFORE

    if not raw:
        msg = (
            f"{_KEY_ENV} environment variable is not set. "
            "Generate one with: "
            "python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        logger.error("security.encryption.load_key.failed reason=missing_key")
        raise EncryptionKeyError(msg)

    if raw == _PLACEHOLDER:
        msg = (
            f"{_KEY_ENV} is set to the placeholder value '{_PLACEHOLDER}'. "
            "Replace it with a valid Fernet key. "
            "Generate one with: "
            "python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        logger.error("security.encryption.load_key.failed reason=placeholder_key")
        raise EncryptionKeyError(msg)

    try:
        key_bytes = raw.encode() if isinstance(raw, str) else raw
        f = Fernet(key_bytes)
        logger.debug("security.encryption.load_key.ok")  # AFTER
        return f
    except (ValueError, Exception) as exc:
        msg = (
            f"{_KEY_ENV} is not a valid Fernet key: {exc}. "
            "Fernet requires a 32-byte url-safe base64 encoded key. "
            "Generate one with: "
            "python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        logger.error("security.encryption.load_key.failed reason=invalid_key error=%s", exc)
        raise EncryptionKeyError(msg) from exc


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plain-text secret with Fernet (AES-128-CBC + HMAC-SHA256).

    The encrypted value is url-safe base64 and safe for TEXT DB columns.
    Uses random IV per call — two calls with the same input produce different
    ciphertexts (both decrypt correctly).

    Args:
        plaintext: Plain-text secret (e.g. API key, OAuth token).

    Returns:
        Fernet token as a UTF-8 string (url-safe base64).

    Raises:
        EncryptionKeyError: If ENCRYPTION_KEY is invalid (propagated from _get_fernet).
        EncryptionError: If encryption fails for any other reason.
    """
    logger.debug("security.encryption.encrypt.start length=%d", len(plaintext))  # BEFORE

    try:
        f = _get_fernet()
        token = f.encrypt(plaintext.encode()).decode()
        logger.debug("security.encryption.encrypt.ok")  # AFTER — no token value logged
        return token
    except EncryptionKeyError:
        raise
    except Exception as exc:
        logger.error("security.encryption.encrypt.error error=%s", type(exc).__name__)
        raise EncryptionError("Encryption failed", cause=exc) from exc


def decrypt_secret(token: str) -> str:
    """Decrypt a Fernet-encrypted secret token.

    Args:
        token: Fernet token string (from encrypt_secret).

    Returns:
        Decrypted plain-text string.

    Raises:
        EncryptionKeyError: If ENCRYPTION_KEY is invalid.
        EncryptionError: If token is corrupt, tampered, or expired.
    """
    logger.debug("security.encryption.decrypt.start")  # BEFORE — no token value logged

    try:
        f = _get_fernet()
        plaintext = f.decrypt(token.encode()).decode()
        logger.debug("security.encryption.decrypt.ok length=%d", len(plaintext))  # AFTER
        return plaintext
    except EncryptionKeyError:
        raise
    except InvalidToken as exc:
        logger.error("security.encryption.decrypt.error reason=invalid_token")
        raise EncryptionError("Decryption failed: token is invalid or corrupted", cause=exc) from exc
    except Exception as exc:
        logger.error("security.encryption.decrypt.error error=%s", type(exc).__name__)
        raise EncryptionError("Decryption failed", cause=exc) from exc


def reset_fernet_cache() -> None:
    """Clear the lru_cache on _get_fernet.

    Used in tests that monkeypatch ENCRYPTION_KEY between test cases.
    Production code should never call this.
    """
    _get_fernet.cache_clear()
