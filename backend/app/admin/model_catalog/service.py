"""
Hilo People — Admin AI model catalog service (orchestration layer).

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Orchestrates the patch-model use case: locates the model, captures
         FROM state, applies the patch (clearing previous default when
         is_default flips to true), commits or rolls back, and writes the
         audit row (D-S2).

Key deps:
  - app.admin.model_catalog.repository.{get_model_by_id,find_previous_default_id,apply_patch}
  - app.admin.model_catalog.audit.write_model_audit

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract (PATCH /models)
  - task pack P02-S05-T001 §D-DEF1 (at-most-one default per model_type)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.admin.model_catalog.audit import write_model_audit
from app.admin.model_catalog.repository import (
    apply_patch,
    find_previous_default_id,
    get_model_by_id,
)
from app.db.models.admin_ai import AiModel

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


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
        Exception: On persistence failure (caller emits 5xx).
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
    except Exception as exc:
        logger.error(
            "admin.models.service.patch.error actor=%s model_id=%s request_id=%s error=%s",
            str(actor_user_id),
            str(model_id),
            request_id,
            type(exc).__name__,
            exc_info=True,
        )
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
