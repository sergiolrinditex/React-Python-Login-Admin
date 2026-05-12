"""
Hilo People — Auth services package (use cases).

Slice:  P01-S02-T002 (debugger cycle 1 — split per validator F2).
        P01-S02-T003 — added RefreshTokenUser, RefreshResult.
Phase:  P01 Auth + Data Foundation
Purpose: One module per use case, per non-negotiables §File size
         ("1 use case per file"). Re-exported here so existing callers keep
         the short `from app.auth.services import SignUpUser` form working.

Submodules:
  - sign_up.py  — SignUpUser, SignUpResult (P01-S02-T001)
  - sign_in.py  — SignInUser, SignInResult (P01-S02-T002)
  - refresh.py  — RefreshTokenUser, RefreshResult (P01-S02-T003)
"""

from app.auth.services.refresh import RefreshResult, RefreshTokenUser
from app.auth.services.sign_in import SignInResult, SignInUser
from app.auth.services.sign_up import SignUpResult, SignUpUser

__all__ = [
    "RefreshResult",
    "RefreshTokenUser",
    "SignInResult",
    "SignInUser",
    "SignUpResult",
    "SignUpUser",
]
