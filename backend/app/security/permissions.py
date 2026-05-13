"""
Hilo People — FastAPI permission guard factories (role-based access control).

Slice:  P02-S02-T001 — Security services (encryption, permissions, rate limit)
Phase:  P02 Core Features
Purpose: Provides re-usable FastAPI dependency factories for role-based
         authorization. Re-exports require_user from users.deps and adds:
           - require_role(role_name) → async FastAPI Depends factory
           - require_admin  = require_role("people_admin")  [§3.3]
           - require_auditor = require_role("people_auditor") [§3.3]

         super_admin is treated as a superset: any role guard passes when
         the user holds "super_admin" (D-PERM1).

         This module does NOT duplicate JWT decode logic — it delegates to
         users.deps.get_current_user which already handles Bearer extraction,
         JWT validation, DB lookup, and anti-enum 401 responses.

Key deps:
  - app.users.deps.get_current_user — existing Bearer dep (P01-S02-T007)
  - app.auth.routers._helpers._error_response — 403 envelope builder
  - app.auth.routers._helpers._get_request_id — X-Request-ID extraction
  - fastapi (Depends, Request)
  - fastapi.responses.JSONResponse

Source refs:
  - task pack P02-S02-T001 §R4 (re-export, no JWT decode duplication)
  - instrucciones.md §3.3 (canonical role names: employee, people_admin,
    people_auditor, super_admin)
  - TECHNICAL_GUIDE §10.2 (Guards: require_user, require_admin, require_auditor,
    require_role)

Decisions:
  - D-PERM1: super_admin is a superset — every require_role check also
    accepts super_admin so a super admin can perform any operation.
  - D-PERM2: 403 envelope reuses _error_response from auth/_helpers.py.
    A future refactor may move _error_response to app/shared/http/ (see
    handoff drift candidate D-S2-T001-A2). For now, import is transitive-clean:
    security → auth._helpers is acceptable because security does NOT depend on
    auth's business logic, only on a shared HTTP envelope helper.
  - D-PERM3: require_role returns a new async function per call (factory
    pattern). FastAPI identifies dependencies by object identity so each
    call to require_role("X") produces a distinct Depends target.

Note on role names: the canonical role names are from instrucciones.md §3.3
(people_admin, people_auditor, super_admin, employee). Tests create these
roles directly in the DB — they are NOT seeded by the verification data loader
in the current baseline.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from app.auth.routers._helpers import _error_response, _get_request_id
from app.db.models.user import User
from app.users.deps import get_current_user

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical role names (§3.3 instrucciones.md)
# ---------------------------------------------------------------------------
_SUPER_ADMIN_ROLE = "super_admin"
_PEOPLE_ADMIN_ROLE = "people_admin"
_PEOPLE_AUDITOR_ROLE = "people_auditor"

# Re-export get_current_user as require_user (§10.2 guard contract).
require_user = get_current_user


def require_role(role_name: str) -> Callable:
    """Factory: return an async FastAPI dependency requiring role_name.

    The returned dependency:
      - Delegates authentication to require_user (→ 401 on failure).
      - Checks that the authenticated user holds role_name OR super_admin.
      - Returns the User ORM instance on success.
      - Returns a JSONResponse 403 on authorization failure.

    Args:
        role_name: Required role name (e.g. 'people_admin', 'people_auditor').

    Returns:
        Async callable usable as FastAPI Depends target.
    """

    async def _guard(
        request: Request,
        user_or_response: User | JSONResponse = Depends(get_current_user),
    ) -> User | JSONResponse:
        """FastAPI dependency: verify authenticated user holds role_name.

        Args:
            request:          FastAPI Request (for X-Request-ID).
            user_or_response: Result from get_current_user dependency —
                              User ORM instance on success, JSONResponse 401
                              on authentication failure.

        Returns:
            User ORM instance on success; JSONResponse (401 or 403) on failure.
        """
        # Propagate authentication failure (401) from require_user.
        if isinstance(user_or_response, JSONResponse):
            logger.debug(
                "security.permissions.require_role.auth_failed role=%s",
                role_name,
            )
            return user_or_response

        request_id = _get_request_id(request)
        user: User = user_or_response

        logger.debug(
            "security.permissions.require_role.start role=%s user_id=%s request_id=%s",
            role_name,
            str(user.id),
            request_id,
        )  # BEFORE

        # Build set of role names the user holds.
        held_roles: set[str] = set()
        if hasattr(user, "user_roles") and user.user_roles:
            for ur in user.user_roles:
                if ur.role and ur.role.name:
                    held_roles.add(ur.role.name)

        # D-PERM1: super_admin is a superset — it passes any role check.
        if role_name in held_roles or _SUPER_ADMIN_ROLE in held_roles:
            logger.debug(
                "security.permissions.require_role.ok role=%s user_id=%s request_id=%s",
                role_name,
                str(user.id),
                request_id,
            )  # AFTER
            return user

        logger.warning(
            "security.permissions.require_role.denied role=%s user_id=%s "
            "held_roles=%s request_id=%s",
            role_name,
            str(user.id),
            sorted(held_roles),
            request_id,
        )  # AFTER — warning (visible in non-verbose)

        return _error_response(
            request_id=request_id,
            code="AUTH_PERMISSION_DENIED",
            message="You do not have permission to perform this action.",
            http_status=403,
        )

    # Give the inner function a stable __name__ for FastAPI routing debug output.
    _guard.__name__ = f"require_role_{role_name}"
    return _guard


# ---------------------------------------------------------------------------
# Pre-built guards (§10.2 canonical guards)
# ---------------------------------------------------------------------------

require_admin = require_role(_PEOPLE_ADMIN_ROLE)
"""Dependency: requires 'people_admin' or 'super_admin' role. Returns 403 otherwise."""

require_auditor = require_role(_PEOPLE_AUDITOR_ROLE)
"""Dependency: requires 'people_auditor' or 'super_admin' role. Returns 403 otherwise."""
