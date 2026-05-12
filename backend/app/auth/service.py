"""
Hilo People — Auth service-layer compat shim.

Slice:  P01-S02-T002 (debugger cycle 1).
Purpose: Backward-compatible re-export of `SignUpUser` and `SignInUser` from
         the new `services/` package. Existing imports `from app.auth.service
         import SignUpUser, SignInUser` keep working. New code should import
         from `app.auth.services` (or the concrete `app.auth.services.sign_up
         / sign_in` modules).

Submodules:
  - app.auth.services.sign_up — SignUpUser, SignUpResult
  - app.auth.services.sign_in — SignInUser, SignInResult
"""

from app.auth.services import (
    SignInResult,
    SignInUser,
    SignUpResult,
    SignUpUser,
)

__all__ = [
    "SignInResult",
    "SignInUser",
    "SignUpResult",
    "SignUpUser",
]
