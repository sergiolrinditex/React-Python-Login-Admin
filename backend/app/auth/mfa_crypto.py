"""
Hilo People — TOTP secret decryption facade for the auth module.

Slice:  P01-S02-T006 — POST /api/v1/auth/2fa/verify
Phase:  P01 Auth + Data Foundation
Purpose: Thin facade that exposes decrypt_totp_secret(encrypted) -> str for
         the auth module's production runtime, delegating to the shared
         verification_data.crypto.decrypt_secret implementation.

         Clean Architecture invariant: the auth module owns its decryption
         surface. verification_data/ is a bootstrap-time module (fixture loader);
         production runtime code must not have a direct runtime import from
         verification_data/. This one-line facade isolates the indirection in
         case we later replace Fernet with KMS.

         See WRITE_SET_DRIFT §D-MFA1.C and task pack §F.8 (D-MFA-CRYPTO).

Key deps:
  - app.verification_data.crypto.decrypt_secret — Fernet decrypt with MFA_ENCRYPTION_KEY
  - cryptography.fernet.Fernet — via verification_data.crypto (no direct import needed)
  - MFA_ENCRYPTION_KEY env var — must be a valid Fernet key (44-char base64-url)

Source refs:
  - task pack P01-S02-T006 §F.8 (D-MFA-CRYPTO)
  - TECHNICAL_GUIDE §C.7 (MFA Fernet encryption)
  - 01-non-negotiables.md §Security (secrets only in env vars)

Risks:
  - R3: MFA_ENCRYPTION_KEY placeholder in dev .env causes RuntimeError at decrypt.
    Verification step: python3 -c "from cryptography.fernet import Fernet; Fernet(os.environ['MFA_ENCRYPTION_KEY'].encode())"
    Documented in handoff §K.
"""

from __future__ import annotations

from app.verification_data.crypto import decrypt_secret as _decrypt_secret


def decrypt_totp_secret(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted TOTP base32 seed stored in mfa_totp_secrets.secret_encrypted.

    The decrypted string is a plain base32 TOTP seed (e.g. 'JBSWY3DPEHPK3PXP').
    Pass directly to pyotp.TOTP(secret_b32_str).verify(...).

    Args:
        encrypted: Fernet token string (from mfa_totp_secrets.secret_encrypted column).
                   Must NOT be logged — it is the encrypted TOTP seed.

    Returns:
        Decrypted base32 TOTP seed string. NEVER log this value.

    Raises:
        RuntimeError: If MFA_ENCRYPTION_KEY is not set or is not a valid Fernet key.
        cryptography.fernet.InvalidToken: If the encrypted token is corrupt or tampered.
    """
    return _decrypt_secret(encrypted)
