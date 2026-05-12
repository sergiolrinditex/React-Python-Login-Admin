"""
Hilo People — Repository: user profile with employee and roles (eager loading).

Slice:  P01-S02-T007 — GET /api/v1/users/me + PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: SQLAlchemy sync repository for user profile queries and language updates.
         Two public methods:
           - find_by_id_with_employee_and_roles: eager-loads User + EmployeeProfile
             + UserRole + Role in a single query (avoids N+1 per G.9, G.10).
           - update_language: UPDATEs preferred_language + updated_at using the DB
             server's now() to avoid Python-clock vs DB-clock skew on sub-second
             precision. Re-fetches the full eager-loaded user and returns it.

Dependencies:
  - sqlalchemy==2.0.49 (Session, select, update, func, joinedload)
  - app.db.models.user (User, EmployeeProfile, UserRole, Role)
  - logging — BEFORE/AFTER under ENABLE_VERBOSE_LOGGING

Source refs:
  - task pack §G.11 (repository layout decision)
  - task pack §G.9 (joinedload for roles, avoid N+1)
  - task pack §G.10 (joinedload for employee_profile)
  - task pack §G.8 (updated_at explicit app-layer update, no DB trigger)
  - 01-non-negotiables.md §Database (parametrized queries, transactions, indexes)

Decisions:
  - Returns User ORM object (still attached to session) to the service layer.
    The service reads attributes and builds the UserProfile DTO before the session
    closes. This avoids DetachedInstanceError without needing expunge_all().
  - update_language uses sqlalchemy func.now() to ensure updated_at is set by
    the DB server clock, matching the server_default=now() used at INSERT time.
    This avoids Python-clock vs DB-clock sub-second skew (T10/T24 regression).
  - No cascading side effects — the method only touches users.preferred_language
    and users.updated_at.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.db.models.user import User, UserRole

logger = logging.getLogger(__name__)


def find_by_id_with_employee_and_roles(
    session: Session,
    user_id: uuid.UUID,
) -> User | None:
    """Fetch a User with eager-loaded EmployeeProfile and UserRoles/Roles.

    Issues a single SQL query using joinedload to avoid N+1. Returns None
    if no user row exists for user_id.

    Args:
        session: Active SQLAlchemy sync Session (provided by get_db_session dep).
        user_id: UUID of the user to fetch.

    Returns:
        User ORM instance with .employee_profile and .user_roles[].role populated,
        or None if not found.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: On DB failure (propagated to caller).
    """
    logger.debug(
        "user_profile.repository.find_by_id.start user_id=%s", str(user_id)
    )  # BEFORE

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            joinedload(User.employee_profile),
            joinedload(User.user_roles).joinedload(UserRole.role),
        )
    )
    result = session.execute(stmt).unique().scalar_one_or_none()

    logger.debug(
        "user_profile.repository.find_by_id.done user_id=%s found=%s",
        str(user_id),
        result is not None,
    )  # AFTER
    return result


def update_language(
    session: Session,
    user_id: uuid.UUID,
    new_language: str,
) -> User | None:
    """Update preferred_language and updated_at for a user, then re-fetch.

    Uses func.now() (DB server clock) for updated_at to avoid Python-clock vs
    DB-clock skew at sub-second precision (T10/T24 regression from using
    datetime.now(tz=timezone.utc) which can be earlier than the DB's now()).

    Args:
        session: Active SQLAlchemy sync Session. Caller must commit/rollback.
        user_id: UUID of the user to update.
        new_language: New language code ('es' | 'en' | 'fr'). Caller validates.

    Returns:
        Updated User ORM instance with eager-loaded relationships, or None
        if the user does not exist.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: On DB failure (propagated to caller).
    """
    logger.debug(
        "user_profile.repository.update_language.start user_id=%s new_language=%s",
        str(user_id),
        new_language,
    )  # BEFORE

    # Use func.now() (DB server clock) so updated_at monotonically advances
    # relative to the created_at/updated_at set by server_default=now() at INSERT.
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(preferred_language=new_language, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    session.execute(stmt)
    # Expire the session cache so the re-SELECT gets fresh data from DB.
    session.expire_all()
    result = find_by_id_with_employee_and_roles(session, user_id)

    logger.debug(
        "user_profile.repository.update_language.done user_id=%s new_language=%s found=%s",
        str(user_id),
        new_language,
        result is not None,
    )  # AFTER
    return result
