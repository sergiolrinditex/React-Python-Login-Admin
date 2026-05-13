"""
Hilo People — Public API for the security module.

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: Re-exports the public surface of app.security for use by other modules
         (llm_gateway, mcp, admin, future features). Consumers import from
         app.security directly instead of from submodules.

         This module has no router.py / service.py / schemas.py (per D-S2-T001-D1
         in task pack): it is pure library code providing reusable primitives,
         not an HTTP feature module.

Key deps:
  - app.security.encryption  — encrypt_secret, decrypt_secret
  - app.security.permissions — require_user, require_role, require_admin, require_auditor
  - app.security.rate_limit  — RateLimiter
  - app.security.errors      — typed domain errors
"""

from app.security.encryption import decrypt_secret, encrypt_secret, reset_fernet_cache
from app.security.errors import (
    EncryptionError,
    EncryptionKeyError,
    PermissionDeniedError,
    RateLimitedError,
    SecurityError,
)
from app.security.permissions import (
    require_admin,
    require_auditor,
    require_role,
    require_user,
)
from app.security.rate_limit import RateLimiter

__all__ = [
    # Encryption
    "encrypt_secret",
    "decrypt_secret",
    "reset_fernet_cache",
    # Permissions
    "require_user",
    "require_role",
    "require_admin",
    "require_auditor",
    # Rate limiting
    "RateLimiter",
    # Errors
    "SecurityError",
    "EncryptionKeyError",
    "EncryptionError",
    "PermissionDeniedError",
    "RateLimitedError",
]
