"""
Hilo People — Shared admin AI audit helper.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Single source of truth for writing audit rows from the admin/ai subtree.
         Both providers/audit.py and model_catalog/audit.py route through this
         helper so the D-S2 pattern (independent session, commits even if main
         tx rolls back) is implemented once instead of duplicated.

Key deps:
  - app.db.session.audit_session_scope — independent audit session
  - app.db.models.auth.AuditLog — ORM target

Source refs:
  - task pack P02-S05-T001 §D-AASPLIT + validator finding "shared audit boilerplate"
  - 01-non-negotiables.md §Security (audit log obligatorio on writes)

Decisions:
  - D-AA-AUDIT: write_admin_ai_audit centralises the boilerplate; callers
    only supply action/entity/metadata. Independent session protects audit
    persistence on caller rollback.
  - Never logs PII/credentials. The metadata passed in is the caller's
    responsibility — the helper only persists what it receives.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from app.db.models.auth import AuditLog
from app.db.session import audit_session_scope

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def write_admin_ai_audit(
    *,
    actor_user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    metadata: dict[str, Any],
) -> None:
    """Write an `audit_logs` row using the D-S2 independent-session pattern.

    The audit row is committed in its own session so it survives even if the
    caller's main transaction rolls back (e.g. after an EncryptionError).

    Args:
        actor_user_id: Admin who performed the action.
        action:        Canonical action string (e.g. 'admin.ai.provider.create').
        entity_type:   Logical entity type ('ai_provider' / 'ai_model').
        entity_id:     UUID of the entity (placeholder UUID(int=0) when the
                       entity was not persisted — caller's choice).
        metadata:      JSON-serialisable dict — caller filters PII/credentials.
    """
    if _VERBOSE:
        logger.debug(
            "admin._audit.write.start actor=%s action=%s entity_id=%s",
            str(actor_user_id),
            action,
            str(entity_id),
        )  # BEFORE

    try:
        with audit_session_scope() as audit_session:
            row = AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                extra_metadata=metadata,
            )
            audit_session.add(row)
            audit_session.commit()

        if _VERBOSE:
            logger.debug(
                "admin._audit.write.ok actor=%s action=%s entity_id=%s",
                str(actor_user_id),
                action,
                str(entity_id),
            )  # AFTER
    except Exception as exc:
        logger.error(
            "admin._audit.write.error actor=%s action=%s error=%s",
            str(actor_user_id),
            action,
            type(exc).__name__,
            exc_info=True,
        )
