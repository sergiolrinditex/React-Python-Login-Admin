"""
Hilo People — Use case: update user preferred language.

Slice:  P01-S02-T007 — PATCH /api/v1/users/me/language
Phase:  P01 Auth + Data Foundation
Purpose: Business use case that updates a user's preferred_language in the DB,
         writes an audit_log row (D-S2 pattern), and returns the updated UserProfile
         DTO. Validates the language value as a defence-in-depth check (Pydantic
         validates first at the router layer, per G.7).

Dependencies:
  - app.db.models.user.User — ORM model
  - app.db.session.Session — sync session from dep
  - app.users.repositories.user_profile.update_language — DB write
  - app.users.services.get_current_user_profile.build_user_profile — DTO mapper
  - app.users.audit.LanguageUpdateAuditWriter — D-S2 audit write
  - app.users.errors.LanguageInvalidError — defence-in-depth error

Source refs:
  - task pack §G.12 (one use case per file)
  - task pack §F.2 (PATCH /me/language side effects: DB write + audit)
  - task pack §G.6 (idempotent: same language twice → 200 both + both audit rows)
  - task pack §G.8 (updated_at set explicitly by repository)
  - task pack §G.15 (D-S2 audit on success path)

Decisions:
  - G.6: Idempotency — no short-circuit on same language. The DB UPDATE still runs
    and the audit row still writes, recording the user's explicit intent.
  - LanguageInvalidError raised only if language somehow passes Pydantic but is
    not in the whitelist — theoretical safeguard.
  - update_language repo method expires_all after UPDATE and re-selects to get
    the server-confirmed updated_at value.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.models.user import User
from app.users.audit import LanguageUpdateAuditWriter
from app.users.errors import LanguageInvalidError
from app.users.repositories.user_profile import update_language
from app.users.schemas import UserProfile
from app.users.services.get_current_user_profile import build_user_profile

logger = logging.getLogger(__name__)

_VALID_LANGUAGES = frozenset({"es", "en", "fr"})


def patch_user_language(
    session: Session,
    user: User,
    new_language: str,
    request_id: str,
    ip: str,
    user_agent: str = "",
) -> UserProfile:
    """Update preferred_language, write audit row, return updated UserProfile DTO.

    Business rule: language must be in {es, en, fr}. Idempotent: updating to the
    same value is allowed and still writes an audit row (G.6).

    Args:
        session: Active SQLAlchemy sync Session. This use case commits the DB write.
        user: Authenticated User ORM instance (status must be 'active').
        new_language: New language code. Validated by Pydantic at router layer;
                      defence-in-depth check here raises LanguageInvalidError.
        request_id: X-Request-ID for audit metadata correlation.
        ip: Client IP address for audit metadata.
        user_agent: User-Agent header for audit metadata.

    Returns:
        Updated UserProfile DTO reflecting the new language.

    Raises:
        LanguageInvalidError: If new_language is not in {es, en, fr}
                              (should not happen after Pydantic validation).
        sqlalchemy.exc.SQLAlchemyError: On DB failure (propagated to router).
    """
    logger.debug(
        "users.service.update_user_language.start user_id=%s new_language=%s request_id=%s",
        str(user.id),
        new_language,
        request_id,
    )  # BEFORE

    if new_language not in _VALID_LANGUAGES:
        logger.error(
            "users.service.update_user_language.invalid_language user_id=%s value=%r",
            str(user.id),
            new_language,
        )
        raise LanguageInvalidError(new_language)

    from_language = user.preferred_language
    user_id = user.id

    # Write audit FIRST via D-S2 independent session so it persists even on rollback.
    # Note: we write audit before the main DB commit so that if the main tx fails,
    # the audit records the attempt. outcome is still 'success' on the happy path.
    audit_writer = LanguageUpdateAuditWriter(
        actor_user_id=user_id,
        from_language=from_language,
        to_language=new_language,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
    )

    # DB update in main session.
    updated_user = update_language(session, user_id, new_language)
    session.commit()

    # Write audit after successful commit (outcome = success).
    audit_writer.write(outcome="success")

    if updated_user is None:
        # Should be unreachable — user was validated active before this call.
        logger.error(
            "users.service.update_user_language.user_disappeared user_id=%s request_id=%s",
            str(user_id),
            request_id,
        )
        raise RuntimeError(f"User {user_id} disappeared after language update")

    profile = build_user_profile(updated_user)

    logger.debug(
        "users.service.update_user_language.done user_id=%s from=%s to=%s request_id=%s",
        str(user_id),
        from_language,
        new_language,
        request_id,
    )  # AFTER
    return profile
