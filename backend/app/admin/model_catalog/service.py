"""
Hilo People — Admin AI model catalog service (orchestration layer).

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
        P02-S05-T003 — IntegrityError → ModelDefaultConflictError translation (§D-SVC-409)
Phase:  P02 Core Features
Purpose: Orchestrates the patch-model use case: locates the model, captures
         FROM state, applies the patch (clearing previous default when
         is_default flips to true), commits or rolls back, and writes the
         audit row (D-S2).

         P02-S05-T003 extension: catches sqlalchemy.exc.IntegrityError for the
         constraint 'ai_models_default_per_type_uidx' (pgcode=23505) and
         translates it to ModelDefaultConflictError. Other IntegrityError causes
         are re-raised unchanged (not swallowed).

Key deps:
  - app.admin.model_catalog.repository.{get_model_by_id,find_previous_default_id,apply_patch}
  - app.admin.model_catalog.audit.write_model_audit
  - app.admin.model_catalog.errors.ModelDefaultConflictError (P02-S05-T003)

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract (PATCH /models)
  - task pack P02-S05-T001 §D-DEF1 (at-most-one default per model_type)
  - task pack P02-S05-T003 §C (IntegrityError translation spec)
  - Precedent: app/auth/repository.py:131 (IntegrityError → EmailAlreadyExistsError)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin.model_catalog.audit import write_model_audit
from app.admin.model_catalog.errors import ModelDefaultConflictError
from app.admin.model_catalog.repository import (
    apply_patch,
    find_previous_default_id,
    get_model_by_id,
)
from app.db.models.admin_ai import AiModel

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# Constraint name for the partial unique index enforcing D-DEF1.
# If the IntegrityError mentions a DIFFERENT constraint we do NOT catch it here
# (we only translate the specific D-DEF1 constraint, not all unique violations).
_DEFAULT_CONFLICT_CONSTRAINT = "ai_models_default_per_type_uidx"
_PG_UNIQUE_VIOLATION_CODE = "23505"


def _is_default_conflict(exc: IntegrityError) -> bool:
    """Return True if the IntegrityError is for the ai_models_default_per_type_uidx constraint.

    Args:
        exc: The SQLAlchemy IntegrityError to inspect.

    Returns:
        True when the underlying psycopg2/psycopg UniqueViolation is for the
        specific partial unique index that enforces D-DEF1.
    """
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False

    # psycopg2: exc.orig.pgcode; psycopg3: exc.orig.sqlstate
    pgcode = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
    if pgcode != _PG_UNIQUE_VIOLATION_CODE:
        return False

    # Check diag.constraint_name (psycopg2) or repr fallback
    diag = getattr(orig, "diag", None)
    if diag is not None:
        constraint_name = getattr(diag, "constraint_name", "") or ""
        if constraint_name == _DEFAULT_CONFLICT_CONSTRAINT:
            return True

    # Fallback: check str representation of orig (covers psycopg3 which embeds the constraint)
    return _DEFAULT_CONFLICT_CONSTRAINT in str(orig)


def patch_model(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    model_id: uuid.UUID,
    enabled: bool | None,
    is_default: bool | None,
    request_id: str,
    ip: str,
    user_agent: str,
) -> AiModel | None:
    """Patch a model and write the audit row.

    Args:
        session:       Active SQLAlchemy Session (will be committed).
        actor_user_id: Admin performing the action.
        model_id:      Target model UUID.
        enabled:       New enabled value (None = no change).
        is_default:    New is_default value (None = no change).
        request_id:    X-Request-ID.
        ip:            Client IP.
        user_agent:    User-Agent header.

    Returns:
        Updated AiModel on success, None if model_id does not exist.

    Raises:
        ModelDefaultConflictError: When a concurrent PATCH sets is_default=true
            on a different model of the same model_type, causing the DB partial
            unique index to reject this transaction's commit.
        Exception: On any other persistence failure (caller emits 5xx).
    """
    if _VERBOSE:
        logger.debug(
            "admin.models.service.patch.start actor=%s model_id=%s request_id=%s",
            str(actor_user_id),
            str(model_id),
            request_id,
        )  # BEFORE

    model = get_model_by_id(session, model_id)
    if model is None:
        return None

    from_state: dict[str, Any] = {"enabled": model.enabled, "is_default": model.is_default}
    model_type: str = model.model_type

    # Record previous default model id BEFORE mutating so audit metadata is
    # accurate even after the patch clears the other model's flag.
    previous_default_id: uuid.UUID | None = None
    if is_default is True and not model.is_default:
        previous_default_id = find_previous_default_id(
            session, model.model_type, exclude_id=model.id
        )

    try:
        apply_patch(session, model, enabled=enabled, is_default=is_default)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_default_conflict(exc):
            # D-DEF1 race: another concurrent transaction won the race and set
            # is_default=true for the same model_type. Log at WARN (not ERROR)
            # because this is an expected business constraint, not an application bug.
            logger.warning(
                "admin.models.service.patch.conflict "
                "actor=%s model_id=%s model_type=%s request_id=%s "
                "constraint=%s",
                str(actor_user_id),
                str(model_id),
                model_type,
                request_id,
                _DEFAULT_CONFLICT_CONSTRAINT,
            )  # AFTER (conflict path — no PII, no token, no SQL fragment)
            write_model_audit(
                actor_user_id=actor_user_id,
                model_id=model_id,
                from_state=from_state,
                to_state={"enabled": enabled, "is_default": is_default},
                request_id=request_id,
                ip=ip,
                user_agent=user_agent,
                outcome="failure",
                failure_reason="default_conflict",
            )
            raise ModelDefaultConflictError(model_type) from exc
        # Any other IntegrityError is unexpected — log at ERROR and re-raise.
        logger.error(
            "admin.models.service.patch.error actor=%s model_id=%s request_id=%s error=%s",
            str(actor_user_id),
            str(model_id),
            request_id,
            type(exc).__name__,
            exc_info=True,
        )  # ERROR path
        write_model_audit(
            actor_user_id=actor_user_id,
            model_id=model_id,
            from_state=from_state,
            to_state={"enabled": enabled, "is_default": is_default},
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            outcome="failure",
        )
        raise
    except Exception as exc:
        logger.error(
            "admin.models.service.patch.error actor=%s model_id=%s request_id=%s error=%s",
            str(actor_user_id),
            str(model_id),
            request_id,
            type(exc).__name__,
            exc_info=True,
        )  # ERROR path
        session.rollback()
        write_model_audit(
            actor_user_id=actor_user_id,
            model_id=model_id,
            from_state=from_state,
            to_state={"enabled": enabled, "is_default": is_default},
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            outcome="failure",
        )
        raise

    to_state = {"enabled": model.enabled, "is_default": model.is_default}

    write_model_audit(
        actor_user_id=actor_user_id,
        model_id=model.id,
        from_state=from_state,
        to_state=to_state,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        outcome="success",
        previous_default_id=previous_default_id,
    )

    if _VERBOSE:
        logger.debug(
            "admin.models.service.patch.ok actor=%s model_id=%s request_id=%s",
            str(actor_user_id),
            str(model_id),
            request_id,
        )  # AFTER
    return model
