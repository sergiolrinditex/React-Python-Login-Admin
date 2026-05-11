"""
Hilo People — Log redaction helpers for verification data.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: Provides utilities for redacting sensitive fields before logging.
         Keeps secrets (passwords, tokens, MFA secrets, API keys) out of logs.
         Follows the redaction rules mandated by §10.5 of the TECHNICAL_GUIDE
         and §01-non-negotiables.md §Logging.

Key deps: None (stdlib only)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.5 logging redaction
  - 01-non-negotiables.md §Logging — Never log tokens, passwords, or PII.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Fields that MUST be redacted entirely (replaced with "***REDACTED***")
# ---------------------------------------------------------------------------
_REDACTED_KEYS = frozenset(
    {
        "password",
        "password_plain",
        "password_hash",
        "token",
        "refresh_token",
        "access_token",
        "secret",
        "encrypted_secret",
        "mfa_totp_secret",
        "totp_secret",
        "api_key",
        "credential_plain",
        "secret_encrypted",
    }
)


def mask_email(email: str) -> str:
    """Return a masked email address for safe logging.

    Masks everything before the '@' except the first character.
    Example: 'employee@inditex.com' → 'e***@inditex.com'

    Args:
        email: Raw email string.

    Returns:
        Masked email safe for log output.
    """
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


def redact_dict(data: dict[str, Any], *, depth: int = 0) -> dict[str, Any]:
    """Return a copy of data with all sensitive fields replaced by '***REDACTED***'.

    Recurses into nested dicts but stops at depth 5 to prevent infinite loops.
    List values are NOT recursed (emails within lists remain unmasked).

    Args:
        data:  Dictionary to redact (e.g. fixture JSON object).
        depth: Current recursion depth (internal use).

    Returns:
        New dict with sensitive fields replaced by '***REDACTED***'.
    """
    if depth > 5:
        return {"_truncated": True}

    result: dict[str, Any] = {}
    for key, value in data.items():
        lower_key = key.lower()
        if lower_key in _REDACTED_KEYS:
            result[key] = "***REDACTED***"
        elif lower_key in ("email", "user_email_ref"):
            # Mask emails — not fully redacted but anonymised.
            result[key] = mask_email(str(value)) if isinstance(value, str) else value
        elif isinstance(value, dict):
            result[key] = redact_dict(value, depth=depth + 1)
        else:
            result[key] = value
    return result
