"""
Hilo People — MFA module re-export aggregator shim.

Slice:  P01-S02-T006 — POST /api/v1/auth/2fa/verify
Phase:  P01 Auth + Data Foundation
Purpose: The Coverage Registry `write_set` for T006 declares `backend/app/auth/mfa.py`
         as the canonical file. Clean Architecture forces the actual implementation
         to be split across routers/mfa.py + services/mfa.py + repositories/mfa.py
         + mfa_crypto.py (per non-negotiables §File size + §1 responsibility per file).
         This shim satisfies the literal write_set contract without violating those rules
         (same precedent as service.py compat shim in T002).

         Callers should prefer the direct module imports:
           from app.auth.services.mfa import VerifyMfaChallenge, VerifyMfaResult
           from app.auth.routers.mfa import mfa_router

         See WRITE_SET_DRIFT §D-MFA1.A–K and handoff §K for full rationale.

Key deps:
  - app.auth.services.mfa — VerifyMfaChallenge, VerifyMfaResult
  - app.auth.routers.mfa — mfa_router

WRITE_SET_DRIFT note: Per task pack §I "Decision: do NOT create a flat `mfa.py`.
If validator demands the literal file exist, a one-line re-export shim is acceptable."
This shim is that acceptable option.
"""

from app.auth.routers.mfa import mfa_router
from app.auth.services.mfa import VerifyMfaChallenge, VerifyMfaResult

__all__ = ["mfa_router", "VerifyMfaChallenge", "VerifyMfaResult"]
