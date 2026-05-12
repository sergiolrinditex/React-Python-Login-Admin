"""
Hilo People — Use case: get current user profile.

Slice:  P01-S02-T007 — GET /api/v1/users/me
Phase:  P01 Auth + Data Foundation
Purpose: Business use case that maps a User ORM instance (already fetched and
         validated by the deps layer) to the UserProfile DTO for the HTTP response.
         This is a pure read — no DB writes, no audit row (G.4/G.5).

Dependencies:
  - app.db.models.user.User — ORM model with loaded relationships
  - app.users.schemas.UserProfile, UserProfileEmployeeFields — response DTOs

Source refs:
  - task pack §G.12 (one use case per file)
  - task pack §F.1 (GET /me side effects: none)
  - task pack §G.9 (roles default to ['employee'] if no user_roles rows)
  - task pack §G.10 (employee_profile null for admin users — DISCREPANCY-3)
  - task pack §F.3 (UserProfile schema — extra_metadata omitted)

Decisions:
  - Pure function: takes an already-authenticated User ORM instance, returns DTO.
    The dep layer (deps.py) owns auth validation; this use case owns DTO mapping.
  - roles: mirrors encode_access_token logic — if user_roles is empty, default ['employee'].
  - employee_profile: None when user has no employee_profile row (admin case).
  - extra_metadata is never included in the DTO (see §F.3 rationale).
"""

from __future__ import annotations

import logging

from app.db.models.user import User
from app.users.schemas import UserProfile, UserProfileEmployeeFields

logger = logging.getLogger(__name__)


def build_user_profile(user: User) -> UserProfile:
    """Map a User ORM instance to the UserProfile response DTO.

    Pure mapping — no DB calls, no side effects. The user must already have
    eager-loaded employee_profile and user_roles relationships.

    Args:
        user: Authenticated User ORM instance with loaded relationships.

    Returns:
        UserProfile DTO ready for serialization.
    """
    logger.debug(
        "users.service.get_current_user_profile.start user_id=%s", str(user.id)
    )  # BEFORE

    # Build roles list (mirrors encode_access_token lines 99-106 for consistency).
    roles: list[str] = []
    if user.user_roles:
        for ur in user.user_roles:
            if ur.role and ur.role.name:
                roles.append(ur.role.name)
    if not roles:
        roles = ["employee"]

    # Build employee_profile DTO (None if admin has no row — DISCREPANCY-3).
    ep_dto: UserProfileEmployeeFields | None = None
    if user.employee_profile is not None:
        ep = user.employee_profile
        ep_dto = UserProfileEmployeeFields(
            employee_id=ep.employee_id,
            brand=ep.brand,
            society=ep.society,
            center=ep.center,
            country=ep.country,
            department=ep.department,
            # extra_metadata intentionally omitted (§F.3)
        )

    profile = UserProfile(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        status=user.status,  # type: ignore[arg-type]
        preferred_language=user.preferred_language,  # type: ignore[arg-type]
        roles=roles,
        employee_profile=ep_dto,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    logger.debug(
        "users.service.get_current_user_profile.done user_id=%s roles=%s has_profile=%s",
        str(user.id),
        roles,
        ep_dto is not None,
    )  # AFTER
    return profile
